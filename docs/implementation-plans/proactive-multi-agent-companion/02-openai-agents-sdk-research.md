# 02 — Nghiên cứu OpenAI Agents SDK

## 1. Phiên bản và phương pháp

| Hạng mục | Giá trị | Nguồn |
| --- | --- | --- |
| Pin trong repo | `openai-agents==0.24.0`, `openai==3.37.0` | [pyproject.toml](../../../backend/pyproject.toml), `backend/uv.lock` |
| Bản phát hành mới nhất trên PyPI (31/10/2026) | `0.24.0` (`info.version` của `https://pypi.org/pypi/openai-agents/json`) | WebFetch PyPI JSON |
| Model cấu hình | `OPENAI_MODEL=gpt-6-luna` (chỉ đọc tên model, không đọc secret); bảng giá nội bộ `RATES["gpt-6-luna"] = (100, 10, 500)` nano-USD/token | `backend/.env` (khóa không bí mật), [accounting.py:12-14](../../../backend/app/ai/accounting.py#L12) |

Phương pháp: đọc **mã nguồn SDK đã cài** (`backend/.venv/Lib/site-packages/agents/`, đúng 0.24.0) cho mọi khẳng định về hành vi; đọc tài liệu chính thức để đối chiếu hướng dẫn. Vì pin trùng bản mới nhất, **không khuyến nghị nâng cấp** trong Phase 1/2. Nhánh `main` trên GitHub có thể có thay đổi chưa phát hành; tài liệu này chỉ cam kết với 0.24.0.

Tài liệu chính thức đã đọc:

- Orchestration and handoffs — <https://developers.openai.com/api/docs/guides/agents/orchestration>
- Multi-agent (Python) — <https://openai.github.io/openai-agents-python/multi_agent/>
- Guardrails — <https://openai.github.io/openai-agents-python/guardrails/>
- Running agents — <https://openai.github.io/openai-agents-python/running_agents/>
- Tracing — <https://openai.github.io/openai-agents-python/tracing/>

## 2. Bảng năng lực

| Năng lực | SDK 0.24.0 hỗ trợ | API phù hợp | MoodPrint phải tự làm | Điểm tích hợp |
| --- | --- | --- | --- | --- |
| Định nghĩa agent | `Agent(name, instructions, model, tools, output_type, output_guardrails, model_settings, handoffs)` | Như hiện tại | Chọn instructions/tools theo bot và theo **origin** (user/proactive/specialist) | [provider.py:207-221](../../../backend/app/ai/provider.py#L207) |
| Runner + streaming | `Runner.run_streamed` → `RunResultStreaming.stream_events()`; `Runner.run` không stream | Giữ `run_streamed` cho chat (đã có `_cancel_and_drain`); dùng `Runner.run` cho specialist/proactive (không cần delta) | Không chuyển delta ra browser (nguyên tắc hiện có) | [provider.py:222-254](../../../backend/app/ai/provider.py#L222) |
| Structured output | `AgentOutputSchema`; strict JSON schema mặc định; validate bằng Pydantic, lỗi → `ModelBehaviorError` | `output_type=CompanionReply` (Pydantic) | Validator nghiệp vụ (tổng độ dài, số bubble, card, link, claim) ở backend | [schemas.py:26-28](../../../backend/app/ai/schemas.py#L26) |
| Agents as tools | `Agent.as_tool(tool_name, tool_description, custom_output_extractor, is_enabled, run_config, max_turns, hooks, failure_error_function, needs_approval, parameters, input_builder, …)` | **Không dùng trực tiếp** (xem §3.1) | Tự viết `FunctionTool`/bước code gọi `Runner.run` với context riêng | Phase 2 coordinator |
| Handoffs | `handoff(agent, input_filter, nest_handoff_history, is_enabled, on_handoff)`; mặc định agent nhận **toàn bộ** lịch sử | **Không dùng** cho hội thoại người dùng (xem §3.2) | — | — |
| Function tools | `@function_tool(..., failure_error_function, strict_mode, is_enabled, needs_approval, tool_input_guardrails, tool_output_guardrails, timeout, timeout_behavior)` | Giữ `FunctionTool` thủ công như hiện tại; có thể dùng `timeout=` cho tool đọc dữ liệu | Authorization sống trong tool (lock owner, data_version) | [runtime.py:395-499](../../../backend/app/ai/runtime.py#L395) |
| Guardrails | Input guardrail **chỉ** chạy với agent đầu tiên; output guardrail **chỉ** với agent tạo final output; tool guardrail bọc function tool, **không** áp dụng cho handoff, `as_tool()` không expose tool guardrail | Output guardrail cho mọi agent cuối (primary, specialist, proactive) | Validator backend sau khi SDK trả kết quả (không phụ thuộc guardrail chain) | [provider.py:55-65](../../../backend/app/ai/provider.py#L55) |
| Human approval | `needs_approval` + interruptions/`RunState` | **Không dùng** trong Phase 1/2 | Mọi hành động bền vững vẫn đi qua UI confirm (proposal) | [memory.py](../../../backend/app/ai/memory.py) |
| Run context | `RunContextWrapper[T].context` là object ứng dụng; không gửi cho model | Context riêng cho mỗi loại run: `LiveRun` (user), `ProactiveContext`, `SpecialistContext` | Context không chứa dữ liệu ngoài phạm vi được cấp | [runtime.py:50-84](../../../backend/app/ai/runtime.py#L50) |
| Sessions / conversation state | `Session`, `previous_response_id`, `conversation_id`, hoặc lịch sử thủ công | **Giữ lịch sử thủ công** (`store=False`, projection có stamp) | Không dùng server-managed state (chặn input filter, khó xóa) | [context.py](../../../backend/app/ai/context.py) |
| Tool concurrency | `ModelSettings.parallel_tool_calls` | Giữ `False` | — | [provider.py:214-220](../../../backend/app/ai/provider.py#L214) |
| Cancellation | `RunResultStreaming.cancel(mode="immediate" \| "after_turn")` | Giữ `immediate` + drain | Hủy proactive bằng `asyncio.timeout` + version check trước publish | [provider.py:112-118](../../../backend/app/ai/provider.py#L112) |
| Timeouts / max turns | `max_turns` (mặc định 10), `MaxTurnsExceeded`, `error_handlers={"max_turns": …}`; `ModelSettings.timeout`; `ToolTimeoutError` | `max_turns` 3 (chat), 2 (proactive không tool), 1–2 (specialist) | Budget tổng qua hooks dùng chung | [provider.py:46,164](../../../backend/app/ai/provider.py#L46) |
| Stream events | `RawResponsesStreamEvent`, `RunItemStreamEvent`, `AgentUpdatedStreamEvent` | Không phát ra client | SSE của MoodPrint chỉ phát trạng thái thật | [stream_events (installed)](https://github.com/openai/openai-agents-python) |
| Tracing | Bật mặc định; tắt bằng `set_tracing_disabled(True)`/`RunConfig.tracing_disabled`; `trace_include_sensitive_data` | Giữ tắt; nếu cần quan sát dùng **custom trace processor nội bộ** không chứa nội dung (Phase 2 tùy chọn) | Receipt content-free trong PostgreSQL thay cho trace | [provider.py:128,228](../../../backend/app/ai/provider.py#L128) |
| Hooks | `RunHooks.on_llm_start/on_llm_end/on_tool_start/on_tool_end/on_handoff/on_agent_start/on_agent_end` | Tái dùng `_BudgetHooks`; tạo một instance **chia sẻ** khi có specialist | Hooks chỉ cho side effect (đếm, revalidate), không phải cơ chế quyền chính | [provider.py:68-109](../../../backend/app/ai/provider.py#L68) |

## 3. Phát hiện đã xác minh trong mã nguồn SDK 0.24.0

### 3.1 `Agent.as_tool()` — vì sao không dùng nguyên bản

Đọc `agents/agent.py` (`def as_tool`, dòng 606 trong bản cài):

1. **Nested run chia sẻ context ứng dụng của cha.** Với `ToolContext`, SDK tạo `ToolContext(context=context.context, usage=context.usage, …)` — nghĩa là specialist nhận **cùng object** `LiveRun` (có `journal_evidence`, `sources`, `actor`). Không thể cấp cho specialist một principal hẹp hơn.
2. **Hooks mặc định `None`.** `Runner.run_streamed(..., hooks=hooks, …)` với `hooks` là tham số của `as_tool`; nếu không truyền, `_BudgetHooks` của run cha **không đếm** model call của specialist → vượt ngân sách 3 call mà không bị phát hiện.
3. **`max_turns` mặc định `DEFAULT_MAX_TURNS = 10`** (`run_config.py:45`) nếu không đặt.
4. Output mặc định là chuỗi (qua `custom_output_extractor`), tool guardrail không cấu hình được qua `as_tool()` (tài liệu Guardrails xác nhận).
5. Accounting: `ai_usage` có CHECK `requests_started <= 3` cho **mỗi run** ([models.py:233](../../../backend/app/infrastructure/database/models.py#L233)); gộp call của specialist vào run cha sẽ vi phạm ràng buộc DB.

Kết luận: chức năng "agent gọi agent" phải được **MoodPrint tự điều phối bằng code** (một `Runner.run` riêng, context riêng, hooks dùng chung, run/usage riêng). Chi tiết ở [phase-2/02](phase-2/02-orchestration-architecture.md).

### 3.2 Handoffs — rủi ro privacy

`agents/handoffs/__init__.py` (`class Handoff`): "By default, the new agent sees the entire conversation history." `nest_handoff_history` "is not a redaction mechanism". Server-managed conversations không hỗ trợ input filter. Agent nhận handoff **trở thành chủ của câu trả lời** (đổi persona trước mặt người dùng). Hai điều này mâu thuẫn với: (a) không chia sẻ toàn bộ hội thoại/nhật ký giữa bot, (b) mỗi hội thoại thuộc một trợ lý hiển thị.

### 3.3 Guardrails trong chuỗi agent

Theo tài liệu và mã: input guardrail chỉ chạy cho agent đầu, output guardrail chỉ cho agent cuối. Trong thiết kế code-driven, **mỗi run là một chuỗi độc lập** nên mọi agent (primary, specialist, proactive) đều có output guardrail của riêng nó — đây là lợi ích phụ của việc không dùng handoff.

### 3.4 `error_handlers` cho `max_turns`

`Runner.run_streamed(..., error_handlers: RunErrorHandlers | None)` có trong 0.24.0 (`run.py:290`, `run_error_handlers.py:50-53`). MoodPrint **không** dùng để tạo output thay thế từ SDK (output fallback phải do backend render từ template đã duyệt), nhưng có thể dùng để chuyển `MaxTurnsExceeded` thành mã lỗi có kiểm soát.

### 3.5 Structured output và giới hạn danh sách

`AiOutput.cards` đang dùng `Field(max_length=3)` và hoạt động với strict schema hiện tại; cùng cơ chế áp dụng cho `messages: list[Bubble] = Field(min_length=1, max_length=4)`. Pydantic validate lại sau khi SDK parse, nên ràng buộc vẫn có hiệu lực kể cả khi provider bỏ qua `maxItems`. Validator chéo trường (tổng ký tự, tổng card) chạy ở `model_validator`.

## 4. Áp dụng cho MoodPrint

| Nhu cầu | Cách làm khuyến nghị | Phần SDK dùng | Phần MoodPrint tự làm |
| --- | --- | --- | --- |
| P1.1 nhiều bubble | `output_type=CompanionReply` | Structured output | Validator, persist từng bubble, SSE v2 |
| P1.2 proactive | `Runner.run(agent, input=[system-built data message], context=ProactiveContext, max_turns=2, hooks=_BudgetHooks)` | Runner, output_type, output guardrail | Scheduler, job lease, quyền, truy xuất dữ liệu, publish |
| P1.3/P1.4 | — | — | Toàn bộ (lịch, read state) |
| P2.1 điều phối | Code-driven: coordinator quyết định theo luật | `Runner.run` cho specialist | Policy matrix, rule engine, receipts |
| P2.2 giao tiếp | Typed input/output Pydantic giữa các run | Structured output | Minimization, validation, provenance |
| P2.4 quan sát | Receipts trong DB; tùy chọn trace processor nội bộ content-free | `add_trace_processor` (tùy chọn) | Metric/log, không lưu nội dung |

## 5. Giới hạn và tình huống lỗi cần xử lý

| Tình huống | Hành vi SDK | Xử lý ở MoodPrint |
| --- | --- | --- |
| JSON không khớp schema | `ModelBehaviorError` | Run `failed` (chat) / job `retry` tối đa N lần (proactive) |
| Vượt `max_turns` | `MaxTurnsExceeded` | Như trên; không replay ngầm |
| Provider timeout | `ModelSettings.timeout` / `asyncio.timeout` | Mã `AI_TIMEOUT` (đã có trong [availability.py](../../../backend/app/ai/availability.py)) |
| Hủy giữa chừng | `cancel()` + drain | Proactive: không có UI hủy; hủy do version/consent đổi → kiểm trước publish |
| Output guardrail tripwire | `OutputGuardrailTripwireTriggered` | Chat: `failed`; proactive: `skipped` với lý do `guardrail` (không retry) |
| Tracing bật nhầm do default | Tracing mặc định bật | Giữ `set_tracing_disabled(True)` ở cả entry mới; test khẳng định `tracing` của fake model là disabled (đã có trong `ScriptedModel.calls[*]["tracing"]`, [fakes.py:56-101](../../../backend/tests/fakes.py#L56)) |

## 6. Nâng cấp

Không nâng cấp. Nếu sau này cần bản > 0.24.0: chạy `test_sdk_adapter.py`, `test_context_selection.py`, `test_journal_ai.py`, toàn bộ `tests/test_ai*.py`, fullstack với fake model, và một eval live có gate; kiểm lại 5 điểm ở §3.1 vì đó là hành vi nội bộ có thể đổi.
