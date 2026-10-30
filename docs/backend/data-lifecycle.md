# Dữ liệu, consent, hoạt động và xóa

## Các version làm nhiệm vụ khác nhau

`auth_version` vô hiệu app sessions khi danh tính/quyền truy cập tài khoản thay đổi. `data_version` đánh dấu privacy context cũ. Consent có version theo purpose; public profile/ref/request giữ snapshot phục vụ recheck. Resource `version` bảo vệ optimistic write. Không thay tất cả bằng một counter frontend.

Consent ban đầu tắt. MEM và VOICE phụ thuộc AI; MATCH yêu cầu adult. Rút quyền ảnh hưởng runtime, index, profile visibility, requests/rooms/activities theo module hooks. Bật lại quyền không tự publish hồ sơ hoặc tự khôi phục grant cũ.

## Export và deletion

[users/routes.py](../../backend/app/modules/users/routes.py) nhận export scopes: `account`, `memories`, `moods`, `consents`, `social`. AI conversation có endpoint export riêng. Export cần ownership/reauthentication theo route, output được quản lý với expiry; không ghi artifact cá nhân vào repository.

Deletion scopes: `memories`, `moods`, `all_private`, `account`. Private profile notes were retired in migration `0020_private_profile_retirement`; approved AI memories remain separate records. Request tạo `DataJob`; response accepted chưa phải toàn bộ dữ liệu đã xóa. Client đọc job status. Account deletion có provider/DB steps trong [lifecycle.py](../../backend/app/modules/users/lifecycle.py), dùng gate ngăn truy cập trong khi chờ.

Không đồng nhất xóa trong active database với xóa backup, provider logs hoặc copy ngoài hệ thống. Restore cần áp dụng tombstone/revocation trước khi mở traffic; không restore temporary raw context.

## Retention và background tasks

[main.py](../../backend/app/main.py) chạy vòng sweep mỗi giây: RAM cleanup, export expiry, deletion jobs, due activity transitions; khoảng mỗi phút chạy DB retention/accounting recovery. Embedding worker có vòng riêng. Mỗi lần dọn có batch bounds; nhiều bản ghi hết hạn có thể cần nhiều vòng.

| Loại dữ liệu | Quy tắc đáng chú ý | Nguồn |
| --- | --- | --- |
| Temporary conversation | 24 giờ idle, mất khi restart | `ai/store.py` |
| Saved chat | Hiệu lực 1–30 ngày, mặc định 30; code clamp `min(CHAT_RETENTION_DAYS, 30)` dù Settings nhận 1–90 | `ai/persistence.py`, chat routes |
| Mood | Cửa sổ 90 ngày local theo timezone owner | `jobs/retention.py`, mood routes |
| Human messages | 90 ngày | `jobs/retention.py`, social routes |
| Terminal usage/run metadata | Dọn sau 90 ngày khi đủ điều kiện | `jobs/retention.py` |
| Candidate ref | Hết hạn dùng sau 15 phút; cleanup sau expiry + 24 giờ | social routes, retention |
| Idempotency receipts | Dọn bản ghi quá 24 giờ | `jobs/retention.py` |
| Activity responses/terminal sessions | 90 ngày, mốc response submit/session end | `jobs/retention.py` |
| Report/moderation decisions | Cleanup theo mốc 365 ngày | `jobs/retention.py` |

Các mốc cleanup không phải SLA physical erasure. Proposal expiry/purge do memory module quản lý; xem code khi thay TTL, không kéo dài implicit bằng UI polling.

## Hoạt động chung

[machine.py](../../backend/app/modules/activities/machine.py) là state machine thuần: nhận state + command + server time, trả state mới hoặc lỗi/NoChange. Route/service chịu trách nhiệm load/lock/validate/persist và connection watermark. `projection.py` chỉ tiết lộ thông tin mà viewer có quyền xem; đáp án peer không được lộ trước điều kiện reveal.

| Kind | Nội dung / thời gian |
| --- | --- |
| `icebreaker` | 3 round, nội dung versioned, chờ reciprocal answer/reveal |
| `coop_quiz` | 5 round, tính điểm chung, không thi với peer |
| `focus` | Kế hoạch 25/5, 15/3 hoặc 50/10 phút; tối đa 4 cycles |

Invite TTL 10 phút. Icebreaker/quiz idle TTL 24 giờ; focus có deadline/pause/join rules riêng trong handler. `FOCUS_TEST_PLAN_SECONDS` chỉ dùng khi APP_ENV=test. Block/end/consent restriction/deletion gọi abort hooks; không để activity tiếp tục khi pair mất quyền.

## Identity reveal và moderation

IdentityField tách khỏi public matching payload. Reveal request/grant cho phép đọc một trường theo owner decision/version; revoke chặn đọc lại. Alias của peer không phải identity field đã được chia sẻ.

Reports dùng evidence do backend kiểm tra quyền và reference; staff queue có claim/resolve và audit actions. [staff.py](../../backend/app/modules/moderation/staff.py) đọc role mỗi request, yêu cầu reauth trong 12 giờ và global admin flag. Enforcement có thể hạn chế social/tạm khóa tài khoản; UI không tự sửa role hoặc thời hạn.

Test liên quan: `test_data_lifecycle.py`, `test_lifecycle.py`, `test_retention.py`, `test_privacy_lifecycle.py`, `test_activity_lifecycle.py`, `test_enforcement.py`, `test_moderation_admin.py`. Xem tên test thực tế trong `backend/tests/` khi chọn targeted run.
