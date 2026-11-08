"""Official Agents SDK runtime with private checkpoints and v1 public events."""

import asyncio
from collections.abc import AsyncGenerator, AsyncIterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from time import perf_counter
from typing import Any, cast
from uuid import UUID, uuid4

from agents import (
    Model,
    RunConfig,
    RunContextWrapper,
    Runner,
    RunState,
    Session,
    SessionSettings,
)
from agents.exceptions import (
    InputGuardrailTripwireTriggered,
    MaxTurnsExceeded,
    ModelRefusalError,
    ModelTimeoutError,
    OutputGuardrailTripwireTriggered,
    ToolTimeoutError,
)
from agents.models.openai_provider import OpenAIProvider
from agents.result import RunResultStreaming
from agents.stream_events import StreamEvent as SDKStreamEvent
from moodprint_shared.config import AppConfig
from moodprint_shared.contracts.agent import AgentToolContext, CompanionTurn
from moodprint_shared.contracts.streaming import RunErrorCode, StreamEvent
from openai import AsyncOpenAI, OpenAIError
from pydantic import BaseModel, ConfigDict, Field

from moodprint_agent.budget import RunToolBudget
from moodprint_agent.companion import PROMPT_VERSION, build_companion, model_settings
from moodprint_agent.errors import InvalidApprovalState, ToolBudgetExceeded
from moodprint_agent.events import EventEmitter
from moodprint_agent.tools.citations import resolve_citations
from moodprint_agent.tools.context import CompanionToolContext, RunScratch
from moodprint_agent.tools.registry import ToolRegistry, diagnostic_registry
from moodprint_agent.tools.safety import (
    ELEVATED_HINT,
    NONE,
    UrgencyAssessment,
    UrgencyLevel,
    assess_conversation,
    assess_reply,
    combine,
    with_emergency_block,
)


@dataclass(frozen=True, slots=True)
class ApprovalCheckpoint:
    id: UUID
    run_id: UUID
    tool: str
    tool_call_id: str
    preview: dict[str, Any]
    expires_at: datetime
    serialized_state: str


class _Checkpoint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = 2
    run_id: UUID
    conversation_id: UUID
    message_id: UUID
    seq: int = Field(ge=1)
    elapsed_ms: int = Field(ge=0)
    tools_version: str
    prompt_version: str
    budget: dict[str, Any]
    scratch: dict[str, Any] = Field(default_factory=dict[str, Any])
    urgency_level: UrgencyLevel = "none"
    urgency_signals: list[str] = Field(default_factory=list[str])
    sdk_state: str


def _public_error(error: BaseException) -> tuple[RunErrorCode, bool]:
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, ToolBudgetExceeded):
            return "tool_budget_exceeded", False
        if isinstance(current, MaxTurnsExceeded):
            return "max_turns", False
        if isinstance(current, ModelTimeoutError):
            return "model_timeout", True
        if isinstance(
            current,
            (ModelRefusalError, InputGuardrailTripwireTriggered, OutputGuardrailTripwireTriggered),
        ):
            return "model_refusal", False
        if isinstance(current, (OpenAIError, ToolTimeoutError)):
            return "upstream_error", True
        current = current.__cause__
    return "internal_error", True


class CompanionRuntime:
    prompt_version = PROMPT_VERSION

    def __init__(
        self,
        cfg: AppConfig,
        registry: ToolRegistry | None = None,
        *,
        model: Model | None = None,
        openai_client: AsyncOpenAI | None = None,
    ) -> None:
        self.cfg = cfg
        self.registry = registry if registry is not None else diagnostic_registry()
        self.agent = build_companion(cfg, self.registry)
        # A provider-neutral Model supports ScriptedModel tests; live calls use the fixed ID.
        self.model = model
        self.openai_client = openai_client
        self._active: dict[UUID, asyncio.Event] = {}
        self._approvals: dict[UUID, tuple[ApprovalCheckpoint, ...]] = {}

    @property
    def tools_version(self) -> str:
        return self.registry.version()

    def run_config(self) -> RunConfig:
        return RunConfig(
            model=self.model if self.model is not None else self.cfg.openai_model,
            model_settings=model_settings(self.cfg),
            tracing_disabled=True,
            trace_include_sensitive_data=False,
            workflow_name="moodprint-companion",
            session_settings=SessionSettings(limit=self.cfg.agent.session_item_limit),
            model_provider=OpenAIProvider(
                openai_client=self.openai_client,
                use_responses=True,
                use_responses_websocket=False,
            ),
        )

    def cancel(self, run_id: UUID) -> bool:
        signal = self._active.get(run_id)
        if signal is None:
            return False
        signal.set()
        return True

    def pending_approvals(self, run_id: UUID) -> tuple[ApprovalCheckpoint, ...]:
        return self._approvals.get(run_id, ())

    async def stream_turn(
        self,
        *,
        ctx: AgentToolContext,
        user_input: str,
        session: Session,
        message_id: UUID | None = None,
        prior_user_messages: Sequence[str] = (),
    ) -> AsyncIterator[StreamEvent]:
        if not user_input.strip() or len(user_input) > self.cfg.agent.max_user_input_chars:
            raise ValueError("invalid user input length")
        emitter = EventEmitter(ctx.run_id, message_id or uuid4(), self.registry)
        # Deterministic layer first: it never depends on the model or the network.
        urgency = assess_conversation([*prior_user_messages, user_input])
        if isinstance(ctx, CompanionToolContext) and urgency.level == "elevated":
            ctx.safety_hint = ELEVATED_HINT
        async for event in self._stream(
            ctx=ctx, sdk_input=user_input, session=session, emitter=emitter, urgency=urgency
        ):
            yield event

    async def resume_after_approval(
        self,
        *,
        ctx: AgentToolContext,
        serialized_state: str,
        approved: bool,
        session: Session,
        tool_call_id: str | None = None,
        message_id: UUID | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """Consume a server-owned snapshot after the service verifies owner/expiry/decision."""
        checkpoint = _Checkpoint.model_validate_json(serialized_state)
        if (
            checkpoint.version not in (1, 2)
            or checkpoint.run_id != ctx.run_id
            or checkpoint.conversation_id != ctx.conversation_id
            or checkpoint.tools_version != self.tools_version
            or checkpoint.prompt_version != self.prompt_version
        ):
            raise InvalidApprovalState("incompatible approval checkpoint")
        ctx.budget = RunToolBudget.from_snapshot(checkpoint.budget)
        if isinstance(ctx, CompanionToolContext):
            ctx.scratch = RunScratch.from_snapshot(checkpoint.scratch)
        urgency = UrgencyAssessment(checkpoint.urgency_level, tuple(checkpoint.urgency_signals))
        state = await RunState.from_string(
            self.agent,
            checkpoint.sdk_state,
            context_override=RunContextWrapper(ctx),
            strict_context=True,
        )
        interruptions = state.get_interruptions()
        matching = [
            item
            for item in interruptions
            if tool_call_id is None or _call_id(item.raw_item) == tool_call_id
        ]
        if len(matching) != 1:
            raise InvalidApprovalState("approval must identify one pending tool call")
        if approved:
            state.approve(matching[0])
        else:
            state.reject(
                matching[0],
                rejection_message="Người dùng không đồng ý. Không thực hiện thay đổi này.",
            )
        emitter = EventEmitter(
            ctx.run_id, message_id or checkpoint.message_id, self.registry, checkpoint.seq
        )
        self._approvals.pop(ctx.run_id, None)
        async for event in self._stream(
            ctx=ctx,
            sdk_input=state,
            session=session,
            emitter=emitter,
            elapsed_ms=checkpoint.elapsed_ms,
            urgency=urgency,
        ):
            yield event

    async def _stream(
        self,
        *,
        ctx: AgentToolContext,
        sdk_input: Any,
        session: Session,
        emitter: EventEmitter,
        elapsed_ms: int = 0,
        urgency: UrgencyAssessment = NONE,
    ) -> AsyncIterator[StreamEvent]:
        if ctx.run_id in self._active:
            raise ValueError("run already active")
        if isinstance(ctx.budget, RunToolBudget):
            ctx.budget.max_calls = min(ctx.budget.max_calls, self.cfg.agent.max_tool_calls_per_run)
        cancel_signal = asyncio.Event()
        self._active[ctx.run_id] = cancel_signal
        started = perf_counter()
        result: RunResultStreaming | None = None
        next_event: asyncio.Task[SDKStreamEvent] | None = None
        cancel_waiter: asyncio.Task[bool] | None = None
        stream: AsyncGenerator[SDKStreamEvent, None] | None = None
        cancelled = False

        def usage_data() -> dict[str, int]:
            usage = result.context_wrapper.usage if result is not None else None
            return {
                "input_tokens": usage.input_tokens if usage is not None else 0,
                "output_tokens": usage.output_tokens if usage is not None else 0,
                "total_tokens": usage.total_tokens if usage is not None else 0,
                "requests": usage.requests if usage is not None else 0,
                "tool_calls": ctx.budget.total_calls,
                "latency_ms": elapsed_ms + int((perf_counter() - started) * 1000),
            }

        try:
            yield emitter.emit(
                "run.started",
                {
                    "run_id": ctx.run_id,
                    "conversation_id": ctx.conversation_id,
                    "message_id": emitter.message_id,
                },
            )
            async with asyncio.timeout(self.cfg.agent.run_timeout_s):
                result = Runner.run_streamed(
                    self.agent,
                    sdk_input,
                    context=ctx,
                    session=session,
                    max_turns=self.cfg.agent.max_turns,
                    run_config=self.run_config(),
                )
                stream = cast(AsyncGenerator[SDKStreamEvent, None], result.stream_events())
                sdk_stream = stream

                async def read_event() -> SDKStreamEvent:
                    return await anext(sdk_stream)

                cancel_waiter = asyncio.create_task(cancel_signal.wait())
                while True:
                    next_event = asyncio.create_task(read_event())
                    while True:
                        waiting: set[asyncio.Task[Any]] = {next_event}
                        if cancel_waiter is not None:
                            waiting.add(cancel_waiter)
                        done, _ = await asyncio.wait(
                            waiting,
                            timeout=self.cfg.agent.heartbeat_interval_s,
                            return_when=asyncio.FIRST_COMPLETED,
                        )
                        if cancel_waiter is not None and cancel_waiter in done:
                            result.cancel("after_turn")
                            cancelled = True
                            cancel_waiter = None
                        if next_event in done:
                            break
                        if not done:
                            yield emitter.emit("heartbeat", {})
                    try:
                        sdk_event = next_event.result()
                    except StopAsyncIteration:
                        break
                    translated = emitter.translate(sdk_event)
                    if translated is not None:
                        yield translated
                next_event = None

                interruptions = result.interruptions
                if interruptions and not cancelled:
                    if not isinstance(ctx.budget, RunToolBudget):
                        raise InvalidApprovalState("persistent approvals require RunToolBudget")
                    checkpoint = _Checkpoint(
                        run_id=ctx.run_id,
                        conversation_id=ctx.conversation_id,
                        message_id=emitter.message_id,
                        seq=emitter.seq + len(interruptions) + 2,
                        elapsed_ms=usage_data()["latency_ms"],
                        budget=ctx.budget.snapshot(),
                        scratch=ctx.scratch.snapshot()
                        if isinstance(ctx, CompanionToolContext)
                        else {},
                        urgency_level=urgency.level,
                        urgency_signals=list(urgency.signals),
                        tools_version=self.tools_version,
                        prompt_version=self.prompt_version,
                        sdk_state=result.to_state().to_string(
                            context_serializer=lambda _: {}, strict_context=True
                        ),
                    ).model_dump_json()
                    approvals: list[ApprovalCheckpoint] = []
                    for item in interruptions:
                        name = item.tool_name or "unknown"
                        preview = await self.registry.approval_preview_for(
                            name, _arguments(item.raw_item), ctx
                        )
                        approval = ApprovalCheckpoint(
                            id=uuid4(),
                            run_id=ctx.run_id,
                            tool=name,
                            tool_call_id=_call_id(item.raw_item),
                            preview=preview,
                            expires_at=datetime.now(UTC) + timedelta(minutes=15),
                            serialized_state=checkpoint,
                        )
                        approvals.append(approval)
                        yield emitter.emit(
                            "approval.required",
                            {
                                "approval_id": approval.id,
                                "tool": name,
                                "label": self.registry.label(name),
                                "preview": preview,
                                "expires_at": approval.expires_at,
                            },
                        )
                    self._approvals[ctx.run_id] = tuple(approvals)
                    status = "awaiting_approval"
                elif cancelled:
                    status = "cancelled"
                else:
                    raw = result.final_output if isinstance(result.final_output, str) else ""
                    scratch = ctx.scratch if isinstance(ctx, CompanionToolContext) else None
                    resolved = resolve_citations(raw, scratch)
                    final = combine(urgency, assess_reply(resolved.content))
                    content = (
                        with_emergency_block(resolved.content)
                        if final.immediate
                        else resolved.content
                    )
                    citations = list(resolved.citations)
                    yield emitter.emit(
                        "message.completed",
                        {
                            "message_id": emitter.message_id,
                            "content": content,
                            "citations": citations,
                            "structured": CompanionTurn(
                                reply=content, urgency=final.level, citations=citations
                            ),
                        },
                    )
                    status = "completed"
                yield emitter.emit("run.usage", usage_data())
                yield emitter.emit("run.completed", {"status": status})
        except TimeoutError:
            if result is not None:
                result.cancel("immediate")
            yield emitter.emit("run.usage", usage_data())
            yield emitter.emit(
                "run.failed",
                {
                    "code": "run_timeout",
                    "message": "Lượt trò chuyện đã quá thời gian. Bạn có thể thử lại.",
                    "retryable": True,
                },
            )
        except Exception as error:
            if result is not None:
                result.cancel("immediate")
            code, retryable = _public_error(error)
            yield emitter.emit("run.usage", usage_data())
            yield emitter.emit(
                "run.failed",
                {
                    "code": code,
                    "message": "Chưa thể hoàn tất lượt trò chuyện. Bạn có thể thử lại.",
                    "retryable": retryable,
                },
            )
        finally:
            if result is not None and not result.is_complete:
                result.cancel("immediate")
            # Continue consuming after cancellation. Cancelling the consumer again can
            # interrupt the SDK while its cancellation-safe session write is settling.
            if next_event is not None:
                await asyncio.gather(next_event, return_exceptions=True)
            if stream is not None:
                await stream.aclose()
            if result is not None and result.run_loop_task is not None:
                await asyncio.gather(result.run_loop_task, return_exceptions=True)
            if cancel_waiter is not None:
                cancel_waiter.cancel()
                await asyncio.gather(cancel_waiter, return_exceptions=True)
            self._active.pop(ctx.run_id, None)


def _call_id(raw: Any) -> str:
    value: Any
    if isinstance(raw, dict):
        data = cast(dict[str, Any], raw)
        value = data.get("call_id", data.get("id"))
    else:
        value = getattr(raw, "call_id", getattr(raw, "id", None))
    if not isinstance(value, str):
        raise InvalidApprovalState("approval has no call identity")
    return value


def _arguments(raw: Any) -> str:
    value: Any = (
        cast(dict[str, Any], raw).get("arguments", "{}")
        if isinstance(raw, dict)
        else getattr(raw, "arguments", "{}")
    )
    return value if isinstance(value, str) else "{}"
