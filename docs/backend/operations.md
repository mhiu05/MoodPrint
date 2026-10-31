# Vận hành backend và xử lý sự cố

## Local và đóng gói

Xem [development](../development.md) cho quickstart và disposable tests. Backend container dùng [backend/Dockerfile](../../backend/Dockerfile), frontend image dùng [frontend/Dockerfile](../../frontend/Dockerfile); root [Dockerfile](../../Dockerfile) là cách đóng gói cả SPA/API. Xem cấu hình cụ thể trước khi chọn pipeline.

```powershell
# repository root, chỉ build local
docker build -t moodprint-backend:local backend
docker build -t moodprint-web:local frontend
```

Build không đồng nghĩa đã deploy. Staging dùng [compose.staging.yml](../../deploy/compose.staging.yml), [Caddyfile](../../deploy/Caddyfile), một backend worker. Các tác vụ hosted/deploy cần quy trình và quyền riêng trong [deploy README](../../deploy/README.md).

## Startup, health và shutdown

- Startup không tự migration. Nếu cấu hình DB có sẵn, lifespan recover metadata interrupted trước nhận traffic; lỗi kết nối/schema có thể làm startup thất bại.
- `/api/v1/health/live` chỉ trả trạng thái process.
- `/api/v1/health/ready` kiểm tra SELECT, `moodprint.alembic_version` thuộc `READY_REVISIONS`, provider-session helper tồn tại. Nó không kiểm tra chất lượng AI, grant đầy đủ trên mọi bảng hoặc tất cả dependency hosted.
- Shutdown cancel sweep/indexer, đóng AI runtime/provider và database engine. Cần drain connection/run theo hạ tầng; restart không replay model call.

## Logging và capacity

Request log/metrics dùng request ID, error class, SQLSTATE hoặc counters tổng hợp; không log body, provider exception text, SQL parameters, tokens, mood notes hoặc transcript. `hide_parameters=True` ngăn SQLAlchemy đưa bind params vào lỗi chuẩn.

Mặc định database pool 8 + overflow 4, pool timeout 10 giây; đây là cấu hình một process, không nhân worker mà bỏ qua giới hạn database. AI runtime, stream slots, rate limit và temporary store có state RAM. Scale nhiều replica cần kiến trúc shared ephemeral state/fencing và test privacy/recovery trước.

## Runbook lỗi thường gặp

| Triệu chứng | Kiểm tra theo thứ tự |
| --- | --- |
| API không lên | Python/uv env, Settings validation, port 8001, DB connectivity và schema startup |
| Live OK, ready 503 | Database URL/role/network → revision → helper; không stamp head để né lỗi |
| Đăng nhập rồi 401 | Database có cùng `auth.sessions` với Auth? helper/runtime grants? session revoked/auth version? |
| AI unavailable | Capability, key + model, consent, eligibility; xem status public, không dump env |
| Budget không chặn | `AI_ACCOUNTING_ENABLED` có bật? daily budget khác 0? đã đọc warning accounting disabled? |
| Chat interrupted sau restart | Trạng thái dự kiến; tải lại, người dùng chọn gửi lượt mới, không auto replay |
| Matching trống | MATCH/adult → published live/consent version → language/goals → blocks/cooldown → threshold |
| Activity timer lệch | Server time offset và projection/version, không lấy đồng hồ thiết bị làm authority |
| DB test skip | Đặt `TEST_DATABASE_URL` local hậu tố `_test`; không dùng runtime URL thay thế |
| Windows không bind 55432 | Kiểm tra port reserved/occupied; dùng container disposable ở port trống, không dừng process người dùng |

`scripts/check_config.py`, `inspect_database.py`, `verify_runtime_role.py` hỗ trợ kiểm tra theo mục tiêu của script. Chúng có thể dùng cấu hình thật: đọc script trước khi chạy, không coi tên “check” là bảo đảm offline.

## Lời hỏi thăm (service `proactive`)

Service Compose riêng `proactive` (cùng image API, lệnh `python -m app.jobs.proactive`) chạy cả vòng materialize lịch → job và executor; process API **không bao giờ** sinh lời hỏi thăm. Mọi phối hợp qua PostgreSQL (`ai_proactive_jobs`: unique `(user, bot, slot, local_date)`, claim `SKIP LOCKED`, lease 90 s có `lease_token`). Không giữ transaction trong lúc gọi model; mọi transaction worker đặt `lock_timeout 2s`, `statement_timeout 5s`, `idle_in_transaction_session_timeout 15s`.

**Thứ tự bật (mỗi bước quan sát ≥ 24 h trên staging trước bước sau):**

1. Hosted đã ở `0022_proactive_messages` qua quy trình review SQL; image R1 (`READY_REVISIONS = 0022`) ready. R0 (`release/proactive-r0-compat`) sẵn sàng làm rollback.
2. (Owner duyệt) `ALTER ROLE moodprint_backend CONNECTION LIMIT 30` và `SET idle_in_transaction_session_timeout = '60s'` — xem [96 §5](../implementation-plans/proactive-multi-agent-companion/96-architecture-hardening-review.md#5-khuyến-nghị-dung-lượng-supabase).
3. `AI_MULTI_MESSAGE_ENABLED=true` (Gate G1a).
4. `AI_ACCOUNTING_ENABLED=true`, `AI_DAILY_BUDGET_USD > 0` (bắt buộc trước bước 6; validator production từ chối worker nếu thiếu).
5. `PROACTIVE_ENABLED=true` với `PROACTIVE_ROLLOUT_USER_IDS=[…]` (chỉ tài khoản thử nghiệm đã đồng ý): người dùng thấy trang lịch, chưa có lời hỏi thăm nào được gửi.
6. `PROACTIVE_WORKER_ENABLED=true` cho service `proactive` (biến trong env file; compose truyền `PROACTIVE_WORKER_ENABLED`). Concurrency mặc định 1; tăng lên 2 chỉ sau khi đã tăng connection limit (bước 2).
7. Mở rộng cohort, cuối cùng để `PROACTIVE_ROLLOUT_USER_IDS=[]`.

**Health.** Container healthcheck `python -m app.jobs.proactive --health` kiểm heartbeat (file trong `/tmp` tmpfs, cập nhật sau mỗi tick, hết hạn 120 s). Khi khởi động, worker đợi tới khi `alembic_version ∈ READY_REVISIONS` (log `proactive_worker_waiting reason=schema_revision`) — không bao giờ chạm bảng khi schema chưa đúng. `deploy.sh` không gate release theo worker (worker có thể tắt độc lập).

**Log/metric (không nội dung, không `user_id`):** `proactive_job_state job_id state reason bot slot attempt`, `metric=proactive_tick_ms`, `metric=proactive_queue_due` (mỗi 60 s), `metric=proactive_lag_seconds`, `metric=proactive_budget_skip`, `metric=proactive_safety_template`, `metric=proactive_job_failed`, `metric=proactive_job_expired`, `metric=proactive_tick_error`, `metric=proactive_provider_configuration`, `proactive_execution_end … duration_ms input_tokens output_tokens`. Alarm: `ProactiveFailedJobs`, `ProactiveExpiredJobs`, `ProactiveTickErrors`, `ProactiveProviderConfiguration`, `ProactiveBudgetSkip` trong [cloudwatch-alarms.json](../../deploy/aws/cloudwatch-alarms.json) (cấu hình, chưa áp dụng).

| Triệu chứng | Kiểm tra theo thứ tự |
| --- | --- |
| Không ai nhận lời hỏi thăm | `PROACTIVE_WORKER_ENABLED` trong env service `proactive`? container healthy? log `proactive_worker_waiting`? `metric=proactive_queue_due` tăng? cohort rollout? |
| Nhiều `expired`/`missed_window` | Worker dừng/chậm: CPU/RAM container, `metric=proactive_tick_ms`, model timeout; sau sự cố dài mỗi lịch chỉ có **một** `missed_window` rồi nhảy tới lần kế tiếp (không backlog) |
| `skipped(budget)` | Chi tiêu ngày ≥ `PROACTIVE_BUDGET_SHARE × AI_DAILY_BUDGET_USD`; chat người dùng vẫn còn phần còn lại |
| `failed(provider_configuration)` | Key/model; không retry tự động |
| `failed(invalid_output)` nhiều | Prompt/model đổi hành vi; chạy `python -m evals.proactive --live …` có trần ngân sách |
| Lời hỏi thăm bị hoãn liên tục (`retry active_chat`) | Người dùng đang chat cùng trợ lý; hết hạn → `skipped(active_chat)`; đúng thiết kế |
| Nghi giao trùng | Không thể với unique `(user,bot,slot,local_date)`; kiểm `ai_proactive_jobs` theo `run_id`, mỗi job `delivered` có đúng một run `completed` |
| Pool timeout ở worker | Concurrency > pool: giữ `DATABASE_POOL_SIZE ≥ PROACTIVE_WORKER_CONCURRENCY` (đo: mỗi job chỉ giữ 1 kết nối tại một thời điểm) |

**Dừng khẩn cấp / rollback:** `PROACTIVE_WORKER_ENABLED=false` rồi `docker compose up -d proactive` (dừng sinh mới; job đang chạy để lease hết hạn, không commit dở). `PROACTIVE_ENABLED=false` ẩn API/UI (GET trả `available=false`, ghi `503`). Tin đã giao vẫn hợp lệ trong lịch sử. Rollback image R1 → R0 an toàn ở 0022 (R0 bỏ qua bảng mới; nhiều bubble hiển thị thành nhiều tin). Không downgrade schema.

## Rollback

App rollback dùng image trước trên expanded schema tương thích và phải đáp ứng readiness thực tế. Ứng dụng journal chỉ chấp nhận `0019_journal`. Image tương thích ngay trước đó chấp nhận `0018_app_feedback` và `0019_journal`, nên nó vẫn ready sau upgrade cộng thêm và là rollback target. Không downgrade schema để rollback. Alembic destructive downgrade bị từ chối trong migrations. Hosted schema change và restore cần review riêng; xem [migrations](../supabase/migrations.md).
