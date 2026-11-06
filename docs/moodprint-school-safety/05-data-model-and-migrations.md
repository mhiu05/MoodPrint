# 05 — Data model và migration

Nguyên tắc: **chỉ thêm bảng mới**, cộng một lần nới CHECK. Không thêm cột vào bảng đang được ORM cũ map. Nhờ vậy image đang chạy tương thích schema mới và rollback chỉ cần đổi image.

Quy ước chung cho mọi bảng dưới đây: schema `moodprint`; `id uuid PK` (trừ khi ghi khác); `created_at timestamptz default clock_timestamp()`; gọi `protect(table)` như `0029_journal_intelligence.py`; FK `user_id → users.id ON DELETE CASCADE` (trừ khi ghi khác); tên CHECK theo convention `ck_<table>_<name>`.

## 1. Danh sách migration

| Revision | Nội dung | WS |
| --- | --- | --- |
| `0030_school_profiles` | `school_profiles`; nới `ck_ai_conversations_bot` thêm `troly` | WS-02 |
| `0031_safety_events` | `safety_events` | WS-03 |
| `0032_assistant_workflows` | `assistant_workflow_states`, `assistant_proposals` | WS-04 |
| `0033_knowledge_base` | `kb_cards`, `kb_card_embeddings` | WS-05 |
| `0034_case_workspace` | `cases`, `incident_events`, `incident_event_revisions`, `case_evidence`, `case_summaries`, `case_action_plans`, `case_shares`, `case_access`, trigger bất biến | WS-06 |
| `0035_support_practice` | `trusted_adults`, `support_drafts`, `practice_sessions`, `speech_usage` | WS-07, WS-08 |

Toàn bộ đi hosted **một artifact**: `deploy/supabase/reviewed-sql/0035-review.sql`, khoảng `0029_journal_intelligence:0035_support_practice`.

## 2. Nhận dạng và điều khoản

### `school_profiles` (0030)

| Cột | Kiểu | Ràng buộc |
| --- | --- | --- |
| `user_id` | uuid PK | FK `users` CASCADE |
| `age_group` | varchar(8) | CHECK in (`'11-14'`, `'15-17'`) |
| `terms_version` | varchar(32) NULL | |
| `terms_accepted_at` | timestamptz NULL | Cùng NULL hoặc cùng có với `terms_version` |
| `guardian_ack_at` | timestamptz NULL | Thời điểm em tự khai người giám hộ đã biết; NULL với guest |
| `neutral_mode` | boolean | default false |
| `version` | int | default 1, ≥ 1 |
| `updated_at` | timestamptz | |

Không ghi `users.age_band`: CHECK của cột đó không chứa nhóm tuổi mới và cột được map ở mọi lần đọc user.

### Nới CHECK bot (0030)

Thêm `troly` vào `ALL_IDS` và dùng `replace_check` như `0024_three_agent_groups.py` với `ck_ai_conversations_bot`. Khai báo cặp này trong `constraint_swaps`. `ai_runs.bot_id` là `String(16)`, không có CHECK. `MEMORY_IDS` **không** thêm `troly`.

## 3. Safety

### `safety_events` (0031)

Không có nội dung. Hàng được ghi cho mức vàng, đỏ và khi postcheck chặn; không ghi cho mức xanh.

| Cột | Kiểu | Ràng buộc |
| --- | --- | --- |
| `user_id` | uuid | FK CASCADE, index cùng `created_at` |
| `run_id` | uuid NULL | FK `ai_runs` SET NULL |
| `request_id` | varchar(64) | |
| `surface` | varchar(16) | `chat`, `practice`, `upload` |
| `level` | varchar(8) | `yellow`, `red` |
| `labels` | jsonb | Mảng, tối đa 8, trong tập nhãn |
| `tier` | varchar(16) | `rule`, `context`, `classifier`, `postcheck`, `timeout` |
| `rule_pack_version` | varchar(32) | |
| `classifier_outcome` | varchar(16) | `ok`, `timeout`, `error`, `skipped` |

Retention 90 ngày trong `jobs/retention.py`.

## 4. Workflow và đề xuất

### `assistant_workflow_states` (0032)

| Cột | Kiểu | Ràng buộc |
| --- | --- | --- |
| `conversation_id` | uuid PK | FK `ai_conversations` CASCADE |
| `user_id` | uuid | FK CASCADE |
| `workflow` | varchar(8) | `none`, `wf01`…`wf06` |
| `state` | varchar(32) | Do state machine kiểm tra |
| `slots` | jsonb | ≤ 8 KiB; chỉ enum và chuỗi ngắn |
| `return_workflow`, `return_state` | NULL | Nơi quay lại sau WF-06 |
| `case_id` | uuid NULL | FK `cases` SET NULL (thêm ở 0034) |
| `emergency_acknowledged_at` | timestamptz NULL | |
| `version` | int | ≥ 1 |
| `updated_at` | timestamptz | |

Hội thoại tạm của phiên luyện nói giữ state này trong RAM trên `Conversation`. Hội thoại của khách là hội thoại lưu, hết hạn theo vòng đời 2 giờ.

### `assistant_proposals` (0032)

Tool không ghi dữ liệu bền vững; chỉ tạo proposal. Người dùng xác nhận trên UI mới ghi.

| Cột | Kiểu | Ràng buộc |
| --- | --- | --- |
| `conversation_id` | uuid | FK CASCADE |
| `run_id` | uuid NULL | FK SET NULL |
| `kind` | varchar(24) | `case_create`, `event_add`, `event_revise`, `plan_save`, `trusted_adult_add`, `draft_save`, `summary_save`, `practice_summary_save` |
| `payload` | jsonb | ≤ 16 KiB |
| `status` | varchar(12) | `proposed`, `confirmed`, `rejected`, `expired` |
| `expires_at` | timestamptz | 24 giờ |
| `decided_at` | timestamptz NULL | |
| `version` | int | ≥ 1 |

## 5. Knowledge base

Thẻ không chứa dữ liệu cá nhân. Git là nguồn sự thật; bảng là bản index.

### `kb_cards` (0033)

| Cột | Kiểu | Ràng buộc |
| --- | --- | --- |
| `card_id` | varchar(64) PK | |
| `version` | int | |
| `content_sha256` | char(64) | |
| `title`, `category`, `action` | varchar | `action` theo enum |
| `audiences`, `age_bands` | jsonb | Mảng |
| `jurisdiction` | varchar(16) | `vn`, `foreign`, `global` |
| `body` | text | ≤ 3000 ký tự |
| `claims`, `sources` | jsonb | |
| `limitations` | text | |
| `review_status` | varchar(16) | Chỉ `approved` hoặc `retired` trong bảng |
| `reviewed_by`, `reviewed_at`, `next_review_at`, `expires_at` | | |
| `search_text` | text | Đã bỏ dấu |
| `search_vector` | tsvector | `GENERATED ALWAYS AS (to_tsvector('simple', search_text)) STORED`; GIN index |
| `updated_at` | timestamptz | |

Không cài `pg_trgm` hay `unaccent`: hosted có sẵn nhưng chưa bật; bỏ dấu làm bằng Python, `simple` không cần extension.

### `kb_card_embeddings` (0033)

PK (`card_id`, `model`, `dimensions`). Cột `content_sha256`, `embedding Vector()`, CHECK `dimensions in (256,512,1024,2048) and extensions.vector_dims(embedding) = dimensions`. Không tạo HNSW: dưới 300 hàng, quét chính xác.

## 6. Hồ sơ sự việc

### `cases` (0034)

| Cột | Kiểu | Ràng buộc |
| --- | --- | --- |
| `title` | varchar(120) | Do người dùng đặt; mặc định "Sự việc của em" |
| `role` | varchar(12) | `target`, `bystander` |
| `behaviors` | jsonb | `physical`, `verbal`, `isolation`, `online`, `sexual_harassment`, `extortion` |
| `status` | varchar(12) | `open`, `closed` |
| `version` | int | |
| `updated_at` | timestamptz | |

### `incident_events` (0034)

| Cột | Kiểu | Ràng buộc |
| --- | --- | --- |
| `case_id` | uuid | FK CASCADE |
| `occurred_at` | timestamptz NULL | |
| `occurred_precision` | varchar(12) | `exact`, `day`, `month`, `approximate`, `unknown` |
| `occurred_label` | varchar(80) NULL | "khoảng đầu tuần trước" |
| `location_kind` | varchar(12) | `school`, `commute`, `online`, `home`, `other`, `unknown` |
| `platform` | varchar(32) NULL | |
| `repeated` | boolean NULL | |
| `people_aliases` | jsonb | Mặc định bí danh |
| `current_revision` | int | ≥ 1 |
| `version` | int | |

Thời điểm ghi là `created_at`, tách khỏi thời điểm xảy ra.

### `incident_event_revisions` (0034)

Append-only. UNIQUE (`event_id`, `revision`). Cột `narrative text` ≤ 4000 ký tự, `author` (`student`, `assistant_draft_confirmed`). Trigger `incident_revision_guard` chặn mọi `UPDATE`.

### `case_evidence` (0034)

| Cột | Kiểu | Ràng buộc |
| --- | --- | --- |
| `case_id` | uuid | FK CASCADE |
| `event_id` | uuid NULL | FK `incident_events` SET NULL |
| `object_path` | varchar(512) | UNIQUE |
| `mime_type` | varchar(32) | Ảnh: `image/jpeg`, `image/png`, `image/webp`, `image/gif`. Video: `video/mp4`, `video/webm`, `video/quicktime` |
| `size_bytes` | bigint | > 0; ảnh ≤ 10 MiB, video ≤ 50 MiB |
| `label` | varchar(120) NULL | |
| `source_kind` | varchar(16) | `self_screenshot`, `self_photo`, `friend_provided`, `other` |
| `source_note` | varchar(200) NULL | |
| `status` | varchar(8) | `pending`, `ready` |
| `sha256` | char(64) NULL | Server tính |
| `uploaded_at` | timestamptz NULL | `clock_timestamp()` lúc xác nhận |

Trigger `case_evidence_guard`: khi `OLD.sha256 IS NOT NULL`, chặn đổi `sha256`, `object_path`, `size_bytes`, `mime_type`, `uploaded_at`.

Bằng chứng dùng chung bucket `journal-media` với tiền tố `cases/{user_id}/{case_id}/{evidence_id}.{ext}`, nên không cần thao tác hạ tầng mới. Tách bucket nếu luật sư yêu cầu ở G6.

### `case_summaries` (0034)

`case_id`, `version`, `draft_text` ≤ 4000, `confirmed_text` NULL, `status` (`draft`, `confirmed`), `run_id` NULL, `confirmed_at` NULL.

### `case_action_plans` (0034)

`user_id`, `case_id` NULL (FK SET NULL), `kind` (`offline_safety`, `online_safety`, `support`), `content` jsonb ≤ 16 KiB, `status` (`active`, `archived`), `version`, `updated_at`.

### `case_shares` (0034)

Nhật ký xuất, chừa chỗ cho chia sẻ. `case_id`, `kind` (`pdf_export`), `scope` jsonb, `sha256`, `revoked_at` NULL. Không giữ file PDF.

### `case_access` (0034)

PK `user_id`. `pin_hash` (scrypt, chuỗi gồm salt và tham số), `failed_attempts`, `locked_until` NULL, `version`, `updated_at`.

## 7. Hỗ trợ và luyện nói

### `trusted_adults` (0035)

`alias` varchar(60), `relation` (`homeroom_teacher`, `counselor`, `teacher`, `parent`, `relative`, `other`), `contact_note` varchar(120) NULL, `is_safe` boolean default true, `priority` smallint, `version`, `updated_at`.

### `support_drafts` (0035)

`case_id` NULL, `kind` (`message`, `card_111`), `recipient_alias` NULL, `content` text ≤ 2000, `version`, `updated_at`.

### `practice_sessions` (0035)

`mode` (`retell`, `trusted_adult`, `call_111`), `scenario_id` varchar(32), `difficulty` (`gentle`, `challenging`), `status` (`active`, `ended`, `expired`), `conversation_id` uuid (hội thoại tạm, không FK), `turn_count`, `ended_at` NULL, `expires_at`, `version`. Retention 30 ngày.

### `speech_usage` (0035)

Mẫu theo `ai_search_usage`. `user_id` FK **SET NULL** (nghĩa vụ chi phí sống qua xóa user), `kind` (`stt`, `tts`), `provider`, `model`, `units`, `estimated_nano_usd` bigint, `state` (`open`, `settled`, `uncertain`). `speech_liability()` cộng vào `budget_liability`.

## 8. Export, purge, retention

| Bảng | Export | Purge tài khoản | Retention |
| --- | --- | --- | --- |
| `school_profiles` | Có | CASCADE | Theo tài khoản |
| `safety_events` | Không (metadata an toàn) | CASCADE | 90 ngày |
| `assistant_workflow_states` | Không | CASCADE | Theo hội thoại |
| `assistant_proposals` | Không | CASCADE | Xóa sau hết hạn 7 ngày |
| `cases`, `incident_*`, `case_evidence`, `case_summaries`, `case_action_plans` | Có | CASCADE; object Storage vào `journal_storage_deletions` | Tới khi người dùng xóa |
| `case_shares` | Có | CASCADE | Theo case |
| `case_access` | Không | CASCADE | Theo tài khoản |
| `trusted_adults`, `support_drafts` | Có | CASCADE | Tới khi người dùng xóa |
| `practice_sessions` | Không | CASCADE | 30 ngày |
| `speech_usage` | Không | SET NULL | 90 ngày |
| `kb_*` | Không | Không liên quan | Theo git |

Dữ liệu của khách tự xóa theo vòng đời 2 giờ: `guests/lifecycle.py` phải biết mọi bảng trên. Xóa case là hành động của người dùng, cần xác nhận. "Bất biến" nghĩa là không sửa, không có nghĩa là không xóa được.

## 9. Quy trình

Mỗi migration:

1. Viết file trong `backend/alembic/versions/`, thêm ORM, `protect(table)`.
2. `upgrade()` chỉ thêm. `downgrade()` từ chối nếu có dữ liệu, như 0029.
3. Trên DB disposable: `alembic upgrade head`, `alembic check`.
4. Cập nhật test ghim head, `docs/supabase/schema.md`, `docs/supabase/migrations.md`.
5. Không dùng `%%` trong SQL; dùng `'...' || quote_ident(r)`.

Khi cả WS-02…WS-08 xong, tạo artifact hosted:

1. Thêm `UpgradePlan` key `"0035"` vào `UPGRADES` trong `scripts/apply_supabase_review.py`: `from_revision="0029_journal_intelligence"`, `to_revision="0035_support_practice"`, `tables` là 18 bảng ở trên, `constraint_swaps=(("ai_conversations", "ck_ai_conversations_bot"),)`.
2. Xuất offline thành `deploy/supabase/reviewed-sql/0035-review.sql`, thêm vào `MANIFEST.json` kèm SHA-256 và số byte.
3. Chạy `python scripts/apply_supabase_review.py --upgrade 0035` ở chế độ review-only, rồi `scripts/check_reviewed_artifacts.py`.
4. Diễn tập trên snapshot chỉ cấu trúc. Thứ tự hosted ở [release-runbook](grok-handoff/release-runbook.md).

**TO_VERIFY**: `review_upgrade_artifact` từ chối regex `\b(?:DROP|TRUNCATE)\b` trong SQL; trigger không được chứa các từ này. `replace_check` phải sinh `ADD ... NOT VALID` + `VALIDATE` để qua kiểm tra `constraint_swaps`. Nội dung `RAISE EXCEPTION` không dùng ký tự `%`.

## 10. Rollback

| Tình huống | Hành động |
| --- | --- |
| Image F lỗi sau khi có schema 0035 | Quay về image C (nhận 0029 và 0035). Schema giữ nguyên. |
| SQL fail giữa chừng | Giao dịch đơn, tự rollback; revision vẫn 0029 |
| Cần bỏ tính năng | Bỏ `APP_PROFILE`, deploy lại. Bảng mới không ảnh hưởng |
| Downgrade schema | **Không làm trên hosted** |
