# WS-04 — Một agent và state machine

Ưu tiên P0. Độ phức tạp L: cắm vào `drive`, 6 workflow, proposal. Nhánh `mhiu05/feat-refactor-ws04-agent`. PR đầu là **contract** (T01). Thiết kế ở [06](../06-ai-orchestration-and-safety.md).

## 1. Mục tiêu và giá trị

Một Trợ lý dẫn em qua từng việc bằng lời nói tự nhiên, không form cứng, không tự lưu gì.

## 2. Hiện trạng đã xác minh

Runtime, provider, hook ngân sách, proposal memory, citation đều dùng lại được. `troly` không thuộc V3 nên tự thoát skills, search, orchestration.

## 3. Khoảng trống

Persona, tool, state machine, proposal tổng quát, card mới.

## 4. Kiến trúc đề xuất

`drive` thêm đúng một nhánh:

```python
if bot == "troly":
    from app.ai.assistant.turn import run_turn
    reply = await run_turn(self, run, c, history, on_progress=progress, observer=observe)
elif run.workflow is not None and run.workflow.decision.delegates:
    ...
```

`run_turn` trả `AiReply`. Mọi thứ khác của `drive` (kiểm tra, publish, finalize) giữ nguyên. Ghi state và proposal trong cùng transaction publish qua `run.assistant_commit`, một callback trên `LiveRun`.

**Hội thoại `troly`**: mỗi tài khoản nhiều hội thoại; không có danh sách bot; UI mở thẳng.

## 5. Phạm vi

Trong: agent, WF-01, WF-02 (qua proposal), WF-05, WF-06, khung tool. Ngoài: tool của WS-05, WS-06, WS-07 chỉ có stub tới khi các WS đó xong.

## 6. File và symbol bị ảnh hưởng

`ai/runtime.py` (`LiveRun`, `drive`); `ai/provider.py` (thêm `run_assistant`); `ai/accounting.py`; `ai/schemas.py` (`Card`, `ProposalCard`); `ai/context.py` (loại tin nhạy cảm); `ai/chat_routes.py`.

## 7. File mới

`backend/app/ai/assistant/{__init__,schemas,prompt,workflow,state,tools,turn,proposals,proposal_routes,caution,reminders}.py`; `assistant/playbooks/{wf01,wf02,wf03,wf04,wf05,wf06}/SKILL.md`; `backend/alembic/versions/0032_assistant_workflows.py`; `backend/evals/assistant/`.

## 8. API contract

```python
class ProposalCard(DTO):
    kind: Literal["proposal"]
    proposal_id: UUID
    proposal_kind: ProposalKind
    preview: str = Field(max_length=2000)

class AssistantBubble(DTO):
    text: str = Field(min_length=1, max_length=1500)

class ClaimRef(DTO):
    sentence: str = Field(max_length=400)
    card_id: str = Field(max_length=64)

class ProposedStep(DTO):
    workflow: Literal["wf01", "wf02", "wf03", "wf04", "wf05"]
    step: str = Field(max_length=32)

class AssistantReply(DTO):
    messages: list[AssistantBubble] = Field(min_length=1, max_length=4)
    claim_refs: list[ClaimRef] = Field(default_factory=list, max_length=8)
    proposed_step: ProposedStep | None = None
```

`AssistantReply` không có `cards`: card chỉ do backend gắn từ receipt của tool. Model không tạo được proposal hay emergency.

| Route | Mô tả |
| --- | --- |
| `GET /api/v1/assistant/proposals/{id}` | Xem |
| `PATCH /api/v1/assistant/proposals/{id}` | Sửa nội dung trước khi lưu, `expectedVersion` |
| `POST /api/v1/assistant/proposals/{id}/confirm` | Lưu, `Idempotency-Key`, trả `ActionReceipt` |
| `POST /api/v1/assistant/proposals/{id}/reject` | Bỏ |
| `GET /api/v1/assistant/state/{conversationId}` | Trạng thái workflow để UI hiện gợi ý |
| `POST /api/v1/assistant/emergency/{conversationId}/ack` | `{ "kind": "safe" \| "called" }` |

**Tool interface** (`tools.py`), WS-05, WS-06, WS-07 cắm vào đây:

```python
@dataclass(frozen=True)
class ToolContext:
    runtime: AiRuntime
    run: LiveRun
    state: WorkflowState
    age_group: Literal["11-14", "15-17"]

class ToolResult(BaseModel):
    status: Literal["ok", "proposed", "unavailable", "denied"]
    data: dict
    proposal_id: UUID | None = None

ToolHandler = Callable[[ToolContext, BaseModel], Awaitable[ToolResult]]

def register_tool(name: str, params: type[BaseModel], handler: ToolHandler,
                  workflows: frozenset[str]) -> None: ...

def tools_for(ctx: ToolContext) -> list[FunctionTool]: ...
```

`ProposalKind` handler: `register_proposal(kind, payload_model, apply: Callable[[db, user, payload], Awaitable[ActionReceipt]])`.

## 9. Dữ liệu và migration

`0032_assistant_workflows`, xem [05 §4](../05-data-model-and-migrations.md#4-workflow-và-đề-xuất).

## 10. Task

| ID | Ưu tiên | Phụ thuộc | Thay đổi, ở đâu | Hành vi mong đợi | Lệnh test | Pass / fail |
| --- | --- | --- | --- | --- | --- | --- |
| WS-04-T01 | P0 | WS-03 | **PR contract**: `assistant/schemas.py`, `ProposalCard`, tool interface, `register_proposal`, OpenAPI, TS | Compile, không hành vi mới | `mypy app`; `npm run typecheck` | Pass: merge trước WS-05, WS-06 |
| WS-04-T02 | P0 | T01 | `workflow.py`: `WORKFLOWS`, `transition` thuần | Bảng transition đủ 6 WF; bước lạ bị bỏ; WF-06 ngắt mọi WF, lưu `return_*` | `pytest -q tests/test_assistant_workflow.py` | Pass: phủ mọi cặp (state, event) |
| WS-04-T03 | P0 | T02 | Migration 0032, ORM, `state.py` (DB cho hội thoại lưu, RAM trên `Conversation` cho tạm) | Đọc ghi có version | `pytest -q tests/test_assistant_state.py`; `alembic check` | Pass |
| WS-04-T04 | P0 | T02 | `prompt.py`, playbooks, loader dùng lại cách của `SkillRegistry` (kiểm tra symlink, 16 KiB, hash) | `ASSISTANT_PROMPT_VERSION` vào `ai_usage.prompt_version`; prompt theo nhóm tuổi; không chứa tên bot cũ | `pytest -q tests/test_assistant_prompt.py` | Pass |
| WS-04-T05 | P0 | T04 | `SdkProvider.run_assistant`, output guardrail `_no_unreceipted_claim`, `_no_output_artifacts`, `_check_capped_model` | `store=False`, tracing tắt, `max_turns=3`, hook 3/2; truyền `safety_identifier` băm (TO_VERIFY cách truyền qua Agents SDK 0.24) | `pytest -q tests/test_assistant_provider.py` | Pass với model giả |
| WS-04-T06 | P0 | T03, T05 | `turn.py`, nhánh trong `drive`, classifier, postcheck, nhắc nghỉ | Thứ tự đúng §3 của [06](../06-ai-orchestration-and-safety.md#3-pipeline-một-lượt); đỏ từ classifier thay bằng template; `ai_timeout_seconds` demo 45 | `pytest -q tests/test_assistant_turn.py` | Pass: bot cũ không đổi, regression chat pass |
| WS-04-T07 | P0 | T06 | `tools.py` thật, `proposals.py`, `proposal_routes.py`, gắn `ProposalCard` | Tool không ghi bảng nghiệp vụ; confirm mới ghi; hết hạn 24 giờ; người khác 404 | `pytest -q tests/test_assistant_proposals.py` | Pass: 0 hàng `cases` trước confirm |
| WS-04-T08 | P0 | T07 | WF-01: `classify_situation`, mẫu hỏi một câu mỗi lượt | Tóm tắt có cấu trúc lưu trong state; em sửa được | `pytest -q tests/test_assistant_wf01.py` | Pass |
| WS-04-T09 | P1 | T07 | WF-05: `bystander_actions`, template | Không khuyên can thiệp thể chất | `pytest -q tests/test_assistant_wf05.py` | Pass |
| WS-04-T10 | P0 | T06 | WF-06: `EMERGENCY_FOLLOW_UP`, `EmergencyCard` giữ trên mọi lời, route ack | Chỉ tool hỗ trợ; ack quay về `return_*` | `pytest -q tests/test_assistant_wf06.py` | Pass |
| WS-04-T11 | P0 | T06 | Vàng: `caution.py` thêm hướng dẫn và chip Tìm hỗ trợ | Vàng không tắt agent | `pytest -q tests/test_assistant_caution.py` | Pass |
| WS-04-T12 | P0 | T06 | `context.py`: lọc tin có `skip_model` khỏi lịch sử, thay ghi chú trung tính | Nội dung nhạy cảm không tới model ở lượt sau | `pytest -q tests/test_assistant_context.py` | Pass: assert input model giả |
| WS-04-T13 | P1 | T08 | `evals/assistant/`, 30 kịch bản, rubric | Báo cáo không nội dung | `python -m evals.assistant --offline <file>` | Pass: runner chạy |

## 11. An toàn và bảo mật

- Tool không nhận `user_id`.
- `runtime.check` trước mỗi tool.
- Kết quả tool bọc "dữ liệu".
- Không có tool gửi ra ngoài.
- Nhánh `troly` không gọi `consult`, `Workflow`, `prepare_turn` skills.

## 12. Test và dataset

Fullstack: thêm kịch bản `troly` vào SDK fake model của `tests/` (TO_VERIFY file `mood_e2e_model.py` hoặc tương đương).

## 13. Acceptance criteria

- `troly` trả lời, tạo proposal, xác nhận mới lưu.
- WF-06 ngắt mọi WF.
- Regression bot cũ pass ở profile default.

## 14. Phụ thuộc và blocker

WS-03. OD-10.

## 15. Rollback

Bot cũ không đổi. Bỏ profile thì nhánh `troly` không có ai gọi.

## 16. Definition of Done

G1 đạt cùng WS-03.

## 17. Ghi chú cho Grok

`ai_usage.prompt_version` là `varchar(60)`; giữ chuỗi ngắn. `gpt-6-luna` tính reasoning vào `max_output_tokens`; đặt `max_tokens` ≥ 1200 và `reasoning` thấp, nếu không stream kết thúc incomplete như đã gặp với hangout.
