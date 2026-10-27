# API, lỗi và transaction

## Hợp đồng

Base path `/api/v1`. Python DTO kế thừa `DTO` dùng camelCase alias, validation và quy tắc schema trong [contracts.py](../../backend/app/contracts.py). [OpenAPI snapshot](../../backend/openapi.json) được export offline; [API inventory](api-reference.md) liệt kê method/path và operation ID. Production tắt `/docs`, `/redoc`, `/openapi.json` public.

Ví dụ lỗi nghiệp vụ:

```json
{"error":{"code":"STALE_VERSION","message":"Dữ liệu đã thay đổi.","retryable":false,"requestId":"synthetic-request-id"}}
```

`DomainError` và [install_errors](../../backend/app/core/errors.py) chuẩn hóa response. Request ID gắn vào `X-Request-ID`. Tránh đưa thông báo gốc từ database/provider vào UI hoặc log. Một số lỗi transport/validation có status riêng, không mặc định tất cả lỗi là retryable.

| Status | Cách hiểu thường gặp |
| --- | --- |
| 401 | Chưa có/mất phiên; một số operation cần reauthentication |
| 403 | CSRF/origin, eligibility, consent hoặc quyền không đủ |
| 404 | Resource không thấy/không thuộc quyền hoặc feature admin tắt |
| 409 | Version/state/context thay đổi hoặc operation conflict |
| 410 | Conversation/reference hết hạn theo operation |
| 413 / 422 | Body quá lớn / dữ liệu không hợp lệ |
| 429 | Admission, quota, concurrency hoặc rate limit |
| 503 | Database/provider/capability chưa sẵn sàng |

## Authenticated writes

Client gửi cookie same-origin, `X-CSRF-Token` và `Idempotency-Key`. `require_actor` kiểm tra app session, user status/auth version và live provider session. `transaction()` mở async session + database transaction, khóa/kiểm tra actor. Purpose gates được gọi trong nghiệp vụ, không chỉ ở dependency ngoài cùng.

`previous_receipt()` tra theo user/operation/key và digest payload canonical. Replay cùng operation/key/payload trả receipt cũ; dùng key cũ cho payload khác bị từ chối. `save_receipt()` được ghi cùng transaction với thay đổi nghiệp vụ. Chỉ operation có áp dụng helper mới có semantics này; header tự nó không đảm bảo idempotency.

Version fields (`expectedVersion`, `expectedConversationVersion`, draft/published versions) phải đến từ lần đọc mới nhất. Khi conflict, tải lại state rồi để người dùng xem/xác nhận; không retry bằng cách đoán version kế tiếp.

## Locking và concurrency

Ordinary user transaction khóa account gate trước resource. Social pair transaction khóa **users theo thứ tự UUID → pair → resource** để reciprocal writes dùng cùng thứ tự. Discovery scan trước, sau đó lấy gates theo canonical order và recheck shortlist dưới lock trước mint candidate ref.

Read polling có thể `lock=False` để không tranh chấp writer, nhưng vẫn chạy live-policy checks. Unique/check constraints là lớp bảo vệ cuối cho pair, message ID/sequence và activity state; không thay SQL lock bằng state RAM hoặc kiểm tra UI.

Nguồn: [security.py](../../backend/app/core/security.py), [social service](../../backend/app/modules/social/service.py), [retrieval](../../backend/app/modules/social/retrieval.py).

## Streaming và giới hạn

AI SSE dùng endpoint `/ai/runs/{run_id}/events`; social SSE `/connections/{connection_id}/events`. Cả hai cần actor hiện hành. AI event protocol và buffering khác social watermark; xem [agents/runtime](../agents/runtime.md), [frontend data flow](../frontend/data-flow.md).

[BodyLimitMiddleware](../../backend/app/core/body_limit.py) xử lý giới hạn body kể cả streaming/chunked request. Mức mặc định 65.536 byte; voice 3.000.000 byte. Middleware còn kiểm tra Content-Length. API response no-store; hashed assets được immutable cache. CSP, HSTS production và microphone policy nằm trong composition root/proxy configuration.

## Quy trình thay đổi endpoint

1. Xác định actor/purpose/ownership và state transition cần bảo vệ.
2. Viết DTO và test cho success, 401/403, cross-user access, stale version, replay/conflict và revoke/race nếu có.
3. Implement transaction nhỏ, không gọi provider chậm trong lock nếu không cần.
4. Export OpenAPI, generate TypeScript, kiểm tra drift và frontend caller.
5. Cập nhật API inventory cùng trang nghiệp vụ; chạy pytest + typecheck/build + browser flow liên quan.
