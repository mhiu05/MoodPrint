# Runtime, tools và giao thức AI

## Luồng một lượt

1. UI đọc `/session`, `/bots`, `/ai/preferences`; capability và consent được trình bày riêng.
2. `POST /ai/conversations` tạo temporary hoặc persistent conversation theo capability/preference. Người dùng sở hữu conversation; temporary conversation còn ràng buộc session trong store.
3. `POST /ai/conversations/{conversation_id}/messages` mang `text`, `clientMessageId`, `expectedConversationVersion`, `moodScope` tùy chọn. Route xử lý idempotency, stale version, admission và run metadata; đây là operation khởi tạo run.
4. API trả `runId`, `conversationId`, version và `eventsUrl`. `AiRuntime.drive()` xây context, chọn memory/tools rồi gọi `SdkProvider`.
5. Quyền được kiểm tra lại khi chạy, khi dùng tool và trước khi đưa kết quả vào trạng thái thành công. Thay đổi `data_version`, session hay consent có thể làm run bị dừng.
6. Persistent result chỉ được coi là hoàn tất khi xử lý lưu trữ thành công. Client cần kết quả validated và terminal receipt.

Nguồn: [chat_routes](../../backend/app/ai/chat_routes.py), [runtime](../../backend/app/ai/runtime.py), [persistence](../../backend/app/ai/persistence.py).

## Admission và provider budgets

| Giới hạn | Giá trị hiện tại | Nguồn |
| --- | --- | --- |
| AI requests/user/minute | Mặc định 20, cấu hình 1–120 | `Settings.ai_requests_per_minute` |
| Concurrent runs/user | Mặc định 2, cấu hình 1–5 | `Settings.ai_user_concurrency` |
| Global concurrency | Mặc định 50, cấu hình 1–100 | `Settings.ai_global_concurrency` |
| Daily turns/user | Mặc định 60; ngày Asia/Bangkok | `Settings.ai_daily_turns_per_user` |
| Runtime timeout | Mặc định 30 giây, cấu hình 1–120 | `Settings.ai_timeout_seconds` |
| Provider timeout | 30 giây trong wrapper hiện tại | `RUN_TIMEOUT_SECONDS`, `ModelSettings` |
| Model calls / tool calls | Tối đa 3 / 2 cho một lượt | `_BudgetHooks`, runtime tool counter |
| Provider output token limit | 1.200 | `ModelSettings.max_tokens` |
| Conversation RAM TTL | 86.400 giây idle | `ConversationStore` |
| Temporary conversations | Tối đa 1.000 toàn store, 10/user | `ConversationStore.create` |

Timeout runtime và provider là hai boundary; tăng setting runtime không tự tăng hard limit của provider. Global daily budget chỉ có hiệu lực khi accounting bật; `warn_unenforced_budget()` cảnh báo nếu đặt budget mà tắt accounting. Quota/admission vẫn cần thiết khi accounting tắt.

## Chính sách provider

[SdkProvider](../../backend/app/ai/provider.py) tạo `Agent` theo bot, `Runner.run_streamed(max_turns=3)` và output type Pydantic. SDK stream được tiêu thụ trong server, không chuyển raw token delta hoặc tool result sang browser. Cấu hình `store=False`, `parallel_tool_calls=False`, `max_retries=0`, tắt tracing và sensitive tracing.

Output thường là `AiOutput`: `text` 1–6.000 ký tự, tối đa 3 card thuộc `navigate_bot`, `mood_form`, `discovery`. Guardrail `_no_unreceipted_claim` bắt một số câu khẳng định đã lưu/gửi khi không có receipt; đây là regex hẹp, không phải bộ phân loại an toàn toàn diện. Với mood analysis có scope, provider dùng `MoodAnalysisPlan`, backend render bằng evidence đã xác thực.

## Tools và hành động được duyệt

`propose_memory` chỉ tạo đề xuất ngắn (tối đa 120 ký tự sau trim), trả status `proposed` và proposal ID/version. Đề xuất chưa phải ghi nhớ đã duyệt. Người dùng xem/sửa/xác nhận qua API riêng; endpoint confirm kiểm tra quyền/version/consent hiện tại.

`read_mood_summary` chỉ cấp cho Nhịp khi người dùng chọn phạm vi ngày. Arguments phải là object rỗng; model không chọn owner, ngày hoặc nguồn dữ liệu. Tool trả điểm/thống kê trong scope, không trả ghi chú riêng tư. Runtime ghi source state và evidence; không diễn giải lỗi tool như nguồn dữ liệu hợp lệ.

## SSE và terminal states

Envelope `AIEvent` có `version="ai-events-v1"`, `seq` dạng chuỗi số dương, `type`, `data`. Dùng chuỗi để không mất độ chính xác số lớn ở JavaScript.

Hai phiên bản giao thức trên cùng endpoint `GET /api/v1/ai/runs/{run_id}/events`:

- **v1 (mặc định, không có query):** `final.data = {text, cards}`; khi lượt có nhiều bubble (`AI_MULTI_MESSAGE_ENABLED`), text là các bubble nối bằng `"\n\n"` (≤ 6.000 ký tự) và cards nối theo thứ tự. Lượt một bubble giống hệt byte-for-byte trước đây.
- **v2 (`?protocol=2`):** mọi event có `version="ai-events-v2"`; `final.data = {partCount, messages: [{messageId, partIndex, text, cards}]}` theo thứ tự bubble, `messageId` là id đã lưu (hoặc id đã publish trong RAM cho chat tạm). Persistent replay vẫn cố định seq 1–3, `afterSeq > 3` → `409 CURSOR_GAP`.

Mọi bubble của một run được ghi trong cùng transaction chuyển run sang `completed`, nên không có trạng thái "đã hiện một phần".

| Event | Ý nghĩa đối với client |
| --- | --- |
| `progress` | Thông tin hoạt động, chưa có câu trả lời thành công |
| `final` | Output hoàn chỉnh đã validate; client buffer |
| `completed` | Xác nhận terminal thành công; cho phép commit final vào UI |
| `failed` | Terminal lỗi, hiển thị thông báo công khai theo allowlist |
| `cancelled` | Terminal bị hủy; không tự gửi lại tin |

[consumeAIEvents](../../frontend/src/api/stream.ts) chỉ chấp nhận events URL cùng `/api/v1/ai/runs/.../events`, content type SSE, đúng version và sequence liên tục. Duplicate seq được bỏ qua; gap, card lạ, final rỗng, output field lạ hoặc EOF trước completed là lỗi. Buffer giới hạn 1.000.000 ký tự.

Cancel là thao tác server (`POST /ai/runs/{run_id}/cancel`); hủy fetch chỉ đóng stream đọc, không chứng minh model đã dừng. Sau mất mạng/timeout, tải lại trạng thái trước khi tạo lượt mới để tránh gọi model lặp. Startup recover đánh dấu interrupted, không replay cuộc gọi provider.

## Kiểm tra khi thay đổi

Chạy `test_sdk_adapter.py`, `test_context_selection.py`, `test_scoped_mood_tool.py`, `test_mood_evidence_runtime.py`, `test_privacy_lifecycle.py` cùng unit test `src/api/stream.test.ts`. Toàn bộ lệnh và phân tầng test ở [development](../development.md), [evaluation](evaluation.md).
