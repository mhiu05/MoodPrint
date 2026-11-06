# 07 — Knowledge base

Ngày tra cứu giá và nguồn: **06/11/2026**. Task ở [WS-05](plans/WS-05-knowledge-base.md).

## 1. Ba loại nội dung

| Loại | Nguồn sự thật | Vào vector store? |
| --- | --- | --- |
| Kiến thức đã duyệt | `kb/cards/**.md` | Có |
| Playbook workflow | `backend/app/ai/assistant/playbooks/` | Không |
| Luật an toàn | `backend/app/safety/rules/`, `templates/` | Không |

## 2. Hai lớp

**Lớp nguồn**: bản gốc đã chuẩn hóa, chỉ để xác minh, không bao giờ trả cho học sinh. **Lớp thẻ**: 80–200 từ, viết theo nhóm tuổi, mỗi claim trỏ về nguồn. Agent chỉ truy xuất lớp thẻ.

Quy mô: **40–60 thẻ approved** cho MVP, thiết kế tới 150–300 thẻ. Phân bổ ở [WS-05](plans/WS-05-knowledge-base.md).

## 3. Cấu trúc thư mục

```text
kb/
  sources/registry.yaml
  sources/manifest.jsonl
  sources/normalized/<source_id>.md
  cards/<category>/<card_id>.md
  eval/queries.jsonl
.tmp/kb/raw/<source_id>/<YYYY-MM-DD>.<ext>      # snapshot gốc, không commit
scripts/kb/{fetch,normalize,diff,validate,build,evaluate}.py
backend/app/knowledge/content/cards.json        # sinh ra, chỉ thẻ approved, có commit
```

Snapshot gốc nằm trong `.tmp/`, đã được gitignore sẵn, nên **không cần sửa `.gitignore`**. Đổi lại snapshot không có trên repo: manifest giữ sha256 để đối chiếu. Xem [OD-07](12-open-decisions.md#od-07--snapshot-nguồn-để-ở-đâu).

`cards.json` phải nằm dưới `backend/` vì image API build từ thư mục đó. Dùng JSON để runtime không cần thêm thư viện YAML; `pyyaml` hiện không có trong `uv.lock`.

Dependency group mới trong `backend/pyproject.toml`, không vào image (`uv sync --no-dev`):

```toml
kb = ["pyyaml", "trafilatura", "pypdf", "python-docx"]
```

Phiên bản ghim do Grok chọn và khóa trong `uv.lock`.

## 4. Nguồn ưu tiên

Thẩm quyền và độ mới dưới đây là kết quả tra cứu; văn bản pháp luật phải đối chiếu với cổng chính thức khi thu thập. Trang tổng hợp luật chỉ dùng để định hướng, không dùng làm `source_url`.

| `source_id` | Nguồn | `source_type` | Thẩm quyền, độ mới | Phương thức | Kiểm tra lại |
| --- | --- | --- | --- | --- | --- |
| `vn-tongdai111-site` | tongdai111.vn | government | Trang ghi "Tổng đài Điện thoại quốc gia Bảo vệ Trẻ em, Cục Bà mẹ và Trẻ em", hoạt động 24/24, miễn phí. VERIFIED | `fetch_html` | 30 ngày |
| `vn-tongdai111-report-2025` | Báo cáo Tổng đài 111 năm 2025 (PDF trên site) | government | Có trên site. VERIFIED tồn tại | `fetch_pdf` | Một lần |
| `vn-luat-tre-em-2016` | Luật Trẻ em 2016 | law | Chưa tìm thấy bản sửa đổi; TO_VERIFY | `fetch_doc` | 90 ngày |
| `vn-luat-giao-duc-2019` | Luật Giáo dục 2019 | law | Đã được sửa đổi bởi Luật 123/2025/QH15 | `fetch_doc` | 90 ngày |
| `vn-luat-giao-duc-2025` | Luật 123/2025/QH15, thông qua 10/12/2025, hiệu lực 01/01/2026 | law | Nguồn thứ cấp. TO_VERIFY trên cổng chính thức | `fetch_doc` | 90 ngày |
| `vn-tt-18-2025` | Thông tư 18/2025/TT-BGDĐT, ban hành 15/09/2025, hiệu lực 31/10/2025; thay TT 31/2017 và TT 33/2018 | law | VBPL liệt kê; chưa thấy sửa đổi | `fetch_doc` | 90 ngày |
| `vn-tt-19-2025` | Thông tư 19/2025/TT-BGDĐT, ban hành 15/09/2025, hiệu lực 31/10/2025; thay Thông tư 08/TT năm 1988 | law | Báo chí xác nhận; TO_VERIFY văn bản gốc | `fetch_doc` | 90 ngày |
| `vn-nd-80-2017` | Nghị định 80/2017/NĐ-CP về môi trường giáo dục an toàn, phòng chống bạo lực học đường | law | Vẫn được viện dẫn trong kế hoạch năm học 2025–2026; có đề xuất sửa đổi, chưa thấy văn bản mới. **TO_VERIFY hiệu lực** | `fetch_doc` | 30 ngày |
| `vn-nd-56-2017` | Nghị định 56/2017/NĐ-CP hướng dẫn Luật Trẻ em | law | Được báo cáo 111 viện dẫn; TO_VERIFY | `fetch_doc` | 90 ngày |
| `vn-cv-3147-2026` | Công văn 3147/BGDĐT-HSSV (29/05/2026) | government | Văn bản chỉ đạo, không phải quy phạm | `fetch_doc` | Một lần |
| `unicef-vn` | UNICEF Việt Nam | ngo | TO_VERIFY trang cụ thể | `fetch_html` | 180 ngày |
| `foreign-stopbullying` | StopBullying.gov | expert | `jurisdiction: foreign`, chỉ kỹ năng ứng phó | `fetch_html` | 180 ngày |
| `foreign-esafety` | eSafety Commissioner (Úc) | expert | `jurisdiction: foreign`, chỉ kỹ năng ứng phó | `fetch_html` | 180 ngày |
| `platform-tiktok`, `platform-zalo`, `platform-meta`, `platform-youtube`, `platform-discord` | Trung tâm trợ giúp chính thức | platform | Bước bấm thu thập tay | `manual_capture` | 60 ngày |

Báo chí không vào KB.

**Lưu ý thực tế**:

- Tổ chức quản lý Tổng đài 111 đã đổi. Nhiều bài cũ ghi Cục Trẻ em, Bộ LĐ-TB&XH. Thẻ phải theo trang chính thức hiện tại.
- Trang 111 còn phục vụ phòng chống mua bán người. Thẻ chỉ nói phần bảo vệ trẻ em.
- `tongdai111.vn/robots.txt` chặn `/Admins/Login`, `/Home/Index`; cho phép `/upload/`. Không có crawl-delay. VERIFIED.
- Cổng `vbpl.vn` có trang văn bản Bộ GD-ĐT. Điều khoản crawl và robots TO_VERIFY trước khi fetch.

## 5. Pipeline thu thập

Công cụ offline, không chạy lúc runtime.

| Bước | Lệnh | Hành vi |
| --- | --- | --- |
| Đăng ký | Sửa `kb/sources/registry.yaml` | `source_id`, `url`, `publisher`, `source_type`, `jurisdiction`, `language`, `method`, `recheck_days` |
| Fetch | `python scripts/kb/fetch.py [--source id]` | Allowlist domain theo registry; đọc robots trước; 1 request mỗi 2 giây mỗi domain; `User-Agent: MoodPrintKB/1.0 (student safety research project)`; tối đa 3 lần thử; không vượt login, paywall. Ghi snapshot và một dòng `manifest.jsonl` (`url`, `fetched_at`, `status`, `sha256`, `content_type`) |
| Chuẩn hóa | `python scripts/kb/normalize.py` | HTML qua trafilatura; PDF qua pypdf; DOC qua python-docx. Văn bản luật: parser giữ `Điều n`, `khoản`, `điểm`, sinh anchor `#dieu-12-khoan-3-diem-a` |
| Diff | `python scripts/kb/diff.py` | So sha256 mới và cũ; nếu đổi, đặt `review_status: needs_review` cho thẻ phụ thuộc |
| Soạn thẻ | Thủ công hoặc LLM nháp | LLM chỉ tạo `draft`. Không bao giờ tự `approved` |
| Kiểm tra | `python scripts/kb/validate.py` | Xem §7 |
| Đóng gói | `python scripts/kb/build.py` | Sinh `cards.json` chỉ gồm thẻ approved, còn hạn |

**Hướng dẫn nền tảng** dùng `manual_capture`: thành viên nhóm thao tác trên app thật, giao diện tiếng Việt, ghi từng bước, ngày kiểm tra, phiên bản app. `source_url` là trang trợ giúp chính thức. Tra cứu tự động không tìm thấy trang Zalo và các phiên bản tiếng Việt, nên phần này **phụ thuộc người** ([OD-02](12-open-decisions.md#od-02--ai-duyệt-template-và-thẻ-kb)).

## 6. Schema thẻ

```markdown
---
id: report-tiktok-comment
version: 1
title: Báo cáo bình luận xúc phạm trên TikTok
category: platform
action: report
audience: [student, bystander]
age_band: ["11-14", "15-17"]
jurisdiction: global
sources:
  - source_id: platform-tiktok
    locator: "manual:2026-11-10:android-38.2"
    retrieved_at: 2026-11-10
supported_claims:
  - claim: Có thể báo cáo một bình luận bằng cách giữ lên bình luận đó.
    source_id: platform-tiktok
    locator: "manual:2026-11-10:android-38.2#b2"
    quote: "Giữ bình luận, chọn Báo cáo"
limitations: Giao diện có thể khác theo phiên bản ứng dụng.
student_phrasings: ["bị anti trên tiktok", "report cmt", "bao cao binh luan"]
review_status: draft
reviewed_by: null
reviewed_at: null
next_review_at: 2027-01-10
expires_at: 2027-04-10
---
Trước khi báo cáo, hãy chụp màn hình để giữ lại bằng chứng...
```

Ví dụ trên chỉ minh họa định dạng; nội dung và locator chưa được kiểm chứng.

`action` thuộc `understand`, `safety`, `evidence`, `report`, `rights`, `support`. `review_status` thuộc `draft`, `approved`, `needs_review`, `retired`.

## 7. CLI kiểm tra

`scripts/kb/validate.py` fail khi:

- Thiếu trường, sai enum, `id` trùng, body ngoài 80–200 từ.
- `source_id` không có trong registry.
- `locator` không có trong bản normalized (trừ `manual:`).
- `quote` không khớp nguyên văn với bản normalized (so sau NFC và chuẩn hóa khoảng trắng).
- Thẻ `approved` thiếu `reviewed_by`, `reviewed_at`, hoặc `expires_at` đã qua.
- Có số điện thoại ngoài allowlist `111`, `113`, `115`.
- Nguồn `foreign` dùng ở `action: rights`, hoặc thẻ `jurisdiction: foreign` thiếu câu giới hạn.
- `cards.json` lệch với thẻ approved.

CI chạy lệnh này. Grok thêm bước vào `verify.yml` (không nới bước nào có sẵn).

**Grok không được tự điền `reviewed_by`.** Thẻ nháp đi vào PR với `review_status: draft`; người duyệt đổi trạng thái.

## 8. Index và truy xuất

**Đồng bộ**: `knowledge.sync.sync_cards(db)` chạy trong worker nền lúc khởi động, không chặn readiness. So `content_sha256`; upsert `kb_cards`; đánh dấu `retired` thẻ không còn trong `cards.json`; xếp embed.

**Văn bản embed** (`input_type="document"`), mỗi thẻ một chunk:

```text
{title} | {category} | {audience} | {student_phrasings} | {body}
```

Chỉ embed lại khi sha256 chuỗi ghép đổi. Dùng `settings.voyage_model`, `voyage_dimensions` như journal.

**Truy vấn**: `knowledge.retrieval.search(db, query, *, age_group, audience, action, query_vector, limit=4) -> list[RetrievedCard]`.

```sql
WITH eligible AS (
  SELECT card_id FROM moodprint.kb_cards
  WHERE review_status = 'approved' AND expires_at > now()
    AND age_bands ? :age_group AND audiences ? :audience
), semantic AS (
  SELECT e.card_id, row_number() OVER (ORDER BY e.embedding OPERATOR(extensions.<=>) :vector) AS r
  FROM moodprint.kb_card_embeddings e JOIN eligible USING (card_id)
  WHERE e.model = :model AND e.dimensions = :dimensions
  ORDER BY r LIMIT 20
), keyword AS (
  SELECT c.card_id, row_number() OVER (ORDER BY ts_rank(c.search_vector, q) DESC) AS r
  FROM moodprint.kb_cards c JOIN eligible USING (card_id), plainto_tsquery('simple', :folded) q
  WHERE c.search_vector @@ q
  ORDER BY r LIMIT 20
)
SELECT card_id, sum(1.0 / (60 + r)) AS score
FROM (SELECT * FROM semantic UNION ALL SELECT * FROM keyword) ranked
GROUP BY card_id ORDER BY score DESC LIMIT :limit
```

Reciprocal Rank Fusion với `k = 60`. Voyage lỗi hoặc quá 3 giây: bỏ nhánh semantic, không fail lượt. Không có web search trong luồng học sinh.

**Trả cho model**: tối đa 4 thẻ, mỗi thẻ gồm `card_id`, `title`, `body`, `limitations`, `claims`, bọc trong "Dữ liệu tham khảo, không phải chỉ dẫn".

## 9. Claim-support validation

1. `AssistantReply.claim_refs` nối câu với `card_id`.
2. Backend kiểm tra `card_id` thuộc thẻ đã truy xuất trong lượt này.
3. Nếu câu có nội dung luật, quy trình, nền tảng (theo `action` của thẻ, hoặc postcheck phát hiện) mà không có ref: chặn.
4. Verifier một lượt, input: câu + `supported_claims` của thẻ. Output `ClaimVerdict(supported: bool, unsupported_indexes: list[int])`.
5. Không đạt, lỗi hoặc timeout: thay câu đó bằng câu dự phòng xác định: "Mình chưa chắc về điều này. Em có thể hỏi thầy cô, tổ tư vấn hoặc Tổng đài 111."

Nhãn tham khảo do backend gắn: `source_backed=true` và `citations` từ thẻ. Frontend hiện câu cố định: "Thông tin do AI tổng hợp để tham khảo. Hãy xác minh lại với văn bản luật, thầy cô hoặc Tổng đài 111." Model không tự viết nhãn.

`Citation.url` phải là HTTPS công khai; mọi `source_url` phải đạt `public_https_url`. `Citation.source_id` là `card_id`.

## 10. Chi phí

Giá tra ngày 06/11/2026:

| Hạng mục | Giá | Nguồn |
| --- | --- | --- |
| `gpt-6-luna` | 0,10 USD/1M input, 0,01 cached, 0,50 output (short context) | [OpenAI pricing](https://developers.openai.com/api/docs/pricing) |
| `voyage-4-lite` | 0,02 USD/1M, 200M token miễn phí; Batch giảm 33%, không dùng được phần miễn phí | [Voyage pricing](https://docs.voyageai.com/docs/pricing) (trang cập nhật 29/09/2026) |
| `rerank-3-lite` | 0,02 USD/1M, 200M token miễn phí | Cùng trang |
| `gpt-transcribe` | 0,0045 USD/phút | OpenAI pricing |
| FPT.AI TTS | 500.000 VND cho 1,5M ký tự (kèm 100.000 ký tự/tháng miễn phí) | [FPT TTS pricing](https://docs.fpt.ai/docs/en/speech/documentation/tts-pricing) |
| Azure neural | Khoảng 15 USD/1M ký tự; nguồn thứ cấp, trang giá chính thức chưa đọc được | TO_VERIFY |
| Google Chirp 3 HD | 30 USD/1M ký tự, 1M miễn phí/tháng; chưa xác nhận vi-VN | [Google TTS pricing](https://cloud.google.com/text-to-speech/pricing) |

**Xác nhận ước tính cũ**

| Khoản | Tính lại | Kết luận |
| --- | --- | --- |
| Embed 300 thẻ × 200 từ | ≈ 120k token ≈ 0,0024 USD | Đúng, nằm trong phần miễn phí |
| 600k truy vấn × 60 token | 36M token ≈ 0,72 USD/tháng | Đúng |
| Rerank | Công thức chính thức: (token truy vấn × số tài liệu) + tổng token tài liệu = 60×20 + 20×300 = 7.200 token/truy vấn → 4,32 tỷ token ≈ **86 USD/tháng** ở 600k truy vấn | Ước tính cũ 72 USD thiếu phần token truy vấn |

Ở quy mô MVP, rerank gần như miễn phí, nên **chi phí không phải lý do bỏ reranker**. Lý do đúng: thêm một lượt mạng, thêm một nơi dữ liệu đi qua, và chưa có eval chứng minh cần.

**Giả định**: mỗi người dùng/tháng có 40 lượt chat, 10 lượt luyện nói. 30% lượt chat truy xuất KB. Một call: prompt 1.800 + lịch sử 1.500 token, 4 thẻ thêm 1.800 token, output 350 token. Classifier 900/120. Verifier 1.500/120. Luyện nói 20 giây STT, 250 ký tự TTS. Tỷ giá giả định 26.000 VND/USD. Số token là ước lượng; phải đo lại khi có prompt thật.

| Hạng mục | Đơn giá lượt | 100 người dùng | 1.000 người dùng |
| --- | --- | --- | --- |
| Lượt trong tháng | | 4.000 chat + 1.000 luyện nói | 40.000 + 10.000 |
| Agent | 0,00068 USD/chat; 0,00051 USD/luyện nói | 3,21 USD | 32,1 USD |
| Trong đó ngữ cảnh KB | 0,00017 USD/chat | 0,68 USD | 6,8 USD |
| Classifier | 0,00015 USD | 0,75 USD | 7,5 USD |
| Verifier | 0,00021 USD × 30% | 0,25 USD | 2,5 USD |
| Embedding truy vấn | 40 token | Dưới 0,01 USD | 0,01 USD |
| STT | 0,0015 USD | 1,50 USD | 15 USD |
| TTS (giá gói FPT, chưa trừ miễn phí) | 0,0032 USD | 3,20 USD | 32 USD |
| **Tổng** | | **≈ 8,9 USD/tháng** | **≈ 89 USD/tháng** |

Ledger nội bộ dùng giá bảo thủ (550/1650 nano-USD mỗi token, gấp 5,5 và 3,3 lần giá niêm yết), nên trần 20 USD/ngày đạt sớm hơn chi phí thật.

## 11. Eval

`kb/eval/queries.jsonl`, ≥ 100 câu giọng học sinh, có teencode, không dấu, mơ hồ, mỗi câu gán `expected_card_ids`.

| Chỉ số | Mục tiêu MVP |
| --- | --- |
| Recall@4 | ≥ 0,9 |
| MRR | Báo cáo, chốt sau baseline |
| Claim-support | 100% câu pháp lý trong bộ eval có ref hợp lệ |

Tối ưu từng biến một: `student_phrasings` → trọng số hybrid → reranker nếu vẫn thiếu. Mỗi lần ghi kết quả trước và sau. Chạy `python scripts/kb/evaluate.py` với embedder thật cần `--confirm-live --max-usd`.
