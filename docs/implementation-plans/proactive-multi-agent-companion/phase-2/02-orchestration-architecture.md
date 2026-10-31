# Phase 2 — 02. Kiến trúc điều phối

Quyết định: [ADR-09](../03-architecture-decisions.md#adr-09--mẫu-điều-phối-đa-agent-phase-2). Dữ kiện SDK: [02 §3](../02-openai-agents-sdk-research.md).

## 1. So sánh bốn phương án

| Tiêu chí | 1. Manager + `Agent.as_tool()` | 2. SDK Handoffs | 3. Code-driven, run riêng | 4. Hybrid (code quyết định + tool hẹp do model gọi) |
| --- | --- | --- | --- | --- |
| Privacy | Nested run nhận **cùng** `context.context` (`LiveRun` có `journal_evidence`, `sources`) → không cấp được principal hẹp | Mặc định chuyển **toàn bộ** lịch sử; input filter phải viết đúng tuyệt đối, `nest_handoff_history` không phải cơ chế che giấu | Specialist nhận `SpecialistContext` riêng và input do code dựng từ trường đã duyệt | Như 3 cho phần chạy; nhưng model chọn thời điểm gọi |
| Quyền tool | Specialist có thể có tool đọc dữ liệu dưới context cha | Agent nhận handoff có tool riêng nhưng thấy transcript cha | Tool/nguồn của specialist khai báo theo cạnh | Như 3 |
| Độ trễ | +1 vòng model (specialist) + model cha phải gọi tool rồi tổng hợp: ~+2 call | Chuyển agent trong cùng run; câu trả lời do agent đích viết: +0–1 call | +1 call specialist (không tool, `max_turns=1`), chạy **trước** primary | +1 call nhưng chỉ sau khi primary đã chạy 1 vòng: ~+2 call |
| Token | Lịch sử cha + mô tả tool + input/output nested | Toàn bộ transcript gửi cho agent mới | Input specialist nhỏ (~300–800 token) | Như 1 |
| Cô lập lỗi | Lỗi nested thành tool error → model cha có thể "đoán" thay | Lỗi agent đích là lỗi của cả lượt | Lỗi specialist → primary chạy một mình (fallback xác định) | Như 1 |
| Ai sở hữu câu trả lời | Primary | **Agent đích** (đổi persona trước mặt người dùng) | Primary | Primary |
| Kiểm toán | Chỉ biết qua hook/trace (đang tắt) | Như 1 | Receipt DB do coordinator ghi trước/sau | Như 3 |
| Tương thích runtime hiện tại | Phá `_BudgetHooks` (hooks nested = None), `max_turns` nested mặc định 10, vượt CHECK `ai_usage.requests_started <= 3` | Phá nguyên tắc "mỗi hội thoại một trợ lý"; output_type thay đổi theo agent đích | Khớp: thêm một bước trước `provider.run()` trong `drive()` và trong executor proactive | Cần tool mới cho model chat, khó dự đoán chi phí |
| Giải thích cho người dùng | Phải suy từ việc model có gọi tool | Khó (ai đang nói?) | Trực tiếp từ receipt | Từ receipt |

## 2. Khuyến nghị

**Chọn phương án 3: code-driven orchestration.** `CollaborationCoordinator` là **lớp định tuyến ẩn** trong backend — không phải agent, không có prompt, không hiển thị, không phải trợ lý thứ sáu. Nó:

1. Đánh giá luật xác định (§3) trên tín hiệu **đã có** (bot, intent từ `conversation_intent()`, khung proactive, quyền chia sẻ, số lượng dữ liệu cho phép), không gọi model để quyết định.
2. Ghi `ai_collaborations(status='authorized' | 'denied')` trước khi chạy.
3. Chạy specialist bằng `Runner.run` riêng: `Agent` của bot specialist với **instructions chuyên biệt cho mục đích**, `tools=[]`, `output_type` của cạnh, `max_turns=1`, `asyncio.timeout(8)`, `ModelSettings(max_tokens=300, store=False)`, tracing tắt, `_BudgetHooks` riêng ghi vào `ai_runs(origin='collaboration', parent_run_id=…)` + `ai_usage` riêng.
4. Validate output theo schema cạnh và chính sách tối thiểu hóa; tính `output_digest`.
5. Đưa kết quả vào primary dưới dạng **dữ liệu có cấu trúc** (§5), rồi primary chạy như bình thường.
6. Khi primary publish thành công → `used_in_reply=true`, `status='completed'`; nếu primary thất bại → `status='discarded'`.

Phương án 4 (hybrid) bị **hoãn**, không nằm trong Phase 2: thêm điểm quyết định không xác định và chi phí khó dự đoán; luật xác định đã phủ các trường hợp có giá trị.

## 3. Luật xác định

Mọi luật đều yêu cầu điều kiện chung **G**: `AI_COLLABORATION_ENABLED`, tài khoản `registered`, đủ tuổi AI, không `deletion_pending`, cạnh bật trong `ai_sharing_permissions`, chưa vượt 10 lần/ngày, ngân sách AI < 70 %, **không** khớp mẫu nguy cơ (`distress_screen` trên tin hiện tại), không phải run specialist (độ sâu 1), chưa nhờ trong lượt này.

| Rule | Ngữ cảnh | Điều kiện thêm | Cạnh | Ghi chú |
| --- | --- | --- | --- | --- |
| R1 | Chat với Rủ Rê | `conversation_intent == "activity"` **và** tin hiện tại khớp mẫu cá nhân hóa (`nhẹ nhàng\|hợp với mình\|đang mệt\|ít năng lượng\|hợp tâm trạng`) **và** `journal_context_enabled` **và** có ≥ 1 entry `saved` trong 2 ngày gần nhất (COUNT, không đọc nội dung) | `nhip_energy_for_rure` | Không có dữ liệu → không gọi (tránh call vô ích) |
| R2 | Lời hỏi thăm sáng của Rủ Rê | `journal_context_enabled` **và** có entry `saved` hôm qua | `nhip_energy_for_rure` | Ví dụ chuẩn của sản phẩm |
| R3 | Chat với Mây | `conversation_intent ∈ {support, practical}` **và** tin khớp một nhu cầu thói quen (`ngủ\|mất ngủ` → sleep, `căng thẳng\|áp lực` → stress, `tập trung` → focus, `uể oải\|thiếu năng lượng` → energy) | `nhip_habit_for_may` | Nhịp **không** đọc nhật ký ở cạnh này |
| R4 | Chat với Gương | `conversation_intent == "reflection"` **và** tin khớp "muốn thử/làm gì/gợi ý hoạt động" **và** trích được một `interest_tag` từ taxonomy đóng bằng regex trên tin hiện tại | `rure_activity_for_guong` | Không đọc memory |

Thứ tự đánh giá: luật đầu tiên khớp thắng; không bao giờ chạy hai specialist.

## 4. Luồng

### 4.1 Chat (R1)

```mermaid
sequenceDiagram
    participant UI
    participant RT as AiRuntime.drive (Rủ Rê)
    participant CO as CollaborationCoordinator
    participant DB
    participant SP as Specialist run (Nhịp)
    participant PR as Primary run (Rủ Rê)
    UI->>RT: POST message (như hiện tại)
    RT->>CO: evaluate(R1..R4) với tín hiệu đã có
    CO->>DB: owner lock: kiểm quyền cạnh + journal consent; insert ai_collaborations(authorized), ai_runs(origin=collaboration)
    CO-->>UI: SSE v2 progress {activity: consulting, companion: nhip}
    CO->>DB: đọc entry 2 ngày (owner lock), ghi provenance tạm
    CO->>SP: Runner.run(EnergyHintRequest), timeout 8 s
    SP-->>CO: EnergyHint {energy, timeBudgetMinutes, basis}
    CO->>DB: settle child usage; ai_collaborations.output_digest
    CO->>PR: input bổ sung: CollaborationInput (enum, không văn bản nhật ký)
    PR-->>RT: CompanionReply
    RT->>DB: publish: messages + ai_message_sources(từ specialist) + collaboration used_in_reply=true
    RT-->>UI: final {messages, collaboration: {summary, companions}} + completed
```

### 4.2 Lời hỏi thăm (R2)

Như 4.1 nhưng nằm trong E2–E4 của executor proactive ([phase-1/03 §6](../phase-1/03-proactive-scheduler-and-workers.md)): specialist chạy sau E2 (đọc nhật ký) và trước E3. Không có SSE; dòng cộng tác hiển thị khi người dùng mở hội thoại. Tin của Rủ Rê được stamp `proactive-journal-v1` với `ai_message_sources` của các entry Nhịp đã dùng → revalidation ADR-08 áp dụng nguyên vẹn.

## 5. Đưa kết quả specialist vào primary

| Loại trường | Kênh | Lý do |
| --- | --- | --- |
| Enum/số (E1 `energy`, `timeBudgetMinutes`) | Nối vào **instructions** của primary như một khối "Gợi ý từ Nhịp (đã kiểm): energy=low, timeBudgetMinutes=5" | Giá trị đóng, không thể chứa chỉ dẫn |
| Văn bản ngắn do specialist tạo (E2 `habitText`, E3 `activityText`) | Một input item dữ liệu có nhãn "dữ liệu, không phải chỉ dẫn" (JSON), sau lịch sử | Văn bản model tạo là bán tin cậy; giữ ở kênh dữ liệu |

Primary không được thấy: input của specialist, nhật ký, provenance, digest.

## 6. Giới hạn, timeout, fallback

| Giới hạn | Giá trị | Nơi kiểm |
| --- | --- | --- |
| Độ sâu | 1 (specialist không có coordinator) | `SpecialistContext.depth=1`; coordinator từ chối nếu `depth ≥ 1` |
| Lần nhờ / lượt | 1 | Unique `(primary_run_id, specialist_bot, purpose)` + cờ trong `LiveRun` |
| Model call specialist | 1 (`max_turns=1`, `_BudgetHooks(limit=1)`) | Hook + CHECK `ai_usage` của run con |
| Tool call specialist | 0 | `tools=[]` |
| Timeout specialist | 8 s (`AI_COLLABORATION_TIMEOUT_SECONDS`, 3–10) | `asyncio.timeout` |
| Thời gian còn lại cho primary | Nếu còn < 15 s trong ngân sách 30 s → bỏ qua phối hợp | Coordinator |
| Lần nhờ / ngày / user | 10 (`AI_COLLABORATION_DAILY_CAP`) | COUNT `ai_collaborations` theo ngày Asia/Bangkok (như quota hiện có) |
| Concurrency | Run con tính vào `ai_global_concurrency` | `admission` |

| Lỗi | Trạng thái receipt | Người dùng thấy |
| --- | --- | --- |
| Quyền bị từ chối/không còn | `denied` (`deny_reason`) | Câu trả lời đơn, không dòng cộng tác |
| Timeout | `timeout` | Như trên |
| Output không hợp lệ | `failed(invalid_output)` | Như trên |
| Primary thất bại sau khi phối hợp | `discarded` | Lỗi chuẩn của lượt (như hiện tại) |
| Người dùng tắt cạnh giữa lượt | `cancelled`; `data_version` tăng → lượt bị hủy | "Đã dừng phản hồi." như hiện tại |

## 7. Vị trí trong code

| Thành phần | File đề xuất |
| --- | --- |
| Ma trận cạnh + luật | `backend/app/ai/collaboration/policy.py` |
| Schema cạnh | `backend/app/ai/collaboration/contracts.py` |
| Coordinator | `backend/app/ai/collaboration/coordinator.py` |
| Specialist runner | `backend/app/ai/collaboration/specialist.py` (dùng `SdkProvider` client và model chung) |
| Tích hợp chat | `AiRuntime.drive()` — một lời gọi `await coordinator.maybe_consult(run, signals)` ngay trước `self.provider.run(...)` ([runtime.py:664](../../../../backend/app/ai/runtime.py#L664)) |
| Tích hợp proactive | `backend/app/ai/proactive/executor.py` giữa E2 và E3 |

Lý do không đặt trong `SdkProvider`: provider không giữ DB session/quyền; coordinator cần owner lock và receipt.
