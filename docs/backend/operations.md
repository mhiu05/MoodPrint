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

## Rollback

App rollback dùng image trước trên expanded schema tương thích và phải đáp ứng readiness thực tế. Image trước journal chấp nhận `0018_app_feedback` và `0019_journal`, nên nó vẫn ready sau upgrade journal cộng thêm và là rollback target của upgrade đó. Mọi head trước 0018 vẫn không ready. Alembic destructive downgrade bị từ chối trong migrations. Hosted schema change và restore cần review riêng; xem [migrations](../supabase/migrations.md).
