# 04 — Phase 2: Retrieval and Evaluation

> Thuộc `feat/knowledge-base`. Đặc tả cho P2-06 (embedder), P2-08 (retriever), P2-09/10 (benchmark, hiệu chỉnh), P2-11 (API response).
> **Các con số mục tiêu trong tài liệu này là "ngưỡng đề xuất", không phải kết quả đo.** Không có số đo nào được bịa; mọi PASS/FAIL phải đến từ lần chạy thật được ghi trong báo cáo.

## 1. Luồng truy hồi

```mermaid
sequenceDiagram
  participant C as Caller (API / tool)
  participant R as PgVectorKnowledgeRetriever
  participant V as Voyage /v1/embeddings
  participant DB as Postgres knowledge.search_chunks
  C->>R: search(query, scope, timeout_s)
  R->>R: validate timeout, normalize, redact, truncate, build tsquery
  R->>V: embed(query, input_type=query, 1024, truncation=false)
  V-->>R: vector 1024 (hoặc lỗi → hạ cấp lexical)
  R->>DB: SET LOCAL ROLE authenticated; statement_timeout; search_chunks(...)
  DB-->>R: candidates (vector_score/rank, lexical_score/rank, fused)
  R->>R: relevance gate, per-doc cap, optional rerank, score ∈ [0,1], sort
  R-->>C: KnowledgeResult(status ok | no_results)
```

Không giữ transaction qua lời gọi Voyage: embed xong rồi mới mở transaction cho đúng một câu SQL.

## 2. Embedding (đã đối chiếu tài liệu Voyage đọc ngày 2026-11-08)

| Hạng mục | Giá trị / quyết định | Nguồn |
|---|---|---|
| Endpoint | `POST https://api.voyageai.com/v1/embeddings`, `Authorization: Bearer` | docs.voyageai.com/reference/embeddings-api |
| Mô hình mặc định | `voyage-4` ("optimized for general-purpose and multilingual retrieval quality"); ngữ cảnh 32 000 token; chiều mặc định 1024 (tùy chọn 256/512/2048) | docs.voyageai.com/docs/embeddings |
| Ghi chú mô hình | Tài liệu **không** liệt kê tiếng Việt cụ thể và không nói "100+ ngôn ngữ"; chỉ nói multilingual → **phải đo bằng benchmark** | cùng trang |
| `input_type` | `document` khi ingest, `query` khi tìm; không bỏ trống | docs (FAQ) |
| `truncation` | `false` (lỗi thay vì cắt im lặng) | API ref |
| `output_dtype` | `float`; vector đã chuẩn hóa độ dài 1 nên cosine ≡ tích vô hướng | FAQ |
| Giới hạn lô | ≤ 1 000 văn bản/yêu cầu; tổng token/yêu cầu: 320K (`voyage-4`), 120K (`voyage-4-large`), 1M (`voyage-4-lite`) | API ref |
| Giá | `voyage-4`: 0.06 USD/M token; `voyage-4-large`: 0.12; `voyage-4-lite`: 0.02; 200M token đầu miễn phí cho mỗi tài khoản | docs/pricing |
| Rate limit (mức cơ bản) | 2 000 RPM; `voyage-4`: 8M TPM | docs/rate-limits |
| Họ mô hình | Theo FAQ, các mô hình dòng voyage-4 tương thích nhau (tài liệu bằng mô hình A, truy vấn bằng mô hình B) → cấu hình bất đối xứng được **thử nghiệm**, không giả định | docs/faq |
| Reranker | Hiện hành: `rerank-3` (0.05 USD/M), `rerank-3-lite` (0.02 USD/M), ngữ cảnh 32 000 token; ≤ 1 000 tài liệu/yêu cầu; endpoint `POST /v1/rerank`. `rerank-2.5*` là legacy | docs/reranker, docs/pricing |
| Lưu giữ dữ liệu | Có thể **opt-out** việc Voyage lưu và dùng dữ liệu để huấn luyện (cần phương thức thanh toán + quyền Admin; không đảo ngược trong dashboard). Tài liệu đọc được **không nêu mặc định** | docs/faq |

`vector(1024)` thỏa giới hạn 2 000 chiều của chỉ mục `vector` (pgvector); không cần `halfvec`. Chiều 1024 được chốt trong `corpus_versions.embedding_dims` (ràng buộc `= 1024`); đổi chiều ⇒ migration + phiên bản corpus mới.

## 3. Xử lý truy vấn (`knowledge/query.py`)

Thứ tự cố định, mỗi bước là hàm thuần có test:

1. **Pydantic** đã bảo đảm `1 ≤ len(text) ≤ 1000`. Thêm: nếu `timeout_s <= 0` → `KnowledgeTimeout` trước mọi I/O.
2. **Chuẩn hóa:** NFC, bỏ ký tự điều khiển/zero-width, gộp khoảng trắng, `casefold`.
3. **Che thông tin định danh** (xóa, không thay bằng placeholder): email; URL; `@handle`; số điện thoại VN (`(\+?84|0)[\s.\-]?\d{2,3}[\s.\-]?\d{3}[\s.\-]?\d{3,4}`); chuỗi ≥ 8 chữ số liên tiếp; mã định danh dạng 9/12 chữ số. Danh sách này nằm trong `query.py`, có test dương/âm tính.
4. **Cắt** ở `KnowledgeConfig.query_max_chars` (300) tại ranh giới từ.
5. **Chuẩn bị nhánh từ khóa:** bản không dấu bằng cùng hàm với DB (`f_unaccent` tương đương Python: NFD → bỏ dấu kết hợp → `đ→d`; phải cho kết quả **giống hệt** `knowledge.f_unaccent` trên bộ kiểm 134 âm tiết + 200 câu ngẫu nhiên, ghi vào pgTAP và pytest). Tách token `[a-z0-9]+`; bỏ **stopword** (danh sách đã bỏ dấu: `la va cua co khong thi toi minh ban gi nhu the nao bi cho duoc khi mot cac nhung de o trong voi`; điều chỉnh bằng dev split); loại token 1 ký tự; tối đa 16 token; dựng chuỗi `t1 | t2 | …` (**chỉ** token đã lọc `[a-z0-9]+`, nên không có toán tử tsquery nào từ người dùng lọt vào `to_tsquery('simple', …)`).
6. **Embed** bản đã che/cắt (có dấu, NFC), không phải bản không dấu (mô hình đa ngôn ngữ hiểu dấu tốt hơn).
7. Nếu sau bước 3–4 chuỗi rỗng → `KnowledgeResult(status="no_results", chunks=[], …)`, không gọi mạng.

## 4. Truy hồi lai và chấm điểm

### 4.1 Hàm SQL `knowledge.search_chunks` (`SECURITY INVOKER`, `STABLE`)

```text
search_chunks(p_version text, p_tsquery text, p_query_embedding vector(1024),
              p_languages text[], p_country_scope text[], p_age_band text, p_topics text[],
              p_vector_k int, p_lexical_k int, p_rrf_k int, p_limit int)
returns table (chunk_id text, document_id text, heading text, text text,
               vector_score float8, vector_rank int, lexical_score float8, lexical_rank int, fused float8)
```

- `p_version` null → phiên bản `published`. Với `authenticated`, RLS chỉ cho thấy bản `published`; ghim bản khác chỉ hoạt động với kết nối quản trị của harness eval.
- Bộ lọc áp dụng trên `documents`: `language = ANY(p_languages)`; nếu `p_country_scope` không rỗng: `country_scope && p_country_scope`; nếu `p_age_band` không null: `cardinality(age_bands)=0 OR p_age_band = ANY(age_bands)`; nếu `p_topics` không rỗng: `topics && p_topics`.
- **Nhánh vector** (bỏ nếu `p_query_embedding` null): `1 - (embedding <=> q)` làm `vector_score`, `row_number() over (order by embedding <=> q)`, `limit p_vector_k`. `ORDER BY` trực tiếp trên toán tử khoảng cách để tận dụng chỉ mục nếu có.
- **Nhánh từ khóa:** `fts @@ to_tsquery('simple', p_tsquery)`; `lexical_score = ts_rank_cd(fts, tsq, 32)` (chuẩn hóa `rank/(rank+1)` ⇒ [0,1)); `limit p_lexical_k`.
- **Hợp nhất RRF:** `full outer join` hai nhánh theo `chunk_id`; `fused = 1/(rrf_k + vector_rank) * w_v + 1/(rrf_k + lexical_rank) * w_l` (thiếu nhánh ⇒ 0), `w_v = w_l = 1`; sắp theo `fused desc, chunk_id`; `limit p_limit`.
- Tham số tuning đặt bằng `SET LOCAL` từ Python khi dùng chỉ mục: `hnsw.ef_search`, `hnsw.iterative_scan = relaxed_order` (chỉ nếu P2-10 tạo HNSW).
- Mô hình mẫu lấy từ hướng dẫn hybrid search của Supabase (FTS + vector + RRF, `rrf_k` mặc định 50); pgvector ≥ 0.8 hỗ trợ `iterative_scan` để lọc không làm tụt recall của HNSW; **mặc định không HNSW** (xem `02` P2-02).

### 4.2 Chấm điểm và cổng liên quan (`scoring.py`)

```text
cos        = vector_score                          (null nếu không có nhánh vector)
vec_rel    = clamp((cos - c_lo) / (c_hi - c_lo), 0, 1)       c_lo, c_hi = hiệu chỉnh ở P2-10
lex_rel    = lexical_score
relevance  = max(vec_rel, lex_rel)                 (dùng cho CỔNG; không phải điểm xuất)
gate       : giữ chunk nếu vec_rel ≥ min_vector_score  HOẶC  lex_rel ≥ min_lexical_score
ranking    : chế độ rrf   (mặc định): score = fused / fused_max,  fused_max = (w_v + w_l)/(rrf_k + 1)
             chế độ blend             : score = w_v' * vec_rel + w_l' * lex_rel   (w_v'+w_l'=1)
cap        : tối đa max_chunks_per_document (mặc định 2) chunk mỗi tài liệu trong top_k
output     : sort theo (-score, chunk_id); cắt top_k; status = ok nếu còn ≥ 1 chunk, ngược lại no_results
match_kind : "hybrid" nếu chunk có mặt ở cả hai nhánh; "vector"/"lexical" nếu chỉ một nhánh;
             toàn bộ "lexical" khi embedding thất bại (hạ cấp)
```

Hai chế độ `rrf`/`blend` và `rerank` là **ứng viên** được so ở P2-10 theo quy tắc quyết định của `02`. `c_lo`, `c_hi`, `min_vector_score`, `min_lexical_score`, `rrf_k`, `max_chunks_per_document` bắt đầu bằng giá trị tạm bảo thủ (ghi rõ "tạm thời" trong báo cáo cho tới P2-10) và được khóa vào `KnowledgeConfig`. **Không** công bố giá trị cụ thể trước khi đo.

**Vì sao cần cổng:** truy hồi vector luôn trả "gần nhất" kể cả khi không liên quan; hợp đồng đòi `no_results` thật (`test_no_results_is_not_error`) và Agent không được bịa citation (IT-04).

### 4.3 Rerank (tùy chọn, mặc định tắt)

Nếu `rerank_enabled`: gửi tối đa 20 ứng viên sau cổng tới `POST /v1/rerank` (`model=rerank-3`, `top_k=min(top_k*2, 10)`, `truncation=true`); `score := relevance_score`; áp thêm ngưỡng `min_rerank_score` hiệu chỉnh ở P2-10. Lỗi rerank ⇒ giữ thứ tự hybrid, không lỗi. Chỉ được bật theo quy tắc quyết định (nDCG@10 +0.03 trên test và p95 trong ngân sách).

## 5. Ma trận lỗi

| Điều kiện | Hành vi của `PgVectorKnowledgeRetriever.search` |
|---|---|
| `timeout_s <= 0` | `KnowledgeTimeout` ngay (trước I/O) |
| Vượt `timeout_s` tổng | hủy tác vụ con, `KnowledgeTimeout` (không trả kết quả một phần) |
| Embed: 429/5xx/timeout sau retry, hoặc ngân sách embed (60% `timeout_s`) cạn | **hạ cấp lexical-only**; mọi chunk `match_kind="lexical"`; log WARNING chỉ chứa mã (`embed_unavailable`); API phản hồi `degraded=true` |
| Embed: 401/403 (khóa sai) hoặc 400 (cấu hình sai) | `KnowledgeUnavailable` (lỗi cấu hình phải ồn ào, không âm thầm hạ cấp vĩnh viễn) |
| DB: lỗi kết nối, `statement_timeout`, thiếu hàm, quyền | `KnowledgeUnavailable` |
| Chưa có bản `published` | `KnowledgeUnavailable` với mã nội bộ `no_published_corpus` (khác `no_results`) |
| `scope.corpus_version` không truy cập được | `KnowledgeUnavailable` (`corpus_version_not_available`) |
| `asyncio.CancelledError` | truyền ra, hủy HTTP/DB đang chạy, không nuốt |
| Truy vấn rỗng sau che | `no_results` không I/O |
| Không chunk nào vượt cổng | `no_results` (**không** raise) |

Quy tắc chung: không bao giờ trả dữ liệu fixture/mock thay thế; không bao giờ treo quá `timeout_s + 0.5 s` (test bằng DB giả chặn).

## 6. Riêng tư của truy vấn

| Rủi ro | Biện pháp |
|---|---|
| Truy vấn của học sinh có thể chứa tên người/sự việc và được gửi tới **Voyage** | Che email/điện thoại/URL/@handle; cắt 300 ký tự; **không** log nguyên văn ở bất kỳ tầng nào (test canary `ZZ-CANARY-<uuid>` quét mọi log); Phase 3 thêm hướng dẫn cho model chỉ tạo truy vấn tổng quát, không có tên riêng |
| Voyage lưu/huấn luyện trên dữ liệu | **Owner O-06:** bật opt-out huấn luyện trong dashboard Voyage (cần thẻ và quyền Admin; không đảo ngược). Cho tới khi có xác nhận, chỉ dùng truy vấn tổng hợp |
| Cache | Cache nhúng chỉ cho văn bản corpus (công khai); **không** cache truy vấn người dùng |
| Phân tích | Chỉ ghi độ dài, số kết quả, `status`, `latency_ms`, `corpus_version`, `degraded` |
| Hub | Hiện dòng lưu ý: "Đừng nhập tên thật hoặc thông tin liên hệ." |

Rủi ro còn lại (ghi trong báo cáo): không thể phát hiện mọi tên riêng trong văn bản tự do.

## 7. Đánh giá

### 7.1 Nguyên tắc

- Không dùng LLM làm giám khảo (AD-20). Nhãn do coding agent Phase 2 gán và rà soát; chỉ số tính bằng mã.
- Bộ dữ liệu **tổng hợp và tự viết**; không chứa dữ liệu thật.
- **Khóa test split trước khi tinh chỉnh** (commit riêng, ghi `split_sha256`); chỉ chạy test split **một lần** cho cấu hình đã khóa.
- Báo cáo kèm khoảng tin cậy bootstrap 95% (1 000 lần lấy mẫu lại, hạt cố định) vì cỡ mẫu nhỏ (≈ 81 truy vấn có đáp án ở test).

### 7.2 Bộ dữ liệu (180 truy vấn)

| Nhóm | Số | Ghi chú |
|---|---|---|
| Có đáp án (answerable) | 150 | |
| ↳ phong cách: chuẩn / không dấu / tiếng lóng-thân mật / kể lể mơ hồ / pha tiếng Anh | 50 / 35 / 30 / 25 / 10 | không dấu: viết tay như người dùng gõ nhanh (tối đa 50% sinh tự động từ truy vấn chuẩn; biến thể **cùng split** với bản gốc) |
| ↳ chủ đề: cyber 35, help-seeking 25, evidence 20, physical 15, verbal/social 15, exclusion 15, school-procedure-vn/legal-vn 15, bystander 10 | 150 | mỗi truy vấn có `topic` chính |
| Không có đáp án | 30 | ngoài phạm vi (thời tiết, bài tập, nội dung người lớn) 20; **thuộc miền nhưng corpus không có** 10 (khoảng trống đã biết) |
| Split | dev 72 (40%) / test 108 (60%) | phân tầng theo phong cách, chủ đề, answerable |

Ví dụ phong cách: chuẩn — "Làm thế nào để lưu lại bằng chứng khi bị nhắn tin đe dọa?"; không dấu — "bi ban nhan tin de doa trong nhom lop"; lóng — "bị cả lớp bơ với kể xấu hoài, chịu hết nổi"; mơ hồ — "dạo này đi học cứ thấy sợ, có bạn hay nhìn mình rồi cười"; pha tiếng Anh — "bị cyberbully trên TikTok thì report sao".

Mỗi dòng JSONL: `{id, split, text, style, topic, age_band, answerable, filters, relevant:[{document_id, grade}], derived_from?, notes}` với `grade ∈ {1,2}` (2 = trả lời trực tiếp, 1 = hữu ích một phần).

### 7.3 Gán nhãn

1. **Pooling:** hợp top-10 của mọi cấu hình A–D + tìm tay toàn corpus; không gán nhãn chỉ trên kết quả của một hệ thống.
2. Gán độ liên quan ở mức **tài liệu**; có thể ghi `anchor_chunks` để đo độ chính xác citation.
3. Gán lại ngẫu nhiên 20% truy vấn ở lượt hai (cách ≥ 1 ngày làm việc nếu có, nếu không thì sau khi làm việc khác) và báo cáo mức đồng thuận (mục tiêu ≥ 0.90 trên nhãn nhị phân).
4. Truy vấn "không đáp án" được xác nhận bằng tìm tay toàn corpus.

### 7.4 Cấu hình so sánh

A lexical-only · B vector-only · C hybrid (`rrf`) · C′ hybrid (`blend`) · D hybrid + `rerank-3`. Biến thể mô hình: `voyage-4` đối xứng; (tài liệu `voyage-4-large`, truy vấn `voyage-4-lite`) bất đối xứng. Với mỗi cấu hình ghi `config.json` (mô hình, dims, `rrf_k`, ngưỡng, `max_chunks_per_document`, `corpus_version`, commit, ngày).

### 7.5 Chỉ số và ngưỡng đề xuất (trên **test split**, truy vấn có đáp án trừ khi nói khác)

| Chỉ số | Định nghĩa | Ngưỡng đề xuất |
|---|---|---|
| **Hit@5** | có ≥ 1 tài liệu `grade ≥ 1` trong top-5 tài liệu | ≥ 0.90 |
| **Recall@5** (chặn) | `|rel ∩ top5| / min(|rel|, 5)` | ≥ 0.80 tổng; ≥ 0.72 nhóm không dấu; ≥ 0.65 nhóm lóng |
| **Recall@10** (chặn) | như trên với 10 | ≥ 0.90 |
| **MRR@10** | nghịch đảo hạng tài liệu liên quan đầu tiên | ≥ 0.60 |
| **nDCG@10** | gain `2^g − 1`, tài liệu khử trùng | ≥ 0.65 |
| **No-result accuracy** | `no_results` đúng / số truy vấn không đáp án | ≥ 0.90 (≥ 27/30) |
| **False-no-result rate** | `no_results` trên truy vấn có đáp án | ≤ 0.08 |
| **Citation integrity** | mọi chunk trả về: `source_id` tồn tại, `document_id` tồn tại trong phiên bản, URL ∈ allow-list, `last_reviewed` đặt, văn bản = DB, bộ lọc ngôn ngữ/quốc gia thỏa | **100%** (cổng cứng) |
| **Citation precision@1** | top-1 tài liệu `grade ≥ 1` | ≥ 0.75 |
| **Độ trễ ấm** | p50 / p95 của `search` đầy đủ gồm lời gọi Voyage, tuần tự, sau 5 lần làm nóng, 3 lượt | p50 ≤ 600 ms; p95 ≤ 1 200 ms; khi hạ cấp lexical ≤ 150 ms |
| **Chi phí** | token Voyage × giá công bố, mỗi 1 000 truy vấn | ≤ 0.02 USD/1 000 truy vấn (≈ 30–60 token/truy vấn × 0.06 USD/M ≈ 0.004 USD) |
| **So với đường cơ sở** | C hoặc D phải hơn max(A,B) | +0.03 Recall@5 (C) / +0.03 nDCG@10 (D) |

Nếu một chỉ số không đạt: báo **FAIL**, nêu nguyên nhân (nhóm truy vấn, chủ đề thiếu tài liệu) và kế hoạch; không hạ ngưỡng im lặng. Hạ ngưỡng dưới 80% giá trị đề xuất cần owner duyệt (O-10).

### 7.6 Kiểm thử trong CI (ngoại tuyến)

`HashingEmbedder` + corpus tổng hợp nhỏ + bộ 20 truy vấn: kiểm hạ tầng harness (chỉ số tính đúng, split không rò, cổng `no_results` đúng với nhiễu `zzzznomatchsynthetic`) và các **sàn** đơn giản (nhánh từ khóa tìm thấy tài liệu có từ trùng khớp). Không dùng ngưỡng chất lượng thật trong CI.

## 8. Hình dạng phản hồi API (P2-11)

```jsonc
// GET /v1/knowledge/search?q=…&topic=cyber&age=11-13&limit=5
{ "status": "ok",                     // hoặc "no_results"
  "corpusVersion": "kb-20261112-01",
  "mode": "hybrid",                   // "hybrid" | "lexical"
  "degraded": false,
  "latencyMs": 412,
  "chunks": [ { "chunkId": "…", "text": "…", "score": 0.83, "matchKind": "hybrid",
                "citation": { "sourceId": "…", "documentId": "…", "title": "…", "publisher": "…",
                              "url": "https://…", "section": "…", "publishedAt": null, "lastReviewed": "2026-11-12",
                              "applicability": "…", "countryScope": ["VN"] } } ] }
```

`GET /v1/knowledge/documents/{documentId}` trả `sections[]` (heading + chunk text theo thứ tự) và `citation`, `derivedFrom[]` (chỉ `sourceId`, `publisher`, `title`, `url`, `locator`). `GET /v1/knowledge/sources` trả danh sách công khai (không có `licence_note`). `GET /v1/knowledge/corpus` trả phiên bản, số tài liệu/chunk, ngày publish. Hub ánh xạ camelCase → kiểu UI trong `services/http/knowledge.ts`.

## 9. Xác minh citation

| Cấp | Khi nào | Nội dung |
|---|---|---|
| Cấu trúc | `validate` (mỗi phiên bản) | FK, `licence_class`, `verified_on`, `last_reviewed`, allow-list URL |
| Nội dung | `verify-citations` | `sha256(chunk.text) == content_sha256`; chunk thuộc đúng tài liệu; thẻ biên soạn có `derived_from` hợp lệ |
| Liên kết | `--link-check` (tùy chọn, báo cáo thông tin) | HEAD tới URL công khai; không chặn gate vì phụ thuộc mạng |
| Thời gian chạy | benchmark | Citation integrity 100% trên mọi chunk trả về |
| Tích hợp | IT-03/IT-04 | `source_id` do `knowledge_search` trả về tồn tại trong `knowledge.sources`; không citation khi `no_results` |

## 10. Ngân sách hiệu năng

| Thành phần | Mục tiêu p95 | Ghi chú |
|---|---|---|
| Chuẩn hóa + che | ≤ 5 ms | thuần CPU |
| Embed Voyage | ≤ 500 ms (kể cả mạng) | ngân sách con 60% `timeout_s` |
| SQL `search_chunks` | ≤ 60 ms ở ≤ 5 000 chunk | quét chính xác; đo ở P2-10 |
| Rerank (nếu bật) | ≤ 400 ms | tùy chọn |
| Tổng | ≤ 1 200 ms | tool Phase 3 đặt `timeout_s = 6` |
| Đồng thời | 8 truy vấn/tiến trình | semaphore; pool `db_pool_size=5` không cạn (test) |
