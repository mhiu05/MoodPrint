# 03 — Kiến trúc điều phối thông minh (Gate B)

Áp dụng cho **lượt chat 1:1 với Điều phối** trong hội thoại đã lưu của tài khoản đã đăng ký, đủ 18+, khi `AI_THREE_AGENT_EXPERIENCE_ENABLED`, `AI_SMART_ORCHESTRATION_ENABLED`, `AI_MULTI_MESSAGE_ENABLED` đều bật (production còn cần accounting). Mọi trường hợp khác: trả lời đơn như Phase 1.

## 1. Luồng một lượt

```
drive(run)                                  # runtime.py, như Phase 1: khóa owner, chiếu ngữ cảnh, ký context
 └─ orchestrate(run, c, history)            # app/ai/orchestration/workflow.py
     1. triage(latest_text)  ── pure ──►  "direct" ─────────────────────────────┐ (0 lời gọi thêm)
     2. grants = live_grants() dưới khóa owner (1 giao dịch ngắn)                │
        nếu không cạnh nào bật / không đủ điều kiện ─────────────────────────────┤
     3. plan = planner LLM (child run 'agent', 1 lời gọi, structured output)      │
     4. decision = policy.validate(plan, grants, counters)  ── pure ──           │
        workflow ∈ {direct, consult, handoff}; phần bị từ chối ghi lý do         │
     5. ghi step 'plan' (content-free) ; nếu decision.direct ────────────────────┤
     6. Runner.run_streamed(Điều phối,                                            │
           tools = [nhatky.as_tool(..), hoatdong.as_tool(..)]  (is_enabled = decision)
           handoffs = [handoff(nhatky|hoatdong, input_filter=strict, is_enabled = decision)])
        ├─ consult: SDK gọi tool ⇒ wrapper mở step + child run (khóa owner) ⇒ nested run SDK
        │           ⇒ extractor kiểm kiểu, tối giản ⇒ đóng step ⇒ Điều phối soạn câu trả lời
        └─ handoff: SDK gọi transfer_to_* ⇒ on_handoff mở step + child run ⇒ input_filter dựng
                    lại input (allowlist) ⇒ chuyên gia trả lời lượt này (last_agent)
     7. publish (khóa owner): kiểm quyền #3, nguồn nhật ký, used_in_reply, ghi bubbles
        dưới run của người nói thật (main run hoặc child run của handoff) ◄────────┘
```

## 2. Fast path (không gọi planner)

`orchestration/triage.py::triage(text) -> Literal["direct","plan"]` là hàm thuần trên tin hiện tại (đã gập dấu):

- `direct` khi: tin rỗng/ngắn chỉ gồm chào hỏi, cảm ơn, tán gẫu (`chao|hi|alo|cam on|ok|hihi|haha`…), hoặc không có tín hiệu nào dưới đây.
- `plan` khi có tín hiệu nhờ chuyên gia: nhật ký/ghi chép/đã viết/nhìn lại tuần/cảm xúc tuần/thói quen; hoạt động/kế hoạch/lên lịch/thử thách/học/cuối tuần/gợi ý việc; hoặc tín hiệu chuyển người (`noi chuyen (truc tiep )?voi`, `chuyen (sang|cho)`, `de .* tra loi`, tên trợ lý chuyên trách).
- Distress (`proactive/safety.distress_screen`) ⇒ `direct` (Điều phối trả lời một mình, không chuyển dữ liệu).

Thêm một cổng rẻ trước planner: nếu người dùng chưa bật **cạnh nào** liên quan, không gọi planner. Vì vậy người chưa opt-in không tốn thêm lời gọi.

## 3. Smart path — planner có cấu trúc

`orchestration/plan.py::OrchestrationPlan` (Pydantic, `extra="forbid"`, strict JSON schema):

| Trường | Kiểu | Ghi chú |
| --- | --- | --- |
| `intent` | enum `chat, reflect_journal, plan_activity, reflect_then_plan, talk_to_specialist, other` | |
| `workflow` | enum `direct, consult, handoff` | |
| `primary_agent` | literal `dieuphoi` | luôn là Điều phối ở 1:1 |
| `specialists` | list enum `nhatky, hoatdong` (≤ 2, không trùng) | consult |
| `handoff_target` | enum `nhatky, hoatdong` \| null | chỉ khi `workflow=handoff` |
| `subtasks` | list `{agent, task: enum, focus: str ≤ 120}` (≤ 2) | `task ∈ summarize_recent_entries, find_patterns, suggest_activities, break_down_goal` |
| `data_categories` | list enum `journal_entries, mood_scores, conversation_goal, time_budget, energy_hint` | chỉ là *yêu cầu*; policy cắt theo cạnh |
| `context_refs` | list enum `latest_message, recent_turns` | không bao giờ là ID dữ liệu |
| `expected_output` | enum `answer, plan, reflection, list_of_options` | |
| `confidence` | float 0–1 | |
| `fallback` | enum `answer_directly, ask_clarifying_question` | |

Planner nhận: tin mới nhất + tối đa 2 lượt gần nhất đã được chiếu cho Điều phối (đã qua `model_messages`, không nhật ký), và **danh sách khả năng hiện có** (enum, không dữ liệu). Không nhận nhật ký, ghi nhớ hay tên người khác. `reasoning.effort=low`, `max_tokens=500`, timeout 8 s, không retry, tracing tắt, `store=False`. Lỗi/timeout/output sai ⇒ fallback `direct` (ghi `plan` step `failed`).

## 4. Policy (thuần, không I/O) — `orchestration/policy.py`

`validate(plan, grants, counters) -> Decision` theo thứ tự cố định: cấu trúc → an toàn → đồng ý → dữ liệu → chi phí.

| Kiểm tra | Từ chối với lý do |
| --- | --- |
| cờ/cohort, tài khoản đã đăng ký 18+, hội thoại đã lưu | `feature_off`, `ineligible_account`, `ephemeral` |
| độ sâu ≥ 1, đã điều phối trong lượt | `depth`, `already_orchestrated` |
| distress trong tin hiện tại; người dùng từ chối đọc nhật ký | `distress`, `journal_refused` |
| cạnh chưa bật (`dieuphoi_consult_nhatky`, `dieuphoi_consult_hoatdong`, `dieuphoi_handoff_nhatky`, `dieuphoi_handoff_hoatdong`) | `edge_disabled` |
| consult Nhật ký cần `journal_context_enabled` | `journal_consent_off` |
| `confidence < 0.55` với handoff ⇒ hạ xuống direct | `low_confidence` |
| số chuyên gia > `AI_ORCHESTRATION_MAX_SPECIALISTS` (2) | cắt danh sách |
| hạn mức ngày (`AI_ORCHESTRATION_DAILY_CAP`), ngân sách toàn cục (`budget_share`), thời gian còn lại, capacity | `daily_cap`, `budget`, `time_budget`, `capacity` |
| `data_categories` ngoài allowlist của cạnh | loại bỏ hạng mục (không từ chối cả bước) |

Kết quả `Decision{workflow, consult: tuple[Agent], handoff: Agent|None, denied: dict, allowed_data: dict}`. Đây là đầu vào duy nhất của `is_enabled` cho tool/handoff.

## 5. Giới hạn cưỡng chế

| Giới hạn | Giá trị | Nơi cưỡng chế |
| --- | --- | --- |
| Độ sâu ủy quyền | 1 (chuyên gia không có tool gọi trợ lý khác, không handoff tiếp) | cấu hình agent + policy |
| Lời gọi chuyên gia / lượt | ≤ 2 consult **hoặc** 1 handoff | policy + `is_enabled` + bộ đếm wrapper |
| Lời gọi model / workflow | ≤ 7 (planner 1 + Điều phối ≤ 3 + chuyên gia ≤ 3) | `WorkflowBudget` dùng chung trong mọi hook |
| Lời gọi model / run | ≤ 3, tool ≤ 2 (CHECK `ai_usage` không đổi) | hook theo agent ghi usage vào run riêng |
| Thời gian | timeout lượt 30 s (Phase 1) ; consult 10 s ; planner 8 s | `asyncio.timeout` + `ModelSettings.timeout` |
| Hạn mức ngày bước chuyên gia | 20/người dùng (cấu hình) | policy, đếm `ai_orchestration_steps` |
| Ngân sách toàn cục | dừng ủy quyền khi đã chi ≥ `budget_share` × ngân sách ngày | policy |
| Retry | 0 (provider) | `ModelRetrySettings(max_retries=0)` |
| Trùng lặp | unique `(workflow_run_id, kind, target_bot, ordinal)` + idempotency lượt Phase 1 | DB |
| Hủy | hủy run cha ⇒ `CancelledError` lan vào nested run; wrapper đóng step `cancelled` | wrapper + `discard` |

## 6. Thất bại và fallback

- Planner lỗi ⇒ trả lời đơn (Điều phối không tool).
- Consult lỗi/timeout/output sai ⇒ tool trả cho Điều phối một chuỗi cố định "chưa lấy được ý kiến…", step `failed|timeout`, Điều phối vẫn trả lời; UI không hiện dòng phối hợp cho bước đó.
- Handoff bị thu hồi giữa chừng (on_handoff kiểm lại thất bại) ⇒ lượt kết thúc `CONTEXT_CHANGED` như Phase 1 (không có đường "lén" chuyển).
- Thu hồi quyền / xóa tài khoản giữa lượt ⇒ monitor 0,5 s hủy run (Phase 1), mọi step mở được đóng `cancelled`, không publish.

## 7. Tương thích

- Cờ B tắt: Điều phối trả lời đơn (như Mây Phase 1), không planner, không tool chuyên gia. R1–R4 của Phase 2 chỉ áp dụng cho trợ lý cũ khi cờ A tắt.
- SSE v1: lượt có handoff vẫn là một `final {text,cards}`; v2 thêm `speaker` và `steps` (xem [04](04-as-tool-and-handoff-contracts.md) §5).
