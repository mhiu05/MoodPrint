# Session, API client và state frontend

## Bootstrap

`SessionRoot` tạo `ApiClient`, tải `/session`, validate capability/consent và đặt CSRF token trong bộ nhớ. `useSession()` cung cấp session/api/refresh cho màn hình. Khi authenticated request trả 401 thật sự, client gọi `onUnauthorized` để UI quay về auth flow. Public auth endpoints và `REAUTH_REQUIRED` có cách xử lý riêng, không mặc định coi là mất toàn bộ session.

`useResource<T>(path, enabled)` quản lý load/data/error/reload và AbortController. `enabled=false` tránh fetch khi feature chưa được phép. Đây là hook cục bộ, không phải cache chuẩn hóa toàn ứng dụng. Sau mutation cần refresh đúng resource/session; không tự xem state optimistic là receipt đã commit.

## HTTP transport

[client.ts](../../frontend/src/api/client.ts) luôn gọi `/api/v1${path}` với credentials same-origin, no-store và redirect error. Timeout 20 giây; abort từ caller được nối vào controller. Server vẫn có thể đã commit khi client timeout.

| Request | Client behavior | Server expectation |
| --- | --- | --- |
| GET | Accept JSON, không thêm idempotency | Auth/ownership vẫn được route kiểm tra |
| Auth public write | `publicWrite=true` | Auth endpoint kiểm tra origin/rate limit |
| Authenticated write | CSRF + key theo method/path/body | Operation kiểm tra purpose/version và receipt |
| 4xx | Bỏ intent key | Kết quả từ chối rõ ràng; sửa dữ liệu/tải lại |
| Network/5xx | Giữ intent key | Retry cùng intent không gây lặp khi route hỗ trợ replay |
| Thành công/204 | Bỏ intent key, parse JSON hoặc undefined | UI dùng response làm kết quả chính thức |

Map intents giới hạn 50; session reset xóa CSRF và intents. Không lưu password, session token hoặc provider JWT vào browser storage. `ApiError` giữ status/code/message/Retry-After; fallback không hiển thị raw response body.

## Hợp đồng API

`api/contracts.ts` dùng kiểu từ `api/generated/schema.d.ts`. Khi sửa backend DTO/router, chạy:

```powershell
# repository root
Push-Location backend
uv run --locked python ../scripts/export_openapi.py
Pop-Location
Push-Location frontend
npm.cmd run contracts:generate
npm.cmd run typecheck
Pop-Location
git diff -- backend/openapi.json frontend/src/api/generated/schema.d.ts
```

Không sửa generated file bằng tay. TypeScript type không validate dữ liệu runtime; AI events được validate riêng vì là dữ liệu stream ngoài JSON response thông thường. Backend cũng inject schema `AIEvent`/`AiOutput` vào OpenAPI export.

## Hai loại stream

**AI:** `consumeAIEvents()` dùng fetch SSE, kiểm tra version/seq/fields/cards, buffer final đến `completed`. Xem [runtime protocol](../agents/runtime.md). Lost stream yêu cầu reconcile trạng thái, không tự gọi model lần nữa.

**Social:** [useConnectionEvents](../../frontend/src/features/real/social/useConnectionEvents.ts) cập nhật watermark/tín hiệu thay đổi của room; client đọc lại projection message/activity. [useSocialSummary](../../frontend/src/features/real/social/useSocialSummary.ts) phục vụ badge riêng của viewer. Read marker không phải read receipt công khai của peer.

## State của màn hình

Mỗi flow phải có loading, unavailable/error, empty và success. Discovery empty khác chưa có profile, chưa bật MATCH hoặc lỗi server. Conversation draft không đồng nghĩa message accepted. Form dùng version từ response mới nhất; 409 cần đọc trạng thái hiện tại thay vì tăng version giả.

Identity `displayName` là input, `gender` là select chuẩn hóa các nhãn Nam/Nữ/Khác trong UI hiện tại. Voice chép vào draft để người dùng xem trước, không tự gửi message. Quick starters chỉ xuất hiện trước user message đầu tiên và khi không loading/busy. Đây là hành vi của working tree được kiểm thử trong lần cập nhật tài liệu này.
