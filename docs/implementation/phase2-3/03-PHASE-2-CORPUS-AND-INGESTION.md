# 03 — Phase 2: Corpus Strategy and Ingestion Pipeline

> Thuộc `feat/knowledge-base` (Grok 4.7). Đặc tả kỹ thuật cho P2-01, P2-03…P2-07. Bổ sung cho `02` (kế hoạch/task) và `04` (truy hồi/đánh giá).
> **Trạng thái nghiên cứu nguồn:** các dòng "VERIFIED-fetch" nghĩa là trang đã được **mở và đọc** trong phiên planning ngày 2026-11-08; "UNVERIFIED" nghĩa là chưa đọc được (HTTP 403) hoặc chỉ có nguồn thứ cấp. **Không** coi UNVERIFIED là sự thật cho tới khi P2-01 xác minh.

## 1. Nguyên tắc

1. **Curated offline first.** Không scrape không giới hạn. Mỗi nguồn là một file `sources/<id>.toml` được duyệt thủ công, có allow-list host, có `licence_class`.
2. **Giấy phép quyết định dạng lưu.** Chỉ `open_reuse` và `authored` được tạo thành chunk và publish. `reference_only` chỉ được liệt kê (siêu dữ liệu + liên kết). `unverified` bị loại khỏi build.
3. **Nội dung tiếng Việt là ưu tiên.** Nguồn tiếng Anh dùng cho truy hồi chéo ngôn ngữ chỉ khi giấy phép cho phép nhúng nguyên văn; không dịch nguyên văn nguồn bị bảo hộ.
4. **Trung thực nguồn gốc.** Thẻ tự biên soạn luôn gọi đúng tên là "Tóm tắt biên soạn", dẫn nguồn gốc có `locator`; không ghi như thể tổ chức nguồn đã phát biểu câu đó.
5. **Bất biến theo phiên bản.** Một bản corpus đã `published` không bao giờ bị sửa tại chỗ.
6. **Không dữ liệu người dùng** trong corpus; không tên thật; không số điện thoại cá nhân (trừ số đường dây đã xác minh như 111).

## 2. Tiêu chí đánh giá nguồn

Chấm 0–3 mỗi tiêu chí; ghi vào `SOURCE-REGISTER.md` cùng bằng chứng.

| Tiêu chí | 0 | 3 |
|---|---|---|
| **Thẩm quyền** | Blog, không rõ tác giả | Cơ quan nhà nước/tổ chức quốc tế/đơn vị chính thức, văn bản có số hiệu hoặc ấn phẩm có ISBN |
| **Liên quan** | Lạc đề | Trực tiếp về bạo lực/bắt nạt học đường, an toàn mạng, bảo quản bằng chứng, tìm người lớn đáng tin |
| **Giấy phép** | Không rõ/cấm | Văn bản quy phạm không thuộc phạm vi quyền tác giả (cần xác nhận), CC BY/BY-SA, public domain có tuyên bố |
| **Ngôn ngữ** | Ngôn ngữ ngoài vi/en | Tiếng Việt chính thức |
| **Áp dụng/Quốc gia** | Pháp lý nước khác, dễ gây hiểu lầm | Áp dụng tại Việt Nam, hoặc khái niệm trung lập nêu rõ phạm vi |
| **Độ mới & trích xuất** | Quá cũ/không trích xuất được | Có ngày rõ ràng ≤ 3 năm hoặc văn bản còn hiệu lực; HTML/PDF text sạch |

**Ngưỡng nhập corpus:** tổng ≥ 12/18, giấy phép ≥ 2, thẩm quyền ≥ 2, và `verified_on` có giá trị. Hạng 1 (thẩm quyền cao nhất) cho văn bản quy phạm và tổ chức nhà nước/liên chính phủ; hạng 2 UN/WHO/UNICEF/UNESCO; hạng 3 NGO uy tín; hạng 4 tài liệu biên soạn nội bộ có đối chiếu.

## 3. Nguồn ứng viên (bản đồ xuất phát cho P2-01)

| ID đề xuất | Nguồn | Ngôn ngữ | Bằng chứng trong phiên planning | Giấy phép phát hiện | Hạng đề xuất | Cách dùng |
|---|---|---|---|---|---|---|
| `vn-nd-80-2017` | Nghị định 80/2017/NĐ-CP (môi trường giáo dục an toàn, lành mạnh, thân thiện, phòng chống bạo lực học đường) | vi | UNVERIFIED: `thuvienphapluat.vn` trả 403; nguồn thứ cấp nêu ban hành 17/07/2017, hiệu lực 05/09/2017 | Văn bản quy phạm pháp luật thường không thuộc phạm vi bảo hộ quyền tác giả theo Luật Sở hữu trí tuệ (Điều 15) — **chưa xác nhận** văn bản điều khoản hiện hành | `open_reuse` nếu xác nhận | Nguồn pháp lý lõi: chunk theo Điều/Khoản; xác minh tình trạng hiệu lực tại 2026-11 |
| `vn-tt-06-2019-bgddt` | Thông tư 06/2019/TT-BGDĐT Quy tắc ứng xử trong cơ sở giáo dục | vi | UNVERIFIED (403; URL chỉ đoán) | như trên | `open_reuse` nếu xác nhận | Quy tắc ứng xử/trách nhiệm trường |
| `vn-tt-38-2019-bldtbxh` | Thông tư 38/2019/TT-BLĐTBXH (một thông tư năm 2019 liên quan Nghị định 80) | vi | UNVERIFIED: **tên đầy đủ chưa xác minh** (kết quả tìm kiếm thứ cấp có tiêu đề hướng dẫn xây dựng môi trường giáo dục an toàn) | như trên | `open_reuse` nếu xác nhận | Hướng dẫn thực hiện; xác minh tiêu đề trước khi ghi |
| `vn-luat-tre-em-2016` | Luật Trẻ em 2016 (102/2016/QH13) | vi | UNVERIFIED (403) | như trên | `open_reuse` nếu xác nhận | Quyền trẻ em, bảo vệ trẻ em, Tổng đài 111 |
| `vn-111-hotline` | Tổng đài Quốc gia Bảo vệ Trẻ em: "Số điện thoại bảo vệ trẻ em" (`tongdai111.vn/tin/so-dien-thoai-bao-ve-tre-em`) | vi | **VERIFIED-fetch**: số 111; hoạt động 24/24; miễn phí cước gọi và cước tư vấn; thành lập theo Luật Trẻ em 2016; đơn vị vận hành thuộc Cục Trẻ em (trang ghi Bộ LĐTBXH — **tên cơ quan chủ quản cần kiểm lại sau cải tổ bộ 2025**); không có ngày | `© Bản quyền thuộc về Tổng đài 111` (không có giấy phép mở) | `authored` (chỉ **sự kiện**: số 111, 24/24, miễn phí) | Thẻ "Gọi 111 khi nào" dẫn nguồn; không chép văn bản trang |
| `unicef-vn-cyberbullying` | UNICEF Việt Nam, "Bắt nạt trực tuyến là gì — Làm thế nào để ngăn chặn điều này?" (16/02/2021) | vi | **VERIFIED-fetch**; bản gốc tiếng Anh "Cyberbullying: What is it and how to stop it" | `unicef.org/legal`: *"UNICEF reserves all copyrights on material on its Web pages"*; sao chép/dịch cần giấy phép viết qua biểu mẫu liên hệ | `reference_only` | Liệt kê + thẻ biên soạn dẫn nguồn (sự kiện/ý chính, không chép câu). Hỏi owner có xin phép không (O-05) |
| `unesco-2019-behind-the-numbers` | UNESCO, *Behind the numbers: Ending school violence and bullying* (2019) | en (fr/es/it có; chưa thấy vi) | Nguồn **thứ cấp** (danh mục aidsdatahub): CC BY-SA 3.0 IGO, ISBN 978-92-3-100306-6 | CC BY-SA 3.0 IGO (cần xác minh tại trang UNESCO) | `open_reuse` (SA) nếu owner chấp nhận ShareAlike | Số liệu/khái niệm; trích đoạn ngắn tiếng Anh `language=en` |
| `who-youth-violence-2026` | WHO, Fact sheet "Youth violence" (08/05/2026) | en | **VERIFIED-fetch**: có đoạn về bắt nạt; không có tuyên bố giấy phép trong thân trang; trang `who.int/about/policies/publishing/copyright`: ấn phẩm WHO theo CC BY-NC-SA 3.0 IGO (phi thương mại, chia sẻ tương tự); phạm vi "ấn phẩm" — **fact sheet có thuộc không: chưa rõ** | CC BY-NC-SA 3.0 IGO (có điều kiện) | `reference_only` (mặc định) | Chỉ liệt kê; cân nhắc nâng hạng khi owner xác nhận dự án phi thương mại (O-05) |
| `stopbullying-what-is`, `stopbullying-report-cyber` | StopBullying.gov (HHS): *What Is Bullying*, *Report Cyberbullying* | en | UNVERIFIED (403 cả 3 trang, gồm trang reuse) | Dự kiến: nội dung liên bang Hoa Kỳ thường public domain — **chưa xác nhận** trên trang | `open_reuse` nếu xác nhận; phạm vi `GLOBAL`, nêu rõ không áp dụng pháp luật Hoa Kỳ ở VN | Khái niệm (lặp lại, chênh lệch quyền lực), bảo quản bằng chứng/báo cáo nội dung |
| `moet-portal` | Cổng Bộ GD&ĐT (`moet.gov.vn`) | vi | **VERIFIED-fetch**: "Bản quyền thuộc về: Bộ Giáo dục và Đào tạo"; trang chủ/văn bản mới (Thông tư 70–93/2026) không có cẩm nang bạo lực học đường; Thông tư 06/2019 không ở trang 1 | Văn bản hành chính; cẩm nang chưa tìm thấy | tìm tiếp | P2-01 tìm hướng dẫn/cẩm nang chính thức |
| `platform-help-*` | Trung tâm trợ giúp Facebook/Instagram/TikTok/YouTube/Zalo (chặn, báo cáo, lưu bằng chứng) | vi/en | Chưa nghiên cứu | Thường bảo lưu bản quyền | `reference_only` | Chỉ liên kết, ghi `last_reviewed`; hướng dẫn thao tác thay đổi nhanh nên **không** nhúng nguyên văn |
| `ngo-*` (Save the Children VN, ChildFund VN, v.v.) | Tài liệu phòng chống bắt nạt | vi | Chưa nghiên cứu | cần đọc | tìm tiếp | Mở rộng tài liệu hướng dẫn cho trẻ/phụ huynh/giáo viên |
| `mp-authored` | MoodPrint biên soạn | vi | Có sẵn: 24 bài tĩnh ở `frontend/src/mocks/data/knowledge.ts` (4 nguồn `UNICEF-VN`, `STOP-DEFINITION`, `STOP-REPORT`, `VN-111` và các nguồn khác trong `sources.ts`) | Nội dung dự án | `authored` | Hạt giống corpus + phần lớn nội dung |

Ghi chú pháp lý cần P2-01 xác minh và **không được** suy diễn: (1) đoạn Điều 15 Luật Sở hữu trí tuệ về văn bản quy phạm pháp luật; (2) hiệu lực và văn bản thay thế của từng văn bản; (3) tên cơ quan chủ quản Tổng đài 111 sau cải tổ bộ 2025; (4) mọi con số thống kê (ví dụ "25% trẻ em bị bắt nạt" của WHO không có trích dẫn trên trang) — chỉ nhập số liệu có nguồn gốc ấn phẩm rõ ràng và ngày.

### 3.1 Ma trận chủ đề phủ (mục tiêu ≥ 3 tài liệu/chủ đề, ≥ 2 nguồn gốc khác nhau khi có thể)

| Topic ID | Nội dung | Ví dụ truy vấn |
|---|---|---|
| `definition` | Thế nào là bắt nạt; dấu hiệu; phân biệt trêu đùa/xung đột | "trêu nhau có tính là bắt nạt không" |
| `physical` | Bạo lực thể chất | "bị bạn đánh ở sân trường" |
| `verbal-social` | Lăng mạ, tung tin đồn | "cả lớp nói xấu mình sau lưng" |
| `exclusion` | Cô lập, loại khỏi nhóm | "không ai chơi cùng, bị loại khỏi nhóm" |
| `cyber` | Quấy rối trực tuyến, nhóm chat, tài khoản giả, lộ thông tin | "bị lập nhóm nói xấu trên Zalo" |
| `evidence` | Lưu bằng chứng, chụp màn hình, mốc thời gian | "chụp màn hình lưu lại như nào" |
| `help-seeking` | Nói với người lớn đáng tin; cách mở lời | "nói với cô giáo thế nào" |
| `school-procedure-vn` | Quy trình tại trường, vai trò GVCN/ban giám hiệu | "báo với trường thì ai xử lý" |
| `legal-vn` | Quyền trẻ em, tổng đài 111, khi nào cần cơ quan chức năng | "khi nào gọi 111" |
| `bystander` | Người chứng kiến | "thấy bạn bị bắt nạt thì làm gì" |
| `emotional-impact` | Cảm xúc, tự chăm sóc (không chẩn đoán) | "bị bắt nạt xong rất lo" |
| `parents-teachers` | Dành cho phụ huynh/giáo viên | "nói với bố mẹ như nào" |
| `platform-reporting` | Chặn/báo cáo nội dung (nguyên tắc chung) | "báo cáo bài đăng trên TikTok" |
| `urgent-safety` | Nguy cơ tức thời: nơi gọi giúp | "mình sợ bị đánh nữa" |

`topics` trong DB và trong `KnowledgeFilters.topics` dùng đúng các ID trên (danh sách kín). Bảng ánh xạ sang chủ đề cục bộ của UI nằm trong `services/http/knowledge.ts`.

## 4. Mô hình dữ liệu (`supabase/migrations/<ts>_kb_schema.sql`)

Đây là đặc tả cột/ràng buộc; P2-02 có thể thêm cột nhưng **không đổi tên** cột đã nêu.

```sql
create schema if not exists knowledge;

create table knowledge.corpus_versions (
  version text primary key check (version ~ '^kb-[0-9]{8}-[0-9]{2}$'),
  status text not null check (status in ('building','validated','published','retired')),
  embedding_model text not null,
  embedding_dims integer not null check (embedding_dims = 1024),
  manifest_sha256 text not null check (manifest_sha256 ~ '^[0-9a-f]{64}$'),
  builder text not null,
  stats jsonb not null default '{}'::jsonb,
  notes text not null default '',
  created_at timestamptz not null default now(),
  validated_at timestamptz, published_at timestamptz, retired_at timestamptz
);
create unique index corpus_one_published on knowledge.corpus_versions ((status)) where status = 'published';

create table knowledge.sources (
  source_id text primary key check (source_id ~ '^[a-z0-9][a-z0-9-]{2,63}$'),
  kind text not null check (kind in ('law','guideline','report','factsheet','hotline','authored')),
  publisher text not null, title text not null, url text,
  language text not null, country_scope text[] not null check (cardinality(country_scope) > 0),
  authority_tier smallint not null check (authority_tier between 1 and 4),
  licence_class text not null check (licence_class in ('open_reuse','authored','reference_only')),
  licence_note text not null, licence_quote text,
  verified_on date not null, retrieved_on date,
  unique (source_id, licence_class)
);

create table knowledge.documents (
  corpus_version text not null references knowledge.corpus_versions(version) on delete cascade,
  document_id text not null check (document_id ~ '^[a-z0-9][a-z0-9._:-]{2,95}$'),
  source_id text not null,
  source_licence_class text not null,                                              -- bản sao hạng giấy phép của nguồn
  licence_class text not null check (licence_class in ('open_reuse','authored')),  -- hạng của CHÍNH nội dung tài liệu
  check (licence_class = 'authored' or source_licence_class = 'open_reuse'),
  title text not null, language text not null, country_scope text[] not null,
  topics text[] not null default '{}', age_bands text[] not null default '{}',   -- rỗng = mọi độ tuổi
  published_at date, last_reviewed date not null, applicability text not null,
  primary_url text, derived_from jsonb not null default '[]'::jsonb,              -- [{sourceId, locator}]
  legacy_article_id text, content_sha256 text not null,
  primary key (corpus_version, document_id),
  foreign key (source_id, source_licence_class) references knowledge.sources(source_id, licence_class)
);

create table knowledge.chunks (
  corpus_version text not null, document_id text not null,
  chunk_id text not null, ordinal integer not null check (ordinal >= 0),
  heading text not null default '', section_path text[] not null default '{}',
  text text not null check (length(text) between 40 and 2000),
  heading_norm text generated always as (knowledge.f_unaccent(heading)) stored,
  fts tsvector generated always as (to_tsvector('simple', knowledge.f_unaccent(heading || ' ' || text))) stored,
  embedding extensions.vector(1024) not null,
  char_start integer, char_end integer, token_estimate integer not null,
  content_sha256 text not null, parser text not null, oversize boolean not null default false,
  primary key (corpus_version, chunk_id),
  unique (corpus_version, document_id, ordinal),
  foreign key (corpus_version, document_id) references knowledge.documents(corpus_version, document_id) on delete cascade
);
create index chunks_fts on knowledge.chunks using gin (fts);

create table knowledge.ingestion_runs (
  id uuid primary key default gen_random_uuid(),
  corpus_version text not null references knowledge.corpus_versions(version) on delete cascade,
  command text not null check (command in ('store','validate','publish','rollback')),
  status text not null check (status in ('started','succeeded','failed')),
  detail jsonb not null default '{}'::jsonb,   -- chỉ số đếm, KHÔNG chứa văn bản
  git_commit text, started_at timestamptz not null default now(), finished_at timestamptz
);
```

**Ràng buộc then chốt:** `documents.licence_class` chỉ nhận `open_reuse` hoặc `authored`; ràng buộc `check (licence_class = 'authored' or source_licence_class = 'open_reuse')` cùng khóa ngoại phức hợp `(source_id, source_licence_class)` khiến DB **từ chối** mọi tài liệu mang nguyên văn từ nguồn `reference_only`, trong khi thẻ **tự biên soạn** vẫn được dẫn nguồn `reference_only` làm gốc. `unverified` không bao giờ có trong DB. `heading_norm`/`fts` là cột sinh từ `knowledge.f_unaccent` (IMMUTABLE).

**RLS/grant:** mọi bảng bật RLS. `corpus_versions`: policy `read_published` cho `authenticated` với `status='published'`. `sources`: `read_all` (không phải dữ liệu nhạy cảm; trừ cột `licence_note` — view `knowledge.public_sources` chỉ lộ cột công khai và là `security_invoker`). `documents`/`chunks`: `read_published` với `corpus_version = (select version from knowledge.corpus_versions where status='published')`. `ingestion_runs`: policy `no_client_access` `USING (false)` (thỏa kiểm "mỗi bảng có policy"). `anon`: không `USAGE`. Không có `INSERT/UPDATE/DELETE` cho vai trò người dùng. Ghi chỉ qua vai trò quản trị của kết nối ingest.

## 5. Pipeline

```text
Acquire → Validate → Parse → Normalize → Deduplicate → Chunk → Embed → Store → Validate → Publish
```

| Bước | Module (`agent/src/moodprint_agent/knowledge/ingest/…`) | Vào | Ra | Lỗi/retry | Bất biến |
|---|---|---|---|---|---|
| **Plan** | `manifest.py` | `corpus/manifest.toml` + `sources/*.toml` | `ManifestPlan` (số nguồn theo hạng, ước tính token/chi phí) | lỗi schema → dừng | `manifest_sha256` = sha256 JSON chuẩn hóa của manifest + sha từng file nguồn/thẻ + tham số chunk/parser |
| **Acquire** | `acquire.py` | `SourceSpec.acquire` (URL, loại) | `RawSnapshot(source_id, url, fetched_at, sha256, bytes_path, http_meta)` trong `.local/corpus-cache/` | 429/5xx/timeout: 3 lần, backoff mũ + jitter, `Retry-After`; 4xx khác: không retry; robots cấm: bỏ qua nguồn và ghi báo cáo | allow-list host, chỉ HTTPS, giải DNS → từ chối IP riêng/loopback/link-local (SSRF), redirect chỉ trong allow-list, ≤ 15 MB, ≥ 1 s giữa hai yêu cầu cùng host |
| **Validate** | `validate.py` | `RawSnapshot` + `SourceSpec` | `ValidatedSnapshot` | thất bại → nguồn bị loại khỏi build, ghi lý do | `licence_class ∈ {open_reuse, authored}`; MIME khớp magic bytes; `sha256` khớp giá trị ghim (nếu có) |
| **Parse** | `parse/{html,pdf,markdown,text}.py` | `ValidatedSnapshot` / thẻ `.md` | `ParsedDocument(blocks: list[Block(kind, text, level, page)], meta)` | parse lỗi → loại tài liệu, ghi `parser_error` | PDF: tỉ lệ ký tự thay thế (U+FFFD) ≤ 0.5%; HTML: bỏ nav/footer/script/cookie banner |
| **Normalize** | `normalize.py` | `ParsedDocument` | `NormalizedDocument` (offset ký tự ổn định) | — | **NFC**; bỏ zero-width/điều khiển; gộp khoảng trắng; nối từ ngắt dòng PDF; giữ nguyên dấu thanh; không dịch |
| **Deduplicate** | `dedupe.py` | tập `NormalizedDocument` | tập đã khử trùng + `duplicate_of` | — | trùng chính xác theo sha256; gần trùng Jaccard 5-shingle ≥ 0.90 giữ bản `authority_tier` thấp số hơn (mạnh hơn) |
| **Chunk** | `chunk.py` | `NormalizedDocument` | `Chunk[]` | — | §6 |
| **Embed** | `embed.py` | `Chunk[]` | `Embedded(chunk_id, vector[1024])` | theo `02` P2-06; tiếp tục theo lô nhờ cache | `input_type="document"`; mô hình/dims ghi vào phiên bản |
| **Store** | `store.py` | `Embedded[]` + metadata | `corpus_versions(status='building')` + `sources/documents/chunks` | lô ≤ 200 chunk/transaction; lỗi giữa chừng: chạy lại tiếp tục (idempotent) | `ON CONFLICT DO NOTHING` + đối chiếu đếm; không chạm bản `published` |
| **Validate (DB)** | `verify.py` | phiên bản `building` | `validated` | vi phạm bất biến → giữ `building`, in danh sách lỗi (không in văn bản) | §7 |
| **Publish** | `publish.py` | phiên bản `validated` | `published` (bản cũ → `retired`) | khóa `FOR UPDATE`; một transaction | luôn đúng một bản `published` |

### 5.1 Cấu trúc dữ liệu chính (`models.py`, Pydantic frozen)

```python
class SourceSpec: source_id; kind; publisher; title; url|None; language; country_scope; authority_tier;
                  licence_class; licence_note; licence_quote|None; verified_on; retrieved_on|None;
                  acquire: AcquireSpec|None        # None cho authored / reference_only
class DocumentSpec: document_id; source_id; title; topics; age_bands; published_at|None;
                    last_reviewed; applicability; derived_from: list[DerivedFrom]; legacy_article_id|None
class Chunk: chunk_id; document_id; ordinal; heading; section_path; text; char_start; char_end;
             token_estimate; content_sha256; parser; oversize
class CorpusManifest: version_label; sources: list[SourceSpec]; documents: list[DocumentSpec]; params: ChunkParams
```

### 5.2 Manifest (TOML)

`agent/ingestion/corpus/manifest.toml` liệt kê `[[document]]` (id, source, đường dẫn thẻ `.md` hoặc `snapshot`), tham số chunk và danh sách **loại trừ có lý do** (ví dụ bài `format=scenario` vì tương tác). `sources/<id>.toml` chứa metadata + `[acquire]` (URL, `allow_hosts`, `expected_sha256` tùy chọn). TOML được đọc bằng `tomllib` (stdlib), không thêm phụ thuộc.

## 6. Chunking

| Quy tắc | Giá trị |
|---|---|
| Đơn vị | Heading + đoạn; không cắt giữa câu, mục danh sách, hoặc Điều/Khoản |
| Kích thước mục tiêu | 600–1100 ký tự (≈ 150–350 token tiếng Việt); tối đa 1400; ngoại lệ `oversize=true` tối đa 1800 |
| Tối thiểu | 200 ký tự, trừ mục ngắn có chủ đích (ví dụ số đường dây) ≥ 40 |
| Chồng lấn | 1 câu cuối chunk trước lặp ở đầu chunk sau (trừ ranh giới Điều) |
| Văn bản luật | chia theo `Điều`, gom `Khoản` ngắn; `section_path = ["Chương …","Điều N"]` |
| ID | `chunk_id = <document_id>#<ordinal:03d>-<sha8(text)>` |
| Ước lượng token | `ceil(len(text) / 3.0)` (bảo thủ cho tiếng Việt); chỉ để chia lô, không dùng để tính tiền |
| Tách câu | quy tắc tiếng Việt: không tách sau viết tắt `TP.`, `Q.`, `P.`, `ThS.`, số thứ tự `1.`; tách sau `. ! ?` + khoảng trắng + chữ hoa |

## 7. CLI

Chạy từ repo root: `uv run python -m moodprint_agent.knowledge.ingest <lệnh>`.

| Lệnh | Tác dụng | Ghi chú |
|---|---|---|
| `plan --manifest M` | Kiểm manifest, in số nguồn theo hạng, ước tính token/chi phí, danh sách bị loại | Không mạng, không DB |
| `acquire --manifest M [--only ID] [--offline]` | Tải nguồn `open_reuse` có `[acquire]` vào cache | `--offline` chỉ dùng cache |
| `build --manifest M --out DIR` | validate→parse→normalize→dedupe→chunk; ghi `documents.jsonl`, `chunks.jsonl`, `report.json` | Tất định: hai lần chạy cho cùng `manifest_sha256` và byte-identical |
| `embed --build DIR [--embedder voyage\|hashing] [--budget-tokens N]` | Nhúng, ghi `vectors.f32` + `embed.json` (model, dims, token, chi phí) | Cần `.local/eval-budget.json` cho `voyage` |
| `store --build DIR --target test-env [--version V]` | Ghi vào DB cục bộ, `status=building` | Chỉ loopback; không có `hosted` |
| `validate --target test-env --version V` | Kiểm bất biến → `validated` | |
| `publish --target test-env --version V` | Đổi con trỏ `published` | |
| `rollback --target test-env --to V` | Bản `retired` → `published` | |
| `status --target test-env` | In các phiên bản, trạng thái, số đếm | |
| `verify-citations --target test-env --version V [--link-check]` | Kiểm citation (xem `02` P2-07) | |
| `seed-synthetic --target test-env` | Nạp corpus tổng hợp bằng `HashingEmbedder` và publish | Dùng cho contract test và E2E (hook `knowledge-seed`) |

Hosted: integrator chạy `scripts/db/publish_corpus.py` (INT-08), bọc cùng thư viện (`store_to_engine`, `validate_in_engine`, `publish_in_engine`) sau `validate_hosted_target` của `scripts/db/safety.py`.

Mã thoát: `0` thành công; `1` lỗi dữ liệu/bất biến; `2` lệnh không tồn tại hoặc thiếu điều kiện (dùng bởi hook `optional`); `3` bị chặn bởi ngân sách/giấy phép.

### 7.1 Bất biến `validate`

(1) `documents`/`chunks` khớp `report.json`; (2) 0 embedding NULL, mọi vector 1024 chiều, độ dài L2 ∈ [0.999, 1.001]; (3) `fts` không rỗng cho mọi chunk; (4) FK nguyên vẹn; (5) mọi `documents.licence_class ∈ {open_reuse, authored}`; tài liệu `open_reuse` có nguồn `open_reuse` và `licence_quote`; tài liệu `authored` có `derived_from` không rỗng, mỗi phần tử trỏ `source_id` tồn tại với `verified_on` không rỗng; (6) mọi tài liệu có `last_reviewed ≤ hôm nay` và `applicability` không rỗng; (7) mọi `topics` ∈ danh sách §3.1; (8) coverage: mỗi chủ đề lõi ≥ 3 tài liệu (cảnh báo nếu thấp hơn, lỗi nếu 0); (9) không URL ngoài allow-list manifest; (10) không chuỗi giống email/số điện thoại cá nhân trong `text` (regex; ngoại lệ whitelist `111`, `113`, `115` đã xác minh).

## 8. Phiên bản, provenance, tái lập

- **Nhãn** `kb-YYYYMMDD-NN`. Mỗi phiên bản lưu `embedding_model`, `embedding_dims`, `manifest_sha256`, `builder` (git commit), `stats`.
- **Chunk provenance:** `corpus_version`, `document_id`, `source_id` (qua document), `section_path`, `char_start/end` (trong văn bản đã chuẩn hóa), `content_sha256`, `parser`, `snapshot_sha256` (ghi trong `report.json`, không trong DB), `derived_from` (thẻ biên soạn).
- **Rollback** là đổi con trỏ; không xóa dữ liệu. Giữ tối đa 3 bản `retired`; xóa cũ hơn bằng lệnh `prune` (quản trị, có xác nhận) — không thuộc tập lệnh mặc định.
- **Tái lập:** `report.json` lưu phiên bản `httpx`, `pypdf`, `beautifulsoup4`, `lxml`, Python; cùng đầu vào + cùng cache ⇒ cùng `chunks.jsonl`. Vector Voyage có thể sai khác rất nhỏ giữa các lần gọi; do đó chỉ so `chunks.jsonl`, và so vector bằng cosine ≥ 0.9999 khi kiểm lại.
- **Cập nhật nội dung:** thay đổi nguồn/thẻ ⇒ `manifest_sha256` mới ⇒ phiên bản mới. Không sửa phiên bản đã `published`.

## 9. Thẻ biên soạn (`agent/ingestion/authored/<document_id>.md`)

```markdown
+++
document_id = "vi-cyber-luu-bang-chung"
title = "Lưu lại bằng chứng khi bị quấy rối trên mạng"
source_id = "mp-authored"
language = "vi"
country_scope = ["VN"]
topics = ["cyber", "evidence"]
age_bands = ["11-13", "14-17"]
last_reviewed = 2026-11-12
applicability = "Tóm tắt biên soạn của MoodPrint cho học sinh tại Việt Nam; không thay thế tư vấn pháp lý."
legacy_article_id = ""            # id bài tĩnh ở frontend nếu có
primary_url = "https://…"         # nguồn gốc chính có thể kiểm chứng
[[derived_from]]
source_id = "stopbullying-report-cyber"
locator = "mục 'Document and report cyberbullying'"
+++
## Chụp lại trước khi xóa
…
```

Quy tắc: văn phong ngắn, dễ hiểu theo độ tuổi; không chẩn đoán; không hứa hẹn kết quả; không khuyên đối đầu hay tự điều tra; luôn nhắc người lớn đáng tin; khẳng định pháp lý phải có `locator` tới điều khoản; câu số liệu phải có nguồn và năm. `_review/<document_id>.md` ghi bảng "khẳng định → nguồn → xác nhận".

Trích dẫn khi truy hồi chunk của thẻ biên soạn (hợp đồng `SourceCitation` không đổi): `source_id` = nguồn gốc chính của thẻ (thật), `document_id` = id thẻ, `title` = tiêu đề thẻ, `publisher` = `"MoodPrint biên soạn — dựa trên <nhà xuất bản nguồn gốc>"`, `url` = `primary_url`, `applicability` nêu rõ "tóm tắt biên soạn". Khi nguồn gốc là `reference_only`, `source_id` trỏ tới bản ghi `sources` hạng `reference_only` (được phép tồn tại trong DB cho mục đích trích dẫn, không có chunk nào mang `licence_class = reference_only`).

## 10. Chi phí và an toàn khi chạy

| Hạng mục | Ước tính | Kiểm soát |
|---|---|---|
| Nhúng toàn corpus (≈ 400–1 500 chunk × ≈ 300 token) | < 0.5M token mỗi lần build ≈ **0.03 USD** ở `voyage-4` (0.06 USD/M token) và nằm trong 200M token miễn phí của tài khoản | `--budget-tokens`; cache theo `(model, dims, input_type, sha256)` |
| Benchmark (180 truy vấn × 4 cấu hình × vài lần) | < 0.05M token | harness đếm `usage.total_tokens` |
| Rerank thử nghiệm (nếu bật) | `rerank-3` 0.05 USD/M token; ước tính ≤ 0.02M token/lần chạy | chỉ khi so sánh D |
| Dữ liệu gửi Voyage | **văn bản công khai/biên soạn** khi ingest; **truy vấn học sinh** khi chạy thật | Xem `04` §6 và quyết định opt-out O-06 |

Con số trên là **ước tính dựa trên bảng giá Voyage công bố** (ghi trong báo cáo cùng ngày đọc), không phải số đo; báo cáo Phase 2 ghi số token và chi phí thực.

## 11. Checklist nghiệm thu corpus

- [ ] `SOURCE-REGISTER.md` có ≥ 12 nguồn đã chấm, ≥ 6 vào corpus, tất cả `verified_on` có bằng chứng.
- [ ] Không tài liệu `reference_only`/`unverified` nào có chunk.
- [ ] Ma trận §3.1 đạt; khoảng trống được nêu.
- [ ] `build` hai lần cho cùng `chunks.jsonl`.
- [ ] `validate` xanh; `verify-citations` xanh; `publish` rồi `rollback` rồi `publish` lại đều đúng.
- [ ] `grep` kiểm: không tên người thật, không số điện thoại cá nhân, không secret.
