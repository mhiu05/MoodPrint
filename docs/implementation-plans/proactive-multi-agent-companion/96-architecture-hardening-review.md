# 96 — Rà soát gia cố kiến trúc (trước khi triển khai Phase 1)

Ngày: **31/10/2026**. Nhánh: `feat/proactive-companion-phase1` (worktree `E:\MoodPrint-proactive-phase1`), tách từ commit `d6eaf71` của `test/local-2026-10-30`. Tài liệu này ghi **dữ kiện đã kiểm chứng** trong phiên triển khai và các quyết định thay đổi so với bộ kế hoạch gốc. Khi khác với [01](01-current-codebase-audit.md)/[03](03-architecture-decisions.md), tài liệu này là bản mới hơn.

> Quy ước bằng chứng: **[mã]** = đọc trực tiếp mã nguồn ở commit `d6eaf71`; **[hosted]** = truy vấn chỉ đọc qua Supabase MCP lúc 31/10/2026 ~08:20 (UTC+7); **[tài liệu]** = tài liệu Supabase chính thức; **[ước lượng]** = công thức có giả định ghi rõ, chưa đo.

## 1. Phát hiện kỹ thuật quan trọng

| # | Phát hiện | Bằng chứng | Hệ quả |
| --- | --- | --- | --- |
| F-01 | Mọi lời gọi mạng (OpenAI, Voyage, Supabase Storage, Supabase Auth) đều nằm **ngoài** transaction DB. `drive()` mở transaction ngắn riêng cho `check()`, `record_usage()`, publish; model call không giữ connection | [mã] [runtime.py:577-725](../../../backend/app/ai/runtime.py#L577), [embeddings.py:599-628](../../../backend/app/ai/embeddings.py#L599), [media_routes.py](../../../backend/app/modules/journal/media_routes.py) (ký URL giữa hai transaction) | Mẫu "transaction ngắn → I/O → transaction ngắn + kiểm lại" **đã là chuẩn** của codebase; executor proactive phải theo đúng mẫu này |
| F-02 | Hiện tượng "3 kết nối *idle in transaction* ~8 phút" của phiên lập kế hoạch **không tái hiện**: lúc kiểm có 5 kết nối `moodprint_backend` qua Supavisor, tất cả `idle`, `max_xact_age = null` | [hosted] `pg_stat_activity` gom nhóm | Không có đường mã nào trong ứng dụng giữ transaction quanh I/O mạng (F-01). Nguồn khả dĩ nhất: tiến trình dev local dùng `backend/.env` trỏ hosted (debugger/REPL dừng giữa transaction) hoặc công cụ ngoài. Không phải lỗi rò rỉ kết nối của ứng dụng |
| F-03 | `monitor_policy()` gọi `check()` mỗi 0,5 s trong suốt một lượt chat → mỗi run đang chạy checkout pool ~2 lần/giây (mỗi lần vài ms) | [mã] [runtime.py:643-653](../../../backend/app/ai/runtime.py#L643) | Không giữ kết nối lâu, nhưng tạo churn tỉ lệ với số run đồng thời. Executor proactive **không** dùng monitor 0,5 s; chỉ kiểm ở E1, trước mỗi model request (hook) và E5 |
| F-04 | Hosted `idle_in_transaction_session_timeout = 0`, `statement_timeout = 120 s`, `max_connections = 60`, `superuser_reserved_connections = 3`, `moodprint_backend.rolconnlimit = 20`, role không có `rolconfig` | [hosted] `pg_settings`, `pg_roles` | Thiếu "lưới an toàn" ở mức server. Worker mới đặt `SET LOCAL lock_timeout/statement_timeout/idle_in_transaction_session_timeout` trong **mọi** transaction của nó; đề xuất (cần owner duyệt) `ALTER ROLE moodprint_backend SET idle_in_transaction_session_timeout = '60s'` |
| F-05 | `daily_turns()` và `admission()` đếm **mọi** `ai_runs` của user | [mã] [persistence.py:190-268](../../../backend/app/ai/persistence.py#L190) | Phải lọc `origin='user'` cho quota/rate/concurrency người dùng (P1-11), global vẫn đếm tất cả |
| F-06 | `ai_runs.conversation_id` **không có FK**; partial unique `uq_ai_active_conversation` trên `conversation_id WHERE status='running'` | [mã] [models.py:190-206](../../../backend/app/infrastructure/database/models.py#L190) | Run proactive chạy với `conversation_id NULL` không đụng unique; khi publish phải đặt `conversation_id` **cùng một UPDATE** với `status='completed'`, nếu không sẽ va unique khi người dùng vừa bắt đầu một run trong cùng hội thoại |
| F-07 | Naming convention CHECK là `ck_%(table_name)s_%(constraint_name)s`; unique `uq_%(table_name)s_%(column_0_name)s` | [mã] [models.py:28-38](../../../backend/app/infrastructure/database/models.py#L28) | Xác nhận rủi ro trùng tên `uq_ai_messages_run_id` của [phase-1/04 §3](phase-1/04-database-and-migrations.md) → tên tường minh `uq_ai_messages_run_part` |
| F-08 | `durable_run()` lấy **một** row bot bằng `scalar()`; SSE persistent dựng event cố định seq 1–3 từ DB | [mã] [chat_routes.py:506-527](../../../backend/app/ai/chat_routes.py#L506), [chat_routes.py:613-635](../../../backend/app/ai/chat_routes.py#L613) | Đúng như kế hoạch; P1-06 thay bằng truy vấn mọi phần `ORDER BY part_index` |
| F-09 | `deploy.sh` chỉ kiểm health `api` và `web`; `docker compose up -d` tạo lại từng service (dừng container cũ trước khi chạy mới) | [mã] [deploy.sh:83-100](../../../deploy/aws/deploy.sh#L83) | Thêm service worker riêng **không** làm hỏng cổng health của release; worker không chồng hai bản khi deploy |
| F-10 | SDK pin `openai-agents==0.24.0` (lockfile); `Runner.run_streamed(max_turns=3)`, `_BudgetHooks` (model ≤3, tool ≤2), guardrail `_no_unreceipted_claim`, tracing tắt, `store=False`, `max_retries=0` | [mã] [provider.py](../../../backend/app/ai/provider.py), `uv.lock` | Không nâng cấp SDK. Proactive dùng `Runner.run` (không stream), `max_turns=2`, không tool, cùng hooks ngân sách |
| F-11 | Hosted nhỏ: 6 user registered active, 116 run/30 ngày, 0 run đang chạy, p95 `requests_started` = 2, 0 journal entry, 7 hội thoại, 58 tin | [hosted] aggregate | Tải proactive beta rất nhỏ; ràng buộc thật là **ngân sách kết nối** và **độ cô lập web**, không phải CPU DB |
| F-12 | Công việc friendship-profile song song của Codex **không có migration** ("No SQL migration/backfill/index/RLS change") | Đọc tài liệu chưa commit `docs/friendship-profile-redesign/04-technical-specification.md` trong worktree gốc (chỉ đọc) | M-P1-A/M-P1-B nhận số **0021**/**0022** nối sau `0020_private_profile_retirement` |
| F-13 | `test_foundation.py::test_ready_revisions_cover_the_reviewed_migration_window` và một case readiness `0019_journal-200` được Codex ghi là fail có sẵn | Sổ bằng chứng friendship-profile | Xác minh lại ở baseline P1-00 ([evidence/execution.md](evidence/execution.md)) |

## 2. Quyết định kiến trúc (thay đổi so với bộ kế hoạch)

| ID | Quyết định | Thay thế | Lý do |
| --- | --- | --- | --- |
| HD-01 | **Topology worker:** service Docker Compose riêng `proactive` (cùng image API, lệnh `python -m app.jobs.proactive`) chạy cả vòng *scheduler* (materialize) và *executor* (claim + chạy) trong **một** process. Process API **không bao giờ** gọi model cho lời hỏi thăm | ADR-05 (worker trong lifespan API) | Owner ưu tiên độ trễ/ổn định và cho phép tăng tài nguyên khi có căn cứ. Tách process loại bỏ hoàn toàn việc model call proactive chia event loop với request web (rủi ro R-04), cho phép giới hạn RAM/CPU riêng và tắt/khởi động lại độc lập. Mọi phối hợp qua PostgreSQL nên tách scheduler/executor thành hai container sau này không đổi mã |
| HD-02 | Pool riêng cho worker: `DATABASE_POOL_SIZE=2`, `DATABASE_POOL_OVERFLOW=0` qua env của service `proactive` | — | Ngân sách kết nối §4 |
| HD-03 | Mọi transaction của worker: `set_config('lock_timeout','2000',true)`, `statement_timeout` 5 s, `idle_in_transaction_session_timeout` 15 s | [phase-1/03 §12](phase-1/03-proactive-scheduler-and-workers.md) (chỉ hai tham số đầu) | F-04: lưới an toàn ở mức transaction không cần đổi hosted |
| HD-04 | Môi trường test/dev: không có worker ngầm trong API; test gọi `proactive_tick()` trực tiếp, fullstack dùng endpoint chỉ tồn tại khi `APP_ENV=test` | ADR-05 "vòng lặp lifespan" | Tất định, không phụ thuộc đồng hồ thật |
| HD-05 | Publish: `UPDATE ai_runs SET conversation_id=:c, status='completed' WHERE id=:r AND status='running'` trong **một** câu lệnh | [phase-1/05 §4.4](phase-1/05-backend-api-and-agent-runtime.md) | F-06 |
| HD-06 | Admission proactive (E1) dùng **cùng** advisory lock `664201` như `admission()` để `ai_global_concurrency` vẫn là trần toàn hệ thống, cộng thêm trần `PROACTIVE_BUDGET_SHARE` | [phase-1/03 §10](phase-1/03-proactive-scheduler-and-workers.md) | Hai process cùng ghi `ai_runs`; chỉ advisory lock dùng chung mới tránh vượt trần đồng thời |

Các ADR-01…ADR-04, ADR-06…ADR-12 **giữ nguyên**; đã đối chiếu với mã ở F-05…F-08.

## 3. Phân tích transaction và kết nối

### 3.1 Đường gọi hiện có (đã đọc mã)

| Đường | Transaction | Có I/O mạng trong transaction? |
| --- | --- | --- |
| `send()` | Một transaction: khóa user + hội thoại, idempotency, admission (advisory lock), insert run/turn/usage/tin `self` | Không |
| `drive()` | `check()` (ngắn) → projection (ngắn) → `retrieve_memories` (ngắn → Voyage → ngắn) → model (**không** transaction) → publish (ngắn) | Không |
| `monitor_policy()` | `check()` mỗi 0,5 s | Không (F-03) |
| `events()` SSE | Mỗi tick 0,25 s một `transaction(lock=False)`; `yield` nằm **ngoài** transaction | Không |
| Journal media | Transaction → ký URL Storage → transaction | Không |
| `require_actor` | Session không `begin()` (autobegin), đóng ngay sau khi đọc | Không |

### 3.2 Đường mới (executor proactive)

```text
T1  claim (khóa job, SKIP LOCKED)                         ~5 ms
T2  E1 authorize + admission + ghi run/turn/usage         ~10–20 ms
T3  E2 đọc dữ liệu persona (owner lock FOR SHARE)          ~5 ms
--  E3 model call — KHÔNG transaction, KHÔNG checkout      1,5–8 s
    hook on_llm_start: authorize rút gọn (transaction ngắn)
    observer usage: persist_snapshot (transaction ngắn)
--  E4 validate — thuần Python
T4  E5 publish (owner → job → conversation)               ~10–30 ms
```

Mỗi transaction đặt HD-03. Không bao giờ giữ session qua `await` model.

## 4. Ngân sách kết nối Supabase

Công thức (mở rộng [budget.py](../../../backend/app/infrastructure/database/budget.py)):

```text
demand = OVERLAP × (api_pool + api_overflow) + (worker_pool + worker_overflow)
headroom = rolconnlimit − demand ≥ MINIMUM_HEADROOM (4)
```

Worker không nhân `OVERLAP` vì compose dừng container cũ trước khi chạy container mới (F-09); job đang chạy để lease hết hạn rồi được claim lại.

| Cấu hình | API (5+2) × 2 | Worker | Tổng | Headroom (limit 20) | Đạt? |
| --- | --- | --- | --- | --- | --- |
| Hiện tại | 14 | — | 14 | 6 | Có |
| **HD-02 (mặc định đề xuất)** | 14 | 2 + 0 | **16** | **4** | **Có** (vừa đủ) |
| Worker 2 + 1 | 14 | 3 | 17 | 3 | Không |
| Tăng `rolconnlimit` lên 30 (cần owner duyệt, hosted) | 14 | 3 + 1 | 18 | 12 | Có |

Tổng phía PostgreSQL [hosted]: ngoài `moodprint_backend` có ~8 kết nối dịch vụ (pgbouncer 2, supabase_admin 3, postgres/mgmt 1, pg_net 1, PostgREST 1) + 3 reserved. Với `rolconnlimit = 30`: 30 + 8 + 3 = 41 < 60 ⇒ còn ~19. Tài liệu Supabase khuyến nghị pool ≤ 40–80 % `max_connections` tùy mức dùng PostgREST [tài liệu: Connection management].

## 5. Khuyến nghị dung lượng Supabase

| Mức | Khi nào | Hành động | Rollback |
| --- | --- | --- | --- |
| S0 (hiện tại) | Beta ≤ 100 user | Giữ compute hiện tại (`max_connections=60`); HD-02 | — |
| S1 | Khi bật worker trên staging/production | `ALTER ROLE moodprint_backend CONNECTION LIMIT 30;` và `ALTER ROLE moodprint_backend SET idle_in_transaction_session_timeout = '60s';` qua quy trình review SQL, **owner duyệt** | `ALTER ROLE … CONNECTION LIMIT 20; ALTER ROLE … RESET idle_in_transaction_session_timeout;` |
| S2 | `db_pool_checked_out` p95 ≥ 5 kéo dài hoặc `pool_timeout` xuất hiện, hoặc > ~500 user hoạt động | Nâng compute add-on để có `max_connections` lớn hơn, sau đó tăng pool API | Hạ compute (Supabase cho đổi qua dashboard, có downtime ngắn khi đổi) |

Không ghi giá: bảng giá compute add-on phải được owner xem trên dashboard (không đọc được qua MCP trong phiên này). Không có thay đổi hosted nào được thực hiện.

## 6. Khuyến nghị dung lượng AWS

**Không kiểm chứng được** tài nguyên EC2: AWS MCP lỗi kết nối `-32602 Invalid request parameters`; AWS CLI cục bộ (`aws-cli/2.38.5`, profile `moodprint`) báo *"Your session has expired. Please reauthenticate using 'aws login'"*. Không suy đoán loại instance hay số credit.

Ước lượng [ước lượng] cho service `proactive` (Python 3.12 + FastAPI app import + SDK, không phục vụ HTTP): RSS lúc nghỉ ≈ 120–180 MB, đỉnh khi chạy 2 job song song < 250 MB. Đề xuất compose: `mem_limit: 384m`, `cpus: 0.5`, `stop_grace_period: 100s`, `read_only`, `restart: unless-stopped`.

Điều kiện trước khi bật worker trên EC2 (giữ từ [91 §9](91-performance-cost-and-capacity.md)): CloudWatch 7 ngày `mem_used_percent` p95 < 70 % **sau khi cộng 384 MB**, `cpu_usage_active` p95 < 50 %. Nếu không đạt: nâng instance một bậc (owner duyệt chi phí trên Billing), không tăng worker uvicorn.

| Phương án | Mô tả | Ưu | Nhược | Đề xuất |
| --- | --- | --- | --- | --- |
| A | Worker trong process API (ADR-05 cũ) | 0 kết nối thêm | Model call chia event loop với web; restart API = dừng worker | Không |
| **B** | **Service `proactive` riêng, cùng EC2** | Cô lập web; giới hạn tài nguyên riêng; tắt độc lập | +2 kết nối, +≤384 MB RAM | **Chọn (HD-01)** |
| C | B + tăng worker uvicorn API / pool lớn | Thông lượng chat cao hơn | Cần `rolconnlimit`/compute lớn hơn; API giữ state RAM (temporary chat, stream) nên **nhiều worker uvicorn chưa an toàn** ([01 §10](01-current-codebase-audit.md)) | Chỉ khi có số đo chat p95 xấu; không phải điều kiện Phase 1 |

## 7. Ma trận phụ thuộc migration

| Revision | Nội dung | Phụ thuộc | Hosted | Ai tạo |
| --- | --- | --- | --- | --- |
| `0019_journal` | Journal | 0018 | **Đã áp dụng** | Có sẵn |
| `0020_private_profile_retirement` | Retire private profile | 0019 | **Chưa** (BLK-02) | Có sẵn |
| `0021_multi_message` (M-P1-A) | `ai_messages.part_*`, `ai_runs.origin/proactive_slot`, nullable có CHECK | 0020 | Chưa — chỉ offline SQL | Nhánh này |
| `0022_proactive_messages` (M-P1-B) | 5 bảng proactive | 0021 | Chưa — chỉ offline SQL | Nhánh này |
| Friendship-profile (Codex) | **Không có migration** | — | — | F-12 |

Nếu một nhánh khác thêm migration nối sau 0020 trước khi merge: đổi `down_revision` của 0021 khi rebase (chưa áp dụng ở đâu nên an toàn), cập nhật `READY_REVISIONS`.

## 8. Rà soát OD-01…OD-12

| ID | Quyết định triển khai (mặc định bảo thủ) | Cần owner trước khi |
| --- | --- | --- |
| OD-01 | Hội thoại gần nhất đủ điều kiện, nếu không tạo mới | Bật worker cho người dùng thật |
| OD-02 | 4/ngày; sáng 05:00–11:30, tối 17:00–22:30, bước 15' | Như trên |
| OD-03 | Teen có lời hỏi thăm (trừ Cầu Nối), tối ≤ 21:00, giờ yên lặng mặc định 21:30–07:00 | Như trên |
| OD-04 | Văn bản consent nháp, **mặc định tắt**; mã và UI có sẵn sau cờ | **Bật `PROACTIVE_ENABLED` cho người dùng thật** — không suy diễn thành consent |
| OD-05 | 14 ngày không hoạt động → ngừng; auto-pause sau 3 lời chưa mở | Bật worker |
| OD-06 | 50 % ngân sách ngày | Bật worker |
| OD-07 | Mẫu tin an toàn **không** có số điện thoại | Owner cung cấp nguồn kiểm chứng |
| OD-08…OD-10 | Phase 2 — không đụng | Gate G1 |
| OD-11 | Timezone riêng cho lời hỏi thăm; không đổi timezone tài khoản | — |
| OD-12 | Dùng `OPENAI_MODEL` hiện tại | — |

Không quyết định nào trên đây thay đổi quyền dữ liệu nhạy cảm theo hướng mở rộng: mọi đường đọc nhật ký mới đều sau opt-in mặc định tắt và sau cờ tính năng mặc định tắt.

## 9. Rủi ro đã giải quyết

| Rủi ro gốc | Trạng thái | Căn cứ |
| --- | --- | --- |
| R-04 Worker làm chậm chat | **Giảm mạnh** | HD-01: process riêng |
| R-06 *Idle in transaction* | **Đóng cho mã ứng dụng** | F-01, F-02; lưới an toàn HD-03 |
| R-13 Số migration bị chiếm | **Đóng** | F-12 |
| Unique khi publish | **Đóng bằng thiết kế** | HD-05 |

## 10. Rủi ro còn mở

| ID | Rủi ro | Giảm thiểu / ai xử lý |
| --- | --- | --- |
| U-01 | Không kiểm được EC2 (RAM/CPU/credit) | Owner chạy `aws login --profile moodprint` hoặc sửa cấu hình `aws-mcp`; cần quyền chỉ đọc `ec2:Describe*`, `cloudwatch:GetMetricData`, `logs:FilterLogEvents`, `ce:GetCostAndUsage` |
| U-02 | Headroom kết nối chỉ vừa đủ 4 với HD-02 | S1 (owner duyệt) trước khi tăng concurrency worker |
| U-03 | Hosted chưa áp dụng 0020 (BLK-02) | Owner |
| U-04 | Rehearsal migration trên bản sao schema hosted cần `pg_dump --schema-only` bằng credential hosted | Chưa làm trong phiên này; chỉ rehearsal trên chuỗi migration sạch + dữ liệu tổng hợp. Cần owner cho phép dump schema |
| U-05 | Eval live tốn phí | Chỉ chạy offline; live cần ngân sách owner duyệt |

## 11. Mức sẵn sàng triển khai local

`READY` cho P1-00…P1-08 trên DB disposable local (`moodprint-proactive-p1-db`, `127.0.0.1:36432`, mọi DB kết thúc `_test`). Không dùng `backend/.env`; pytest đã ép `DATABASE_URL=''`; Alembic chỉ chạy với `DATABASE_MIGRATION_URL` local truyền tường minh.

## 12. Điều kiện Gate G1a

1. P1-00…P1-08 xong, mỗi task có test đỏ→xanh và commit riêng.
2. Toàn bộ backend suite xanh (trừ fail có sẵn đã ghi ở baseline, nếu còn).
3. Migration 0021/0022: upgrade từ 0020 có dữ liệu mẫu, `alembic check` không drift, offline SQL sinh được.
4. SSE v1 byte-for-byte với run 1 bubble; v1 ghép với run nhiều bubble; v2 đúng thứ tự; replay `afterSeq` 0..3.
5. Frontend: typecheck, unit, build, E2E fixture; agent-browser trên fullstack local với fake model nhiều bubble ở 390/768/1440.
6. Báo cáo eval tách bubble: offline chạy thật; live ghi rõ "chưa chạy".

## 13. Điều kiện triển khai hosted

1. Owner duyệt và áp dụng 0020 (BLK-02).
2. Owner cho phép dump schema hosted để rehearsal 0021/0022; artifact review SQL + sha256.
3. Owner duyệt S1 (connection limit + idle timeout) **trước** khi chạy service `proactive` trên staging.
4. EC2 đạt điều kiện §6 (cần U-01).
5. OD-04 được duyệt trước khi bật `PROACTIVE_ENABLED` cho người dùng thật; rollout theo `PROACTIVE_ROLLOUT_USER_IDS`.

## 14. Yêu cầu kiểm thử bổ sung (so với [phase-1/09](phase-1/09-testing-and-acceptance.md))

| Test mới | Lý do |
| --- | --- |
| Executor không giữ checkout trong model call: fake model đo `database.occupancy()` trong lúc gọi = 0 | F-01, HD-01 |
| Mọi transaction worker có `lock_timeout`/`statement_timeout`/`idle_in_transaction_session_timeout` (đọc `current_setting` trong transaction) | HD-03 |
| Publish khi người dùng có run `running` trong hội thoại đích → defer, không vi phạm `uq_ai_active_conversation` | HD-05 |
| Admission proactive + chat song song không vượt `ai_global_concurrency` | HD-06 |
| `budget.py`: demand gồm worker; headroom ≥ 4 với cấu hình mặc định | §4 |
