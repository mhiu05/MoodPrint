# 04 — Kiến trúc AI với OpenAI Agents SDK

> **Kiến trúc đã chốt ngày 23/10/2026:** Python 3.12/FastAPI/Pydantic v2, SQLAlchemy 2 async + psycopg 3, Alembic/uv, Supabase PostgreSQL/Auth và OpenAI Agents SDK Python. Giữ React/Vite/TypeScript; Pydantic → OpenAPI → `frontend/src/api/generated/`. Chỉ scaffold cloud, không deploy. Evidence audit ban đầu là lịch sử, không phải trạng thái implementation mới.

**D03 đã chốt: OpenAI Agents SDK Python, một runtime chung, một bot hoạt động trong mỗi run.** Audit ban đầu chưa có SDK/agent server; trạng thái implementation mới phải có evidence riêng; [registry UI](../../frontend/src/companions/registry.ts#L1) và [scriptedReply](../../frontend/src/companions/scenarios.ts#L4) là nguồn danh tính, UX và ví dụ đánh giá, không phải runtime cần port nguyên trạng.

## SDK Python đã xác minh và trách nhiệm adapter

Official Python docs được mở **23/10/2026**; documentation không phải runtime compatibility evidence. Distribution `openai-agents`, import `agents`; không local package cùng tên. P02.01 phải pin uv lock và kiểm signatures/imports/fake transport trước live call.

| Primitive         | Python API và quyết định                                                                                                                                                                                                                                               |
| ----------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Agent/loop        | `Agent`, async `Runner.run`, `Runner.run_streamed`; SDK sở hữu model/tool loop, không viết lại. [Running](https://openai.github.io/openai-agents-python/running_agents/)                                                                                               |
| Tools/context     | `@function_tool`, `RunContextWrapper[T]`; actor/services/deadline local, không expose model. [Tools](https://openai.github.io/openai-agents-python/tools/), [context](https://openai.github.io/openai-agents-python/context/)                                          |
| Structured output | `Agent(output_type=AiOutputV1)` Pydantic v2; app còn kiểm live policy/receipts. [Agents](https://openai.github.io/openai-agents-python/agents/)                                                                                                                        |
| Streaming/cancel  | `result = Runner.run_streamed(...)`; `async for event in result.stream_events()` tới hết rồi final. `result.cancel()` immediate, `after_turn` không dùng cho immediate revoke. [Streaming](https://openai.github.io/openai-agents-python/streaming/)                   |
| Sessions          | App-owned RAM history/TTL; không durable SDK SQLite/SQL sessions vì no raw transcript/WAL. SDK session adapter chỉ nếu cùng policy được test. [Sessions](https://openai.github.io/openai-agents-python/sessions/)                                                      |
| Guardrails        | Input/output/tool checks bổ sung; không thay auth/ownership/transaction. Buffer final tới sau checks. [Guardrails](https://openai.github.io/openai-agents-python/guardrails/)                                                                                          |
| Model/provider    | Configured `Model`/`ModelProvider`, ModelSettings/RunConfig, fake transport; không browser model choice. [Models](https://openai.github.io/openai-agents-python/models/)                                                                                               |
| Tracing           | Trước run đầu `set_tracing_disabled(True)`, `RunConfig(tracing_disabled=True, trace_include_sensitive_data=False)`, env `OPENAI_AGENTS_DISABLE_TRACING=1`; disable sau buffering không xóa spans cũ. [Tracing](https://openai.github.io/openai-agents-python/tracing/) |
| Orchestration     | Baseline một bot/run, navigate-only; handoffs/agents-as-tools chỉ use case+eval thực. [Orchestration](https://openai.github.io/openai-agents-python/multi_agent/)                                                                                                      |
| Sandbox/jobs      | Chỉ Docker interface disabled khi chưa code/file use case; app worker/outbox sở hữu recovery/fencing, không SDK exactly-once.                                                                                                                                          |

P02.01 kiểm `ModelSettings(store=False)` outbound mapping khi provider/model hỗ trợ, asyncio deadline/cancel, event parsing/usage, hard model-call/tool caps qua SDK hooks/model adapter và tracing canary. `max_turns` chỉ ceiling phụ, không thay counter trước network/tool call. Không fake package options hoặc bật real request để dò API. App sở hữu configs/context/consent/ownership/budgets/IDs/status/proposals/source invalidation/output DTOs/replay/idempotency/evals. Contracts dưới đây là app Python, không SDK API.

## Bot Registry và cấu hình

```python
from dataclasses import dataclass
from typing import Literal

BotId = Literal["may", "guong", "nhip", "rure", "caunoi"]

@dataclass(frozen=True)
class BotConfig:
    bot_id: BotId
    name: str
    instructions_version: str
    instructions: str
    model_config_id: str
    tool_policy_version: str
    allowed_tools: tuple[str, ...]
    context_policy_id: str
    memory_scope: Literal["source-bot", "none"]
    output_schema_version: Literal["ai-output-v1"] = "ai-output-v1"
    model_calls: int = 3
    tool_calls: int = 2
    deadline_seconds: float = 30.0
```

Registry code và prompts ở `backend/app/ai/bots/`; các version được review và ghi vào run metadata. Frontend chỉ nhận BotPublicDTO: botId/name/role/description/starters/avatarKey, không instructions, credentials hoặc policy nội bộ. Các UI colors/SVG hiện tại giữ nguyên.

| Bot     | Instructions và context được chọn                                                     | Tools cho baseline                                                          | Dữ liệu không được thấy                                                             |
| ------- | ------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| Mây     | Lắng nghe/gợi mở, không chẩn đoán; chỉ thread Mây và memory được duyệt cho Mây        | `propose_memory`, `suggest_bot_transition`                                  | Mood/private khác scope, dữ liệu người khác, human chat                             |
| Gương   | Hỏi làm rõ, nhận xét là giả thuyết; thread Gương, nguồn user chủ động chọn            | `propose_private_item`, `propose_memory`, `suggest_bot_transition`          | Raw private profile toàn bộ mặc định, matching của peer                             |
| Nhịp    | Ghi mood do user tự chọn; diễn giải số liệu có nguồn, không suy cảm xúc từ text/voice | `get_mood_summary`, `suggest_mood_form`, `propose_memory` theo policy nguồn | Note ngoài range được chọn, chat người, dữ liệu peer                                |
| Rủ Rê   | Học/chơi ngắn từ nội dung duyệt; không tự mời bạn                                     | `get_activity_content`, `suggest_bot_transition`                            | Room/matching peer, private/mood, social write                                      |
| Cầu Nối | Giúp soạn own matching draft từ taxonomy; mở discovery bằng card                      | `get_own_matching_draft`, `propose_matching_tags`, `suggest_discovery`      | Private/mood/memory riêng mặc định, danh sách hồ sơ người khác hoặc report evidence |

Cầu Nối dùng `memory_scope="none"` ở baseline để giữ ranh giới matching; nếu muốn nhớ cách xưng hô sau này cần policy scope riêng không cấp quyền đưa memory vào scoring. “Cho phép tool” không có nghĩa đủ quyền dùng nguồn: Nhịp còn cần request range hợp lệ và user chủ động yêu cầu xem mood. C-MEM bật không cấp quyền đọc mọi domain record.

Bảng trên mô tả allowlist khi baseline hoàn chỉnh. Registry chỉ expose tool có domain producer đã sẵn: phase 3 Cầu Nối có card điều hướng, phase 4 chưa đăng ký tool matching-draft; P07.03 mới nối `get_own_matching_draft`/`propose_matching_tags` sau khi cả P04.02 và P05.01 hoàn tất. Nhánh matching vẫn chạy độc lập LLM; thiếu capability không được fallback sang fixture hoặc đưa tool chưa hoạt động cho model.

Thêm bot mới: đăng ký BotId/schema/public metadata, config/prompts, allowlist/context policy và eval cases. `create_agent(config, services)` dùng chung; không sửa loop hoặc tạo DB/process riêng. Không cho user tải system prompt, URL tools hoặc code thực thi.

## Contract runtime và run lifecycle

```python
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal

class StartAiRun(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    conversation_id: str = Field(alias="conversationId")
    client_message_id: str = Field(alias="clientMessageId")
    expected_conversation_version: int = Field(alias="expectedConversationVersion", ge=1)
    text: str = Field(min_length=1, max_length=500)

RunStatus = Literal["accepted", "running", "waiting_for_approval", "completed",
                    "cancelled", "failed", "interrupted", "expired"]

# App public service interfaces; dependent DTOs defined in app.api.schemas.
async def start_run(actor: AuthenticatedActor, request: StartAiRun) -> RunAccepted: ...
async def cancel_run(actor: AuthenticatedActor, run_id: str) -> RunView: ...
async def build_context(actor: AuthenticatedActor, run: RunRecord) -> ContextBundle: ...
async def get_session_view(actor: AuthenticatedActor, conversation_id: str) -> SessionView: ...
```

Conversation do server tạo theo owner+bot+session; botId bất biến của conversation. runId/userMessageId/assistantMessageId do server cấp; clientMessageId do client tạo để retry. Không tin `actor`, `botId`, consent hoặc prompt nằm trong text/LLM arguments. Message text nằm trong SessionStore; `ai_runs` chỉ chứa metadata và opaque message IDs.

```mermaid
sequenceDiagram
  participant U as Frontend
  participant B as API / policy
  participant S as SessionStore TTL
  participant R as Agents SDK
  participant T as Tool Gateway
  participant D as Domain + PostgreSQL
  U->>B: POST conversation/messages + clientMessageId
  B->>D: Auth, eligibility, C-AI, budget, claim run slot
  B->>S: Append input, versions, expiry; build bounded history
  B-->>U: 202 runId / messageId / stream endpoint
  B->>R: Agent config + prepared input + local context
  opt Có tool trong ngân sách
    R->>T: Tool name + validated args
    T->>D: Live actor/scope/consent/source-version check
    D-->>T: Minimal data / proposal ref / typed failure
    T-->>R: Structured tool result
  end
  R-->>B: Stream events và final output
  B->>B: Validate schema/policy; recheck permissions
  B->>S: Append validated final + replay events (TTL)
  B->>D: Complete run metadata + actual usage
  B-->>U: SSE final committed-to-session / complete
```

`202` chỉ xác nhận server nhận lượt, chưa có final answer. Hai lượt cùng conversation: unique active-run guard trong DB và session version CAS; trả `409 RUN_IN_PROGRESS`, không tự xếp hàng dài với context đã cũ. Các bot khác chạy được nhưng cùng quota account/global. Durable lease có fencing token để worker cũ không commit khi lease đã mất. Sau restart run còn running chuyển interrupted, không tự gọi lại model với text không còn.

**Giới hạn thăm dò:** tối đa 3 model calls, 2 tool executions, không SDK handoff trong baseline, 30 giây tổng gồm model/tools; tool read timeout 3 giây; max input 500 ký tự, output policy cap 1.200 tokens/lượt ngắn; global model concurrency ban đầu 5, mỗi account tối đa 2 runs khác bot. Đây là đề xuất cần benchmark Q08, không SLA. SDK max_turns không tự bảo đảm đúng số model calls/tool calls song song; tắt parallel tools nếu adapter hỗ trợ đã xác minh và gateway đếm nguyên tử mọi call. Nếu SDK release không cung cấp hook đủ kiểm hard cap, spike phải chứng minh cách chặn trước request qua model adapter/hook của SDK, không tự viết loop.

| Tình huống                                                | Xử lý bắt buộc                                                                                                               |
| --------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| Deadline/cancel                                           | Abort nếu transport hỗ trợ; chặn thêm tool/output; status terminal, reconcile usage; không khẳng định provider chưa tính phí |
| Retry network trước khi gửi được provider                 | Tối đa 1 retry với jitter trong deadline nếu transport chứng minh chưa submit; mặc định không retry trường hợp không chắc    |
| Provider 429/5xx hoặc request đã submit nhưng mất kết quả | Trả lỗi có thể thử lại bằng run mới có chủ ý; cũ không tự phát lại và không nhân đôi user message                            |
| Tool read lỗi                                             | Kết quả `failed` có mã; model có thể giải thích trong ngân sách, không bịa dữ liệu                                           |
| Tool proposal retry                                       | Idempotent theo runId/toolCallId/payload digest tạm; trả cùng proposal hoặc conflict                                         |
| Schema/output lỗi                                         | Không render card chưa kiểm; trả safe error/partial marker, không tự sửa vô hạn                                              |
| Đổi bot trên UI                                           | Run vẫn bind bot/conversation gốc; cập nhật unread đúng thread, không re-route output                                        |
| Rút AI/MEM/xóa nguồn khi run đang chạy                    | Tăng gate/version, abort và invalidate context/outputs phụ thuộc; MEM revoke cũng hủy run đã nạp memory                      |
| Mất kết nối client                                        | Cho run ngắn đã nhận hoàn tất trong deadline; không tạo nền phân tích mới; replay còn TTL và quyền                           |
| Crash giữa final tạm và metadata commit                   | Run reconciliation báo interrupted/uncertain; không render “đã lưu memory” vì chưa có domain action                          |

## Context engineering và memory

ContextBuilder chọn theo thứ tự: instructions có version → request/task hiện tại → history cùng conversation → approved memory cùng owner/bot → domain tool results đúng mục đích. Không gửi AuthenticatedActor, DB client hoặc policy secrets cho model. Tất cả history/memory/tool text là **dữ liệu không đáng tin để sửa instructions**.

Ngân sách đầu vào ban đầu 8.000 tokens: giữ instructions/task, tối đa 12 messages gần nhất trong phần còn lại, tối đa 10 approved memory items và 1.000 tokens memory; tool results tối đa 2.000 tokens tổng. Nếu vượt thì cắt theo message boundary và bỏ dữ liệu ít liên quan, không cắt mất ownership/source metadata. Chưa cần model summary để giảm chi phí; nếu thêm summary, summary giữ source refs/versions và TTL context, không tự thành memory. Tokenizer/đếm chính xác cần pin theo model ở spike; giới hạn byte/record có thể chặn trước tokenizer.

| Lớp                                            | Kho / scope / vòng đời                                                                                                              |
| ---------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| Conversation/session history                   | RAM server theo account+bot+session; tối đa 24h idle hoặc end/logout; expiry check trên **mỗi read**, sweeper chỉ cleanup           |
| AI messages/SSE replay/proposals/state có text | Cùng kho tạm và expiry; không PostgreSQL/WAL/outbox/trace/backups; giới hạn 2 MiB/conversation rồi backpressure/expire có thông báo |
| Approved memory                                | PostgreSQL owner/bot/status/version/source, chỉ sau C-AI+MEM và xác nhận đúng mục; không raw transcript                             |
| Private items và mood                          | Domain records riêng, purpose/retention riêng; không có quyền ngầm đưa tất cả vào context                                           |
| Nội dung học/chơi/hướng dẫn                    | Thư viện versioned không chứa private data; keyword/taxonomy lookup trước                                                           |

Reload còn cùng auth session và conversation chưa hết hạn lấy lại SessionView. Backend restart có thể mất text; UI báo “Phiên trò chuyện đã kết thúc” và mở conversation mới. Cookie/session server chỉ giữ identity và metadata tối thiểu. Đóng tab không đáng tin để biết kết thúc phiên; định nghĩa end/logout/idle ở Q05. **Không bán persistence phiên như khả năng nhớ lâu dài.**

Memory pipeline: proposal ephemeral → user preview/edit/reject → server validate source/consent/version + one-use approval → commit approved memory. Nội dung user sửa là bản được duyệt; source text không cần giữ vô hạn, chỉ opaque source reference và bản đã xác nhận. Hết TTL nguồn phiên tự nhiên không xóa approved memory đã được lưu độc lập; **explicit delete nguồn** phải invalidation theo dependency trước truy xuất tiếp. Conflict hai mục memory không được AI tự kết luận: tạo đề xuất thay thế, chờ user chọn. Sửa/xóa/thu hồi item tăng version, chặn dùng ngay, invalidate session context/runs liên quan và physical purge theo [09](09-security-devops-plan.md).

PostgreSQL query owner/bot/active + taxonomy/từ khóa đủ baseline. pgvector/RAG chỉ sau retrieval eval chứng minh mất recall quan trọng trên nguồn hợp lệ, với scope filter tại query và deletion path cho embeddings. Không embedding private chat để matching.

## Tool Gateway và HITL

```python
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

class ToolResult(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    status: Literal["succeeded", "proposed", "denied", "failed"]
    data: dict[str, Any] | None = None
    source_versions: list[SourceVersion] = Field(default_factory=list, alias="sourceVersions")
    proposal_id: str | None = Field(None, alias="proposalId")
    proposal_version: int | None = Field(None, alias="proposalVersion")
    expires_at: str | None = Field(None, alias="expiresAt")
    code: str | None = None
    retryable: bool = False
    # Production validators enforce required fields per status and wire aliases.

async def execute_tool(ctx: ServerRunContext, name: str, args: Any) -> ToolResult: ...
async def confirm_proposal(actor: AuthenticatedActor, proposal_id: str,
                           request: ConfirmProposal) -> DomainActionResult: ...
```

`ServerRunContext` là local SDK context: actorId lấy từ phiên, botId/conversation/runId, consent/source snapshots, deadline/budgets và public services. Gateway allowlist tool name+bot, runtime schema, length/range, live actor/consent/source versions và quota trước thực thi. Model không cung cấp userId, role, confirmation hoặc SQL/URL/code. Domain service kiểm lại ở commit; gateway không chỉ kiểm schema.

- Read-only: mood summary chọn range, own matching draft, thư viện nội dung. Result có nguồn/version, dữ liệu tối thiểu; không query user khác hoặc đọc human chat.
- Proposal/preview: private item/memory/tag suggestions, mood form, navigate bot/discovery. Đây chỉ tạo đề xuất có expiry, không grant hoặc publish.
- Write/action: save mood/private/memory, publish, invite/accept, reveal/block **là API do UI user action**, không nằm trong tools baseline. Lưu private item không mặc nhiên lưu memory; click đã duyệt không cấp quyền hành động xã hội khác.

```mermaid
sequenceDiagram
  participant AI as Gương / SDK
  participant G as Tool Gateway
  participant E as Ephemeral proposals
  participant U as UI / người dùng
  participant D as Domain transaction
  AI->>G: propose_memory(text, sourceRefs)
  G->>E: Lưu proposal pending + source/consent versions + TTL
  G-->>U: Card status=proposed, chưa lưu memory
  U->>D: Confirm ID + version + bản sửa + idempotency key
  D->>E: Kiểm owner / pending / TTL và claim one-use
  D->>D: Lock account gate; check AI+MEM và nguồn; commit approved item
  D-->>U: succeeded + resourceId/version
  Note over E,D: Consent/nguồn đổi hoặc hết hạn → conflict/expired, không lưu
```

Ở PoC một instance, proposal claim trong RAM và domain idempotency phải phối hợp: claim `processing`, commit memory với unique proposalId/owner, retry sau crash đọc kết quả đã commit; nếu chưa commit và proposal mất thì trả expired, yêu cầu tạo lại. Không giữ transaction/LLM call mở trong lúc user cân nhắc.

SDK Python có `needs_approval`/interruptions/resumable state theo docs; app chưa cần dùng nó cho social actions. Nếu thử workflow approval SDK sau này: bind actor, action, payload digest/version, source+consent versions, expiresAt; validate lại trước `approve/resume`; raw state chỉ kho tạm có TTL; serialized state version không tương thích thì hết hạn an toàn. SDK approval **không là** quyền truy cập dữ liệu của app.

## UI transition và orchestration

Mây đề nghị mở Nhịp → user bấm → frontend đổi route → Nhịp dùng thread riêng; không payload transcript, không LLM gọi thêm bốn bot. Nếu có transition contract: `{kind:'navigate_bot',botId:'nhip'}`, server allowlist destination, frontend render CTA. Đây không phải SDK handoff. Safe transition test T-AI-04 giữ đúng hành vi đã có.

Nếu sau này cần context transfer: user preview/edit một bản tóm tắt rõ nguồn và nơi nhận, một lần, có expiry/version; bot đích nhận như dữ liệu, không memory mới và không quyền mới. Specialist-as-tool cần input/output nhỏ, không arbitrary history, depth≤1, chung tổng budget, benchmark so với một agent. Chưa có task triển khai specialist trong roadmap MVP.

## Output contract và streaming

```python
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field

# Allowlisted discriminated card DTOs live in app.api.schemas.ai.
AiCard = Annotated[NavigationCard | ProposalCard | MoodFormCard | MoodSummaryCard |
                   ActivityContentCard, Field(discriminator="kind")]

class AiOutputV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    schema_version: Literal["ai-output-v1"] = Field(alias="schemaVersion")
    reply: str
    cards: list[AiCard]

class ActionView(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    action_id: str = Field(alias="actionId")
    status: Literal["proposed", "pending", "succeeded", "denied", "failed", "expired"]
    resource_id: str | None = Field(None, alias="resourceId")
    resource_version: int | None = Field(None, alias="resourceVersion")
    error_code: str | None = Field(None, alias="errorCode")
```

Model không được tạo `succeeded` chỉ bằng text. Card IDs/source refs phải match server tool receipts hoặc template deterministic; invalid IDs bị loại và trả lỗi, không render button có quyền tự tạo. `succeeded` của write chỉ do domain commit response. Response text cũng bị kiểm chuyện “đã lưu/đã mời” không có receipt; rubric và deterministic output checks phối hợp, không dựa vào prompt đơn lẻ.

SSE app events: `run.accepted`, `run.progress`, `message.delta`, `message.final`, `action.proposed`, `run.completed`, `run.failed`, `run.cancelled`, `session.expired`. Envelope gồm `{eventId,seq,runId,conversationId,botId,type,data}`; không gửi provider raw events/arguments trực tiếp. Seq tăng theo run, cursor là chuỗi số, event ID unique. Heartbeat chỉ comment, không làm tăng message count.

**Baseline buffer final output trước hiển thị text/cards.** SDK vẫn consume streaming để theo dõi tiến độ, cancel và usage; UI nhận progress thật. Sau schema/guardrail/live permission checks, gửi final vào SessionStore rồi `message.final`; nếu chia chunk cho UX, đó là output đã kiểm, không giả metric TTFT model. Raw deltas chỉ bật ở experiment sau khi chấp nhận rủi ro output chưa kiểm; không stream JSON structured-output từng token vào UI.

Kết nối: POST tạo run → GET authenticated SSE với `afterSeq`; fetch ReadableStream + AbortController, credentials đúng site; reconnect có backoff hữu hạn, gọi snapshot/replay theo cursor. Replayed final giữ messageId cũ. Buffer hết TTL trả `410 SESSION_EXPIRED`; không gọi model lại để “replay”. Consent revoke trả terminal metadata, chặn text còn lại; bytes đã gửi trước gate không thu hồi được. UI phải xóa view khi nhận invalidation, không dùng cache lâu dài.

## Tracing, usage và chiến lược tích hợp

**Tracing SDK server bật mặc định** theo official guide đã đọc; do đó P02.01 phải tắt exporter trước run đầu tiên, sau đó kiểm outbound network bằng canary text. Các option nêu trên phải chạy compatibility test theo version đã lock; documentation không là runtime evidence. Muốn bật traces phải dùng allowlist metadata, inspect model/tool/error spans, nesting và flush path; sample rate không thay redaction.

Log/metric cho phép: opaque run/request IDs, bot/config/model versions, tool name/status, consent/source version numbers, latency, usage, retry/error code và cost ước tính từ bảng giá được ghi ngày. Không raw prompt, reply, mood/note/memory, tool args/results, session state, identity hoặc chain-of-thought. Số token/cost từ usage thật; provider lỗi giữa chừng có thể usage chưa biết, phải ghi unknown/reservation chưa reconcile.

Thực hiện: P02.01 compile SDK adapter + fake transport → P02.02 một bot không tool → P02.03 TTL/run limits/SSE → P02.04 Mây UI → P03 registry/schema/cards → P04 domain tools/memory. Mỗi bước có stub deterministic và cases adversarial trước model thật. Danh mục test/gates tại [08](08-testing-evals-plan.md); không chạy real-model eval bằng dữ liệu người dùng trong lượt planning.

Runtime thực tại `backend/app/ai/`; Pydantic schemas export OpenAPI và generated TypeScript. Sandbox interface/config disabled mặc định; Docker isolation theo [09](09-security-devops-plan.md). Không shell/code tools cho 5 bot baseline.
