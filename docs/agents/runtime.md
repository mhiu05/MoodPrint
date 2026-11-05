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
- **v2 (`?protocol=2`):** mọi event có `version="ai-events-v2"`; `final.data = {partCount, messages: [{messageId, partIndex, text, cards}]}` theo thứ tự bubble, `messageId` là id đã lưu (hoặc id đã publish trong RAM cho chat tạm). Persistent replay cố định seq 1–3, `afterSeq > 3` → `409 CURSOR_GAP` (khi `AI_COLLABORATION_ENABLED`, v2 có thể có tới 5 event — xem [Trợ lý phối hợp](#trợ-lý-phối-hợp-phase-2)).

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

## Lời hỏi thăm (run chủ động)

Run `origin='proactive'` do service `proactive` tạo khi lịch người dùng tự hẹn đến hạn ([operations](../backend/operations.md#lời-hỏi-thăm-service-proactive)). Không có `Actor`, session, tin `self` hay transcript: `SdkProvider.run_proactive` nhận **một** input item dữ liệu do code dựng (`Dữ liệu cho lời hỏi thăm …`), không tool, tracing tắt, `store=False`, `max_turns=2`, timeout 30 s, guardrail claim như chat. Prompt là lớp runtime `PROACTIVE_*` (`proactive-2026-11-a1`) nối sau `instructions(bot)` đã đóng băng. Output `ProactiveReply` (1–3 bubble, ≤ 1.200 ký tự; Nhịp thêm `source_entry_ids`, Rủ Rê thêm `challenge_kind`) rồi qua validator nghiệp vụ (≤ 1 câu hỏi, không link, card theo trợ lý, Nhịp không nói "hôm qua" khi không có entry, ID nguồn phải thuộc digest, Cầu Nối không phần trăm/"đã kết nối"). Quyền được kiểm ở E1, trước mỗi model request và lại dưới owner lock khi publish; publish đặt `conversation_id` + `completed` trong **một** UPDATE. Quota người dùng (lượt/ngày, rate, concurrency) chỉ đếm `origin='user'`; trần toàn cục và ngân sách ngày đếm cả hai, lời hỏi thăm dừng ở `PROACTIVE_BUDGET_SHARE`. `GET /ai/runs/{id}/events` của run chủ động trả 404 — tin xuất hiện qua `GET /ai/conversations/{id}` và `/ai/inbox`.

## Trợ lý phối hợp (Phase 2)

`CollaborationCoordinator` ([coordinator.py](../../backend/app/ai/collaboration/coordinator.py)) là lớp định tuyến bằng code, **không** phải agent hay trợ lý thứ sáu (ADR-09). Trong `drive()`, ngay trước `provider.run_reply`, `AiRuntime.consult()` chạy luật thuần R1/R3/R4 ([policy.py](../../backend/app/ai/collaboration/policy.py)) trên tin hiện tại; không khớp → không truy cập DB, không call thêm. Khớp → dưới owner lock: kiểm quyền #1 (cờ + cohort, tài khoản 18+, cạnh bật trong `ai_sharing_permissions`, journal consent cho cạnh năng lượng, cap/ngày, ngân sách, thời gian còn lại ≥ timeout + 15 s, trần đồng thời, không distress), đọc dữ liệu duy nhất cạnh được phép (R1: ≤ 3 entry `saved` 2 ngày local), ghi receipt `authorized` + run con. Specialist chạy `SdkProvider.run_specialist`: instructions theo mục đích (không persona), `tools=[]`, `max_turns=1`, `_BudgetHooks(model_limit=1, tool_limit=0)`, kiểm quyền #2 trước request, tracing tắt, `store=False`. Output qua schema rồi tối thiểu hóa (không link, @, số điện thoại, tên trợ lý viết hoa, "nhật ký", thuốc, claim hành động; ID nguồn ⊆ ID đã cấp). Primary nhận `PrimaryBrief`: giá trị đóng vào instructions, văn bản specialist là **một** input item dữ liệu có nhãn ngay trước tin mới nhất. Khi publish (cùng transaction với bubble): kiểm quyền #3 + revision entry → `ai_message_sources` (R1) → `used_in_reply=true`. Lỗi tùy chọn → câu trả lời đơn; thu hồi/hủy → lượt kết thúc như Phase 1; primary lỗi → `discarded`. R2 chạy giữa E2 và E3 của executor proactive và xác nhận ở E5 (thu hồi → job `cancelled`, entry đổi → `retry(source_changed)`).

**SSE v2 khi cờ bật:** danh sách event của run đã lưu là hàm xác định, chỉ tiến, của DB: `progress {}` → `progress {activity:"consulting", companion}` (có receipt không `denied`) → `progress {activity:"composing"}` (receipt đã kết thúc) → `final` (+`collaboration`: template hoặc `null`) → `completed`; tối đa 5 event (`afterSeq ≤ 5`). v1 và cờ tắt giữ nguyên dạng Phase 1. Client chỉ nhận `{}` hoặc đúng hai dạng progress trên và một `collaboration` hợp lệ (≤ 200 ký tự, cạnh allowlist); khung `event: revoked` là dừng đã xác nhận. Chat tạm (không lưu) không phối hợp.

## Kiểm tra khi thay đổi

Chạy `test_sdk_adapter.py`, `test_context_selection.py`, `test_scoped_mood_tool.py`, `test_mood_evidence_runtime.py`, `test_privacy_lifecycle.py` cùng unit test `src/api/stream.test.ts`. Toàn bộ lệnh và phân tầng test ở [development](../development.md), [evaluation](evaluation.md).
