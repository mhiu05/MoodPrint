# 03 — Embedding nhật ký và truy xuất lai có trích dẫn

Phạm vi: yêu cầu 4 (phần embedding, truy xuất, công tắc, backfill, xóa/sửa). Task JI-20…JI-25. Schema phần memory tự động cũng nằm trong 0029 (JI-20) nhưng logic ở [04](04-auto-memory.md).

## Hiện trạng (đã đọc code)

| Thành phần | Vị trí | Ghi chú |
| --- | --- | --- |
| Tool `search_journal_entries` | `backend/app/ai/runtime.py:507-543`, đăng ký `:561-572` | Chỉ cấp cho `caps(bot).journal` (`nhatky`, `nhip`); bị chặn khi có `mood_scope` hoặc `journal_read_allowed=False`. Owner lock + `assert_purpose(AI)` + `data_version`; stamp `JOURNAL_TURN_POLICY` trước khi văn bản tới model |
| Truy vấn | `backend/app/modules/journal/ai.py:31-88` | `icontains` literal; `limit ≤ 5`; ≤ 90 ngày; snippet 1.000 ký tự; ngân sách 24.000 byte; `coverage.completeHistory=False` |
| Bằng chứng | `backend/app/ai/journal.py` | `JournalEvidence` (owner/run/data_version/hạn), `_render_journal` chỉ chấp nhận `source_entry_ids` ⊆ nguồn đã trả, backend tự dựng link `/self/entry/{id}`; `assert_journal_revisions` kiểm revision dưới owner lock lúc publish |
| Prompt | `journal.py:85-104` | Cấm "embeddings or automatic memories", phải đổi có chủ đích (JI-23) |
| Embedding memory | `backend/app/ai/embeddings.py`, `embedding_models.py`, `voyage.py` | Mẫu cần tái dùng: job có lease + `SKIP LOCKED`, khóa owner → job, fence lúc publish, cosine chính xác không ANN (`embeddings.py:639-643`), `lexical_rank` fallback |
| Voyage adapter | `voyage.py:31-38` | Từ chối input > 8.000 ký tự; entry cho phép 10.000 (`journal/models.py` CHECK) |
| Worker nền | `backend/app/main.py:133-143,226-233` | `embedding_pass` mỗi 1 s trong lifespan API, độc lập cờ |
| Đường xóa entry | `journal/service.py:85-98` (`delete_entries`, `purge_owned_journal`) | Được gọi từ: route DELETE (`journal/routes.py:176-195`), retention (`jobs/retention.py:112-125`), xóa theo phạm vi/tài khoản (`users/lifecycle.py:110-111`), guest (`guests/lifecycle.py:282`). Xóa **cứng** |
| Sửa entry | `journal/routes.py:142-170` | `version += 1`, `user.data_version += 1`; có thể chuyển `saved → draft` (`JournalEntryEdit.status`) |

**Tái dùng `EmbeddingJob`?** Không tái dùng bảng. `memory_embedding_jobs` có `memory_id` NOT NULL FK, snapshot theo phiên bản consent MEM và CHECK bot (`embedding_models.py:42-85`). Nhét entry vào đó phải làm `memory_id` nullable và đổi unique constraint đang được dùng trong `ON CONFLICT`, tức phá bất biến đã test. Kế hoạch tái dùng **mẫu code** (lease/fence/backoff), `VoyageProvider`, `validate_vector`, `Vector` type và `lexical_rank`, với bảng job riêng.

## Thiết kế

```text
POST/PUT /journal/entries ──(cùng transaction)──► xóa vector cũ, hủy job cũ, enqueue job(kind=embed|memories, entry_version)
                                                    available_at = now + debounce
worker (lifespan API, mỗi 1 s) ─► claim job (SKIP LOCKED) ─► khóa owner → job, kiểm quyền+revision ─► nhả khóa
                               ─► Voyage document embed (không giữ khóa) ─► khóa owner → job, kiểm lại ─► upsert vector
search_journal_entries ─► (không khóa) đọc quyền nhanh, embed query ≤ 3 s ─► (owner lock) semantic ∪ keyword ∪ recent
                       ─► JournalEvidence như cũ ─► _render_journal như cũ
DELETE entry / retention / xóa tài khoản ─► FK ON DELETE CASCADE xóa vector + job + memory tự động
```

### Migration `0029_journal_intelligence` (JI-20)

`down_revision = "0028_collaboration_defaults"`. Expand-only. Mọi bảng mới dùng helper bảo mật theo mẫu `0024_three_agent_groups.py:45-65`: `ENABLE ROW LEVEL SECURITY`, `REVOKE ALL … FROM PUBLIC` và role client, `GRANT SELECT,INSERT,UPDATE,DELETE … TO moodprint_runtime`. Không dùng `format()` có `%` (offline SQL nhân đôi `%%`, ghi chú bộ nhớ dự án); dùng `quote_ident` như 0024.

1. **`journal_ai_settings`**: `user_id uuid PK FK users ON DELETE CASCADE`, `embedding_enabled bool NOT NULL DEFAULT true`, `auto_memory_enabled bool NOT NULL DEFAULT true`, `notice_version varchar(32) NOT NULL DEFAULT 'journal-ai-v1'`, `version int NOT NULL DEFAULT 1 CHECK (version >= 1)`, `updated_at timestamptz NOT NULL DEFAULT clock_timestamp()`. **Không có hàng = mặc định bật** (OD-04). Tách khỏi `ai_preferences` vì `ai_preferences.version` nằm trong snapshot embedding memory (`embeddings.py:95-102`): đổi công tắc nhật ký ở đó sẽ làm mọi vector memory thành cũ và gửi lại Voyage.
2. **`journal_entry_embeddings`**: `id uuid PK`, `entry_id uuid NOT NULL FK journal_entries ON DELETE CASCADE`, `user_id uuid NOT NULL FK users ON DELETE CASCADE`, `entry_version int NOT NULL`, `settings_version int NOT NULL`, `content_sha256 char(64) NOT NULL`, `model varchar(100) NOT NULL`, `dimensions int NOT NULL`, `embedding extensions.vector NOT NULL`, `created_at timestamptz NOT NULL DEFAULT clock_timestamp()`. `UNIQUE (entry_id, model, dimensions)`; `INDEX (user_id, model, dimensions)`; `CHECK (dimensions in (256,512,1024,2048) and extensions.vector_dims(embedding) = dimensions)`. **Không có HNSW**: tập mỗi người ≤ 90 ngày entry, cosine chính xác sau bộ lọc owner rẻ và không bao giờ lọc mất kết quả hợp lệ (cùng lý do `embeddings.py:639-640`).
3. **`journal_ai_jobs`**: `id uuid PK`, `entry_id uuid NOT NULL FK journal_entries ON DELETE CASCADE`, `user_id uuid NOT NULL FK users ON DELETE CASCADE`, `kind varchar(16) NOT NULL CHECK (kind in ('embed','memories'))`, `entry_version int NOT NULL`, `settings_version int NOT NULL`, `model varchar(100) NOT NULL`, `dimensions int NULL` (`NULL` ⇔ `kind='memories'`), `status varchar(16) NOT NULL DEFAULT 'pending' CHECK (status in ('pending','running','retry','succeeded','cancelled','failed','skipped'))`, `attempts int NOT NULL DEFAULT 0 CHECK (attempts between 0 and 8)`, `available_at`, `lease_until`, `lease_token uuid`, `last_error varchar(48)`, `run_id uuid NULL FK ai_runs ON DELETE SET NULL` (chỉ `memories`), `created_at`. `UNIQUE (entry_id, kind, entry_version, settings_version, model)`; `INDEX (status, available_at, lease_until)`; `INDEX (user_id, kind, created_at)` để đếm cap/ngày.
4. **`memories`** (cho 04): `ADD origin varchar(16) NOT NULL DEFAULT 'approved'`, `ADD source_entry_id uuid NULL REFERENCES journal_entries(id) ON DELETE CASCADE`, `ADD source_entry_version int NULL`, `ALTER proposal_id DROP NOT NULL`. `CHECK memories_origin` (thêm `NOT VALID` rồi `VALIDATE`): `(origin='approved' AND proposal_id IS NOT NULL AND source_entry_id IS NULL) OR (origin='journal_auto' AND proposal_id IS NULL AND source_entry_id IS NOT NULL AND source_entry_version >= 1)`. Partial index `ix_memories_source_entry (source_entry_id) WHERE source_entry_id IS NOT NULL`. Partial unique `uq_memories_auto_text (source_entry_id, source_entry_version, md5(text)) WHERE origin='journal_auto' AND status='active'` để retry không tạo trùng.
5. **`ai_runs`**: thay CHECK `origin` thành `origin in ('user','proactive','collaboration','agent','journal')` (drop + add `NOT VALID` + `VALIDATE`). Các CHECK `parent`, `slot`, `conversation` giữ nguyên; run `journal` có `conversation_id NULL`, `parent_run_id NULL`, `proactive_slot NULL`.

`downgrade()`: raise nếu tồn tại `memories.origin='journal_auto'` hoặc `ai_runs.origin='journal'` (theo tiền lệ 0028 chỉ downgrade khi không có dữ liệu mới); ngược lại drop theo thứ tự ngược. Rollback vận hành **không** dùng downgrade mà dùng image tương thích (06).

ORM: `JournalAiSettings`, `JournalEntryEmbedding`, `JournalAiJob` trong `backend/app/modules/journal/ai_models.py` (mới). `Memory` thêm 3 cột (`infrastructure/database/models.py:152-161`). CHECK `AiRun` (`models.py:218`). `READY_REVISIONS = ("0029_journal_intelligence",)` (`core/revisions.py`), cập nhật docstring.

### Setting mới (`EmbeddingSettings`, `backend/app/ai/embedding_config.py`)

| Setting | Mặc định | Biên | Ý nghĩa |
| --- | --- | --- | --- |
| `journal_semantic_enabled` | `true` | bool | Capability; còn cần `VOYAGE_API_KEY` (`journal_semantic_available`). Field + property đã thêm ở JI-01 |
| `journal_embedding_debounce_seconds` | 20 | 5–300 | Trễ trước khi embed, gom các lần sửa liên tiếp |
| `journal_embedding_daily_cap_per_user` | 200 | 10–1000 | Số document embed thành công/người/ngày; vượt thì **hoãn** tới ngày sau, không bỏ |
| `journal_query_timeout_seconds` | 3 | 1–5 | Trần thời gian embed truy vấn trong lượt chat |
| `journal_semantic_top_k` | 6 | 1–8 | Số entry ngữ nghĩa tối đa |
| `journal_recent_k` | 2 | 0–5 | Số entry gần nhất luôn kèm theo |
| `journal_similarity_threshold` | 0.25 | 0–1 | Ngưỡng cosine (distance ≤ 1 − ngưỡng) |
| `journal_document_char_limit` | 7000 | 1000–7900 | Cắt văn bản entry trước khi embed (adapter chặn 8.000) |

### Văn bản được embed

Ruling về trần adapter: 24 tag hợp lệ (mỗi tag 60 ký tự) cộng text 7.000 có thể
vượt 8.000 ký tự. `journal_document` giữ metadata giới hạn hợp lệ và cắt phần text
theo cả `journal_document_char_limit` lẫn ngân sách còn lại của toàn document
8.000 ký tự. Không gửi ID/media/timezone; hash tính trên đúng document đã cắt.

Ruling về cap: đếm job succeeded không bền vì FK cascade xóa job cùng entry.
Dùng receipt nội bộ content-free `journal:embed-usage` trong `idempotency_keys`,
khóa theo owner, reserve trước provider cho mọi ngày local có thể hoàn tất trong
lease (kể cả qua nửa đêm). Thành công giữ charge dù entry/job đã bị xóa; thất bại
rõ ràng refund, crash chưa biết giữ reservation bảo thủ. Receipt quota giữ 72h,
độc lập receipt API 24h; account deletion xóa receipt quota, settlement không tạo
lại. Không thêm bảng/cột ngoài schema 0029. Backfill lọc đủ bằng chứng tuổi trước
LIMIT, rồi kiểm lại quyền dưới owner lock để tránh batch legacy không hợp lệ làm
kẹt người dùng khác.

`journal_document(entry) -> str`: `"Ngày {local_date:%d/%m/%Y}. Tâm trạng {mood}/5.\nCảm xúc: {', '.join(emotions)}\nYếu tố: {', '.join(factors)}\n\n{text[:journal_document_char_limit]}"`. Không có ID, timezone hay media. `content_sha256 = sha256(document.encode())`. Entry `draft` không bao giờ được embed. Entry `saved` có text rỗng vẫn được embed nếu có emotions/factors. Entry > 7.000 ký tự bị cắt, ghi trong `coverage` (`snippetTruncated` đã có); chunking để sau demo.

### Quy tắc enqueue / hủy hiệu lực (đúng–sai, có test)

| Sự kiện | Trong **cùng** transaction của route | Kết quả |
| --- | --- | --- |
| Tạo entry `saved` | enqueue `embed` + `memories` (`available_at = now + debounce`) | |
| Sửa entry (bất kỳ field) | `DELETE journal_entry_embeddings WHERE entry_id`; `UPDATE journal_ai_jobs SET status='cancelled' WHERE entry_id AND status IN (pending,retry,running)`; xóa memory tự động **chưa sửa** của entry (04); nếu vẫn `saved` thì enqueue cho revision mới | Không còn vector của revision cũ dù chỉ một khoảnh khắc |
| Chuyển `saved → draft` | như trên, không enqueue | |
| Xóa entry (mọi đường) | FK `ON DELETE CASCADE` | vector, job, memory tự động (và `memory_embeddings`/`memory_embedding_jobs` của nó qua cascade sẵn có) biến mất |
| Tắt `embedding_enabled` | `DELETE journal_entry_embeddings WHERE user_id`; hủy job `embed`; `version += 1`; `user.data_version += 1`; hủy run đang chạy (giống `chat_routes.py:184-188`) | Truy xuất rơi về từ khóa + gần nhất |
| Bật lại | `version += 1` | reconcile backfill |
| Xóa tài khoản / scope `all_private` | `purge_owned_journal` cascade; thêm `DELETE journal_ai_settings` trong `users/lifecycle.py:91-103` và `guests/lifecycle.py` | |
| Đổi `VOYAGE_MODEL`/`VOYAGE_DIMENSIONS` | worker hủy job khác cấu hình; truy xuất lọc theo model/dims; publish xóa vector khác cấu hình của cùng entry | Không bao giờ trộn không gian vector |
| Worker publish | dưới owner lock → job: lease token khớp, `job.entry_version == entry.version`, `entry.status='saved'`, `settings_version` hiện hành, người dùng còn đủ điều kiện | Nếu không: `cancelled`, không ghi vector |

Ai được embed: `account_kind='registered'`, `status='active'`, không `deletion_pending`, `is_adult_eligible`, AI consent bật (`consent_enabled`), `journal_ai_settings.embedding_enabled` (không có hàng = true), `settings.journal_semantic_available`. Guest bị loại (OD-06).

### Truy xuất lai (JI-23)

`hybrid_search(db, user, args, *, query_vector, settings, reason) -> dict` (chữ ký đầy đủ ở Interfaces của JI-23) trong `backend/app/modules/journal/retrieval.py` (mới); `search_for_ai` thành wrapper gọi nó với `query_vector=None` để giữ chữ ký cũ cho caller khác.

1. Cửa sổ ngày như cũ: mặc định 90 ngày, `from/to` ≤ 90 ngày. Lý do không nới: retention xóa entry > 89 ngày (`jobs/retention.py:112-125`), nên nới cửa sổ không có dữ liệu để đọc (OD-05).
2. `semantic`: nếu có `query_vector`, top `journal_semantic_top_k` theo `embedding <=> :vector` trong join `journal_entries` với `version = entry_version`, `status='saved'`, cùng owner, trong cửa sổ, đúng model/dims, distance ≤ 1 − ngưỡng.
3. `keyword`: nếu `query` khác rỗng, truy vấn `icontains` hiện tại (giữ `autoescape=True`).
4. `recent`: `journal_recent_k` entry mới nhất trong cửa sổ.
5. Hợp nhất theo thứ tự semantic (distance tăng) → keyword (ngày giảm) → recent; bỏ trùng theo `id`; cắt `args.limit` (mặc định **6**, tối đa **8**, trước đây 5) và ngân sách 24.000 byte như cũ.
6. Mỗi entry thêm `"match": "semantic"|"keyword"|"recent"`; `coverage` thêm `"retrieval": {"mode": "hybrid"|"keyword"|"recent", "reason": null|"disabled"|"not_indexed"|"provider_unavailable"|"timeout"}` và `"indexed": <số entry có vector hiện hành trong cửa sổ>`.

Tích hợp tool (`runtime.py:507-543`):
- Trước khối `async with … lock_actor`: nếu `args.query` khác rỗng, đọc nhanh (không khóa) `journal_ai_settings` + điều kiện; nếu được phép, `asyncio.timeout(journal_query_timeout_seconds)` gọi `VoyageProvider.embed(query, "query")`. Lỗi/timeout ⇒ `query_vector=None`, `reason` tương ứng. Lần gọi này tính vào `check_tool` (giới hạn 2 tool call/lượt không đổi).
- Trong khối khóa: đọc lại `journal_ai_settings.version`; khác bản đã đọc ⇒ bỏ vector (`reason="disabled"`).
- Phần còn lại giữ nguyên: stamp `JOURNAL_TURN_POLICY`, `JournalEvidence`, `result["evidence"]`.
- `JournalSearchInput.limit`: `Field(default=6, ge=1, le=8)` (`journal/ai.py:18`). Schema tool đổi nên cập nhật mọi test snapshot của tool schema.

Prompt (`journal.py:85-104`, runtime layer, không đụng persona đóng băng): thay "no drafts, media, legacy mood notes, other users, embeddings or automatic memories" bằng "no drafts, media, legacy mood notes or other users. The tool ranks your saved entries by meaning and keywords; only entries it returns are evidence". Thêm: "Call search_journal_entries before answering what the user wrote; for 'this week' pass from_date/to_date. If coverage.retrieval.mode is not hybrid, results come from keywords/recent entries only." Marker usage `"+j1"` → `"+j2"` (`runtime.py:392`). Persona Nhật ký vẫn nói "hướng dẫn chọn khoảng ngày" (`prompts.py`, V3_PERSONAS); câu runtime mới làm rõ đó là cho **điểm tâm trạng** (mood scope), không đổi cơ chế mood scope.

## JI-20 — Migration 0029 + ORM

**Mục tiêu:** Schema 0029 expand-only cho công tắc, vector, job và memory tự động; image 0028 vẫn chạy được trên nó.

**Files:** Create `backend/alembic/versions/0029_journal_intelligence.py`, `backend/app/modules/journal/ai_models.py`, `backend/tests/test_journal_intelligence_migration.py`. Modify `backend/app/infrastructure/database/models.py:152-161,218`, `backend/app/core/revisions.py`, `docs/supabase/schema.md` (3 bảng + cột mới), `backend/tests/conftest.py` (import model mới để `create_all` có bảng).

**Interfaces:** Produces ORM `JournalAiSettings(user_id, embedding_enabled, auto_memory_enabled, notice_version, version, updated_at)`, `JournalEntryEmbedding(...)`, `JournalAiJob(...)` (tên field = tên cột ở trên); `Memory.origin: str`, `Memory.source_entry_id: UUID | None`, `Memory.source_entry_version: int | None`, `Memory.proposal_id: UUID | None`.

- [ ] **Bước 1: Test đỏ** `test_journal_intelligence_migration.py` theo khuôn `tests/test_v3_migration.py` (tua về 0028, seed, nâng cấp):
  - `test_upgrade_preserves_every_approved_memory`: memory seed trước ⇒ `origin='approved'`, `proposal_id` giữ nguyên.
  - `test_origin_check_rejects_mixed_rows`: 4 dạng sai (approved không proposal; auto không entry; auto có proposal; auto `source_entry_version=0`) đều `IntegrityError`.
  - `test_entry_delete_cascades_vectors_jobs_and_auto_memories`: xóa `journal_entries` ⇒ 0 hàng ở 3 nơi, memory `approved` không bị đụng.
  - `test_ai_runs_accepts_journal_origin_without_conversation`.
  - `test_new_tables_have_rls_and_no_public_grants` (truy `pg_class.relrowsecurity`, `has_table_privilege('public', …)`).
  - `test_downgrade_refuses_when_auto_memories_exist`.
  - `alembic upgrade head` trên DB trắng ⇒ `0029_journal_intelligence (head)`; `alembic check` ⇒ "No new upgrade operations detected".
- [ ] **Bước 2:** `uv run --locked pytest -q tests/test_journal_intelligence_migration.py` → FAIL.
- [ ] **Bước 3:** Viết migration + ORM.
- [ ] **Bước 4:** Chạy lại; chạy `$env:DATABASE_MIGRATION_URL='postgresql+psycopg://…/moodprint_ji_migration_test'; uv run --locked alembic upgrade head; uv run --locked alembic check`; `uv run --locked alembic upgrade 0028_collaboration_defaults:0029_journal_intelligence --sql > $env:TEMP\0029.sql` để xem trước (bản pin chính thức ở JI-50).
- [ ] **Bước 5:** `uv run --locked pytest -q tests/test_memory.py tests/test_embeddings.py tests/test_journal*.py tests/test_v3_migration.py tests/test_collaboration_migration.py tests/test_reviewed_artifacts.py` không có hồi quy.
- [ ] **Bước 6:** Commit `feat(db): 0029 journal intelligence schema (expand-only)`.

**Rủi ro:** `memories.proposal_id` đổi nullable có thể làm code cũ giả định không-null (`MemoryDTO` không lộ field này; `rg "proposal_id" backend/app` để rà). `VALIDATE CONSTRAINT` trên `ai_runs` quét toàn bảng nhưng lock nhẹ (`SHARE UPDATE EXCLUSIVE`); dữ liệu hosted nhỏ. **Rollback:** xem 06 (image tương thích); downgrade chỉ khi chưa có dữ liệu mới.

## JI-21 — Công tắc người dùng, thông báo, API `journal-ai`

Ruling triển khai Windows: hàm thuần dùng `journalAiSettingsModel.ts` thay `journalAiSettings.ts`. Vite/esbuild trên filesystem không phân biệt hoa/thường phân giải nhầm tên chỉ khác case với component `JournalAiSettings.tsx`; browser test đã tái hiện lỗi thiếu export. Component/API giữ nguyên tên.

**Mục tiêu:** Người dùng biết nhật ký được xử lý bởi dịch vụ ngoài và tắt được; số liệu chỉ mục kiểm chứng được.

**Files:** Create `backend/app/modules/journal/ai_settings.py` (router + service), `frontend/src/features/real/journal/JournalAiSettings.tsx`, `frontend/src/features/real/journal/journalAiSettings.ts` (+ `.test.ts`). Modify `backend/app/main.py` (import + thêm router vào vòng `main.py:396-422`), `frontend/src/features/real/RealApp.tsx:2270-2279` (`AccountPage` render `<JournalAiSettings />` giữa `AdultEligibility` và `AccountActions`), `docs/backend/api-reference.md`. Test `backend/tests/test_journal_ai_settings.py`.

**Interfaces:**
- `GET /api/v1/journal/ai-settings` → `JournalAiSettingsView { embeddingEnabled: bool, autoMemoryEnabled: bool, embeddingAvailable: bool, autoMemoryAvailable: bool, noticeVersion: "journal-ai-v1", version: int, indexedEntries: int, pendingEntries: int, autoMemories: int }`.
- `PUT /api/v1/journal/ai-settings` body `JournalAiSettingsInput { embeddingEnabled: bool, autoMemoryEnabled: bool, noticeVersion: Literal["journal-ai-v1"], expectedVersion: int }`, header `Idempotency-Key` + CSRF, operation receipt `"journal:ai-settings"`. `409 STALE_VERSION` khi lệch version. Guest ⇒ `403 REGISTERED_REQUIRED` qua dependency có sẵn `require_registered_actor` (`core/security.py:116-128`). Bật khi `embeddingAvailable=false` vẫn được lưu (ý muốn người dùng) nhưng view trả `embeddingAvailable=false`.
- Produces `journal_ai_allowed(db, user, settings, kind: Literal["embed","memories"]) -> int | None` (trả `settings_version` khi được phép, `None` khi không). JI-22, JI-23, JI-30 dùng hàm này.

- [ ] **Bước 1: Test đỏ** (`clients`, ghim nền + bật `journal_semantic_enabled`, `voyage_api_key` giả):
  - `test_absent_row_means_enabled_and_is_reported_available`.
  - `test_put_is_idempotent_and_versioned` (cùng key ⇒ cùng receipt; key mới + version cũ ⇒ 409).
  - `test_turning_embedding_off_deletes_vectors_cancels_jobs_and_running_turns` (seed 2 vector + 1 job pending + run `running` ⇒ 0 vector, job `cancelled`, run `cancelled`, `data_version` tăng).
  - `test_counts_are_owner_scoped` (actor B không thấy số của A).
  - `test_guest_is_refused`.
  - Frontend `journalAiSettings.test.ts`: `noticeText()` chứa "Voyage AI" và "bên ngoài"; `toggleLabel("embedding") === "Tìm theo ý nghĩa trong nhật ký"`.
- [ ] **Bước 2:** chạy → FAIL.
- [ ] **Bước 3:** Cài đặt. Copy chốt (tiếng Việt):
  - Tiêu đề mục: "Nhật ký và trợ lý AI".
  - Thông báo: "Để trợ lý Nhật ký tìm đúng những trang bạn cần, MoodPrint gửi nội dung các trang nhật ký đã lưu tới Voyage AI, một dịch vụ embedding bên ngoài, để tạo chỉ mục tìm kiếm. Chỉ mục bị xóa khi bạn sửa hoặc xóa trang, khi tắt công tắc này, hoặc khi xóa tài khoản. Bản sao ở nhà cung cấp hoặc bản sao lưu có thể chưa bị xóa ngay."
  - Công tắc 1: "Tìm theo ý nghĩa trong nhật ký"; khi `embeddingAvailable=false`: "Tính năng này chưa sẵn sàng trên máy chủ. Trợ lý vẫn tìm theo từ khóa."
  - Công tắc 2 (04): "Tự ghi nhớ điều quan trọng từ nhật ký". Phụ chú: "Ghi nhớ tự động có nhãn riêng trong mục Ghi nhớ; bạn sửa hoặc xóa được." **Chỉ render khi `autoMemoryAvailable`.** Ở JI-21, server luôn trả `autoMemoryAvailable=false`; JI-30 mới đổi thành `settings.journal_auto_memory_enabled and runtime.available_for(user)`. Nhờ vậy cắt nhóm B không để lại công tắc vô tác dụng.
  - Trạng thái: "Đã lập chỉ mục {indexedEntries} trang · đang chờ {pendingEntries}".
- [ ] **Bước 4:** export OpenAPI + `npm.cmd run contracts:generate`; test pass; `check_docs.py` PASS.
- [ ] **Bước 5:** Commit `feat(journal): user notice and switches for journal AI processing`.

**Rủi ro:** chủ dự án có thể bác bỏ thông báo/công tắc (OD-04). Khi đó chỉ gỡ component frontend; API giữ (rẻ, cần cho kiểm tra demo "xóa entry thì chỉ mục giảm"). **Rollback:** revert; bảng giữ nguyên.

## JI-22 — Enqueue, worker embed, reconcile/backfill

**Mục tiêu:** Mọi entry `saved` đủ điều kiện có vector của đúng revision hiện hành; vector của revision cũ hay entry đã xóa không tồn tại.

**Files:** Create `backend/app/modules/journal/indexing.py`. Modify `backend/app/modules/journal/routes.py:108-195` (create/update/delete gọi hook), `backend/app/main.py:133-143` (thêm `journal_index_pass` vào `embedding_pass` hoặc task riêng cùng nhịp 1 s), `backend/app/modules/users/lifecycle.py:91-103`, `backend/app/modules/guests/lifecycle.py` (xóa `journal_ai_settings`). Modify `backend/tests/fakes.py` (thêm `FakeEmbedder`). Test `backend/tests/test_journal_indexing.py`.

**Interfaces:**
- `async def on_entry_saved(db, user, entry, settings) -> None` và `async def on_entry_changed(db, user, entry, settings) -> None` (gọi trong transaction route, sau `flush`).
- `async def process_journal_jobs(database, settings, *, embedder: EmbeddingProvider | None = None, memory_runner=None) -> int` (một tick có giới hạn `embedding_job_batch_size`; `memory_runner` dùng ở 04).
- `async def reconcile_journal_jobs(database, settings) -> int` (tìm entry `saved` trong 90 ngày, đủ điều kiện, thiếu job hiện hành; tối đa `embedding_job_batch_size`/tick, thứ tự `journal_entries.id`).
- `journal_document(entry) -> str` như trên.
- `tests.fakes.FakeEmbedder(dimensions=1024, synonyms: dict[str, str] = …)`: vector xác định = băm token sau chuẩn hóa NFC/casefold, gộp từ đồng nghĩa (`"kiệt sức"→"mệt"`, `"rã rời"→"mệt"`, `"lo lắng"→"lo"`), chuẩn hóa L2; đếm số lần gọi; có thể cấu hình `delay`/`error`.
- `app.state.journal_embedder` (test-only override, `None` ở prod) được worker lifespan đọc.

- [ ] **Bước 1: Test đỏ** (mỗi test nêu assertion chính):
  - `test_save_enqueues_one_embed_job_after_debounce`: tạo entry ⇒ 1 job `embed` `pending`, `available_at ≥ now + 19 s`; tick trước hạn ⇒ 0 lần gọi embedder.
  - `test_draft_is_never_indexed`.
  - `test_edit_deletes_stale_vector_in_the_same_transaction`: vector rev1 tồn tại; PUT ⇒ trong response transaction, `SELECT` vector = 0; job rev2 pending.
  - `test_rapid_edits_index_only_latest_revision`: 3 PUT liên tiếp ⇒ chỉ job rev4 không bị hủy; tick ⇒ đúng 1 lần gọi embedder, vector `entry_version=4`.
  - `test_every_journal_delete_path_removes_derivatives` (parametrize `route`, `retention`, `scope_journal`, `account`, `guest_purge`): sau mỗi đường, 0 hàng `journal_entry_embeddings`/`journal_ai_jobs` cho entry.
  - `test_delete_during_lease_never_publishes`: `FakeEmbedder(delay=event)`; xóa entry khi đang chờ; thả event ⇒ không có vector, không exception lọt ra worker.
  - `test_settings_off_mid_flight_discards_result`.
  - `test_provider_failure_retries_with_backoff_then_fails`: lỗi 4 lần ⇒ `failed`, `last_error='embedding_provider_unavailable'`, khoảng `available_at` 5/10/20 s.
  - `test_daily_cap_defers_to_next_local_day`.
  - `test_minor_guest_and_deletion_pending_never_enqueued`.
  - `test_reconcile_backfills_existing_entries_in_bounded_batches`: 25 entry cũ, batch 10 ⇒ tick 1: 10 job, tick 3: 25; entry > 89 ngày không được chọn.
  - `test_model_change_cancels_and_reembeds_without_mixing`.
  - `test_document_is_bounded_and_hash_stable`: text 10.000 ký tự ⇒ document ≤ 7.000 + header; cùng entry ⇒ cùng sha.
- [ ] **Bước 2:** `uv run --locked pytest -q tests/test_journal_indexing.py` → FAIL.
- [ ] **Bước 3:** Cài đặt theo mẫu `process_embedding_jobs` (`embeddings.py:394-530`): claim chỉ khóa job → nhả → khóa owner → job (thứ tự owner → job như `embeddings.py:436-439`), đọc document từ entry **hiện hành** ngay trước khi gửi (không dùng bản đã đọc trước khi khóa, như `_document_dispatch`), gửi Voyage không giữ khóa, publish lại dưới owner → job. Log content-free: `journal_index_attempt state=%s attempt=%s error=%s`, `journal_index_queue pending=%d retry=%d failed=%d`.
- [ ] **Bước 4:** chạy lại + `tests/test_journal.py tests/test_journal_contract.py tests/test_privacy_lifecycle.py tests/test_embeddings.py`.
- [ ] **Bước 5:** Commit `feat(journal): background journal indexing with revision fencing`.

**Rủi ro:** worker trong process API dùng chung pool (5+2). Batch 10/tick, mỗi tick tối đa 10 kết nối ngắn tuần tự; đo `metric=db_pool_checked_out` trong JI-50. Voyage giới hạn tốc độ: backoff + cap. **Rollback:** đặt `JOURNAL_SEMANTIC_ENABLED=false` (không cần deploy); revert code nếu cần.

## JI-23 — Truy xuất lai trong tool + prompt

**Mục tiêu:** Nhật ký tìm đúng trang theo ý nghĩa trên toàn cửa sổ 90 ngày, có fallback, giữ nguyên `journal-evidence-v1`.

**Files:** Create `backend/app/modules/journal/retrieval.py`. Modify `backend/app/modules/journal/ai.py:15-88`, `backend/app/ai/runtime.py:507-543,392`, `backend/app/ai/journal.py:85-104`. Test `backend/tests/test_journal_retrieval.py`; cập nhật `backend/tests/test_journal_ai.py`.

**Interfaces:** Consumes `journal_ai_allowed` (JI-21), `JournalEntryEmbedding` (JI-20). Produces `hybrid_search(db, user, args: JournalSearchInput, *, query_vector: list[float] | None, settings, reason: str | None) -> dict` và `async def journal_query_vector(database, settings, actor, query: str, *, embedder=None) -> tuple[list[float] | None, int | None, str | None]` (vector, settings_version đã đọc, reason).

- [ ] **Bước 1: Test đỏ**
  - `test_paraphrase_query_finds_entry_without_substring`: entry "mệt rã rời sau ca đêm", query "kiệt sức" (FakeEmbedder) ⇒ entry trả về với `match="semantic"`; với `journal_semantic_enabled=False` ⇒ không trả.
  - `test_hybrid_always_includes_recent_entries`.
  - `test_query_embedding_timeout_falls_back_within_budget`: `FakeEmbedder(delay=10 s)`, timeout 3 s ⇒ tool trả trong < 3,5 s, `coverage.retrieval == {"mode":"keyword","reason":"timeout"}`, lượt `completed`.
  - `test_unindexed_user_reports_not_indexed`.
  - `test_vector_of_an_older_revision_is_ignored` (chèn tay vector `entry_version` cũ).
  - `test_settings_change_between_vector_and_lock_discards_vector`.
  - `test_limit_defaults_to_6_and_caps_at_8_within_24kb`.
  - `test_citation_must_be_a_returned_entry`: fake model cite một entry tồn tại nhưng không được trả về ⇒ `409 JOURNAL_CITATION_INVALID` (bất biến `journal-evidence-v1` giữ nguyên).
  - `test_refusal_and_mood_scope_still_deny_the_tool` (hai đường cũ: `journal_read_refused`, `mood_scope`).
  - `test_instructions_describe_ranking_and_usage_marker_is_j2`.
- [ ] **Bước 2:** chạy → FAIL.
- [ ] **Bước 3:** Cài đặt (thuật toán ở mục "Truy xuất lai"). Log `metric=journal_retrieval mode=%s semantic=%d keyword=%d recent=%d latency_ms=%d` (không nội dung, không ID).
- [ ] **Bước 4:** chạy + `tests/test_journal_ai.py tests/test_mood_evidence_runtime.py tests/test_scoped_mood_tool.py tests/test_context_selection.py tests/test_sdk_adapter.py tests/test_three_agents.py tests/test_orchestration_sdk.py`.
- [ ] **Bước 5:** Commit `feat(ai): hybrid journal retrieval with keyword and recent fallback`.

**Rủi ro:** câu query do model viết được gửi ra Voyage. Nó được suy ra từ tin nhắn người dùng, tương tự truy vấn memory hiện có (`embeddings.py:624-631`), và nằm dưới cùng công tắc. Thêm một lần gọi Voyage làm tăng độ trễ lượt tối đa 3 s. **Rollback:** `JOURNAL_SEMANTIC_ENABLED=false` ⇒ hành vi = từ khóa + gần nhất (vẫn khác bản cũ ở `limit` 6 và phần recent; muốn y hệt cũ thì revert).

## JI-24 — Đo chất lượng truy xuất (bắt buộc cho demo)

**Mục tiêu:** Có số đo recall/MRR của truy xuất lai so với từ khóa để trình bày ở demo và chặn hồi quy.

**Files:** Create `backend/evals/journal_retrieval/dataset.json`, `backend/evals/journal_retrieval/run.py`, `backend/evals/journal_retrieval/README.md`; test `backend/tests/test_journal_retrieval_eval.py` (chạy bộ dữ liệu với `FakeEmbedder`).

- Dữ liệu tổng hợp tiếng Việt: 40 entry rải 60 ngày của một người dùng giả; 15 truy vấn có nhãn entry liên quan: 5 khớp từ khóa nguyên văn, 6 diễn đạt khác (không có chuỗi con chung), 4 mẫu cảm xúc ("mình hay lo khi nào?"). Không dùng dữ liệu thật.
- `run.py --embedder fake|voyage --out <dir>`: nạp vào DB `_test` disposable, chạy `hybrid_search` ở hai chế độ (`query_vector=None` = baseline từ khóa; có vector = lai), in recall@6, MRR@6, recall@6 riêng nhóm diễn đạt khác, độ trễ p50/p95. `voyage` đòi `VOYAGE_API_KEY` trong env của phiên và cờ `--confirm-cost` (55 lần gọi, vài nghìn token; kiểm bảng giá Voyage trước khi chạy).
- Ngưỡng mục tiêu cho demo (ghi số thật vào ledger, không làm tròn): lai đạt recall@6 nhóm diễn đạt khác ≥ 0,8 và không thấp hơn baseline ở nhóm từ khóa. Không đạt thì ghi rõ, chỉnh `journal_similarity_threshold`/`top_k` một lần rồi đo lại; không chỉnh theo từng truy vấn.
- Test CI `test_journal_retrieval_eval.py`: với `FakeEmbedder`, lai ≥ baseline ở mọi nhóm, và nhóm diễn đạt khác của baseline < lai (chứng minh pipeline, không phải chất lượng Voyage).

## JI-25 (cắt được, nhóm B) — Hybrid cho consult của Điều phối

**Mục tiêu:** Consult Nhật ký của Điều phối chọn trang liên quan nhất trong cửa sổ đã cho phép.

`orchestration/workflow.py:163-183` `journal_excerpts(db, user, days)` → thêm `query_vector: list[float] | None = None`; vector tính trong `Workflow.decide` **trước** `open_step` (không giữ khóa). Giữ trần `days ≤ 14`, `JOURNAL_EXCERPTS = 5`, `EXCERPT_CHARS = 600` (policy edge `dieuphoi_consult_nhatky` không đổi); chỉ đổi thứ tự chọn trong cửa sổ. Test `test_consult_ranks_relevant_entry_first_within_window` trong `tests/test_orchestration_sdk.py`. Rollback: tham số mặc định `None` = hành vi cũ.
