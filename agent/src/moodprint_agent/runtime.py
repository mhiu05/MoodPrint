"""Official Agents SDK runtime with private checkpoints and v1 public events."""

import asyncio
import logging
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
from moodprint_agent.roleplay.service import EXIT_ROLE_TEXT, build_partner
from moodprint_agent.tools.citations import resolve_citations
from moodprint_agent.tools.context import CompanionToolContext, RunScratch
from moodprint_agent.tools.registry import ToolRegistry, diagnostic_registry
from moodprint_agent.tools.risk_assessor import HybridResult, RiskAssessor, hybrid_assess
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
from moodprint_agent.tools.save_intent import TURN_HINT_CLEAR, assess_save_intent


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
        risk_assessor: RiskAssessor | None = None,
    ) -> None:
        self.cfg = cfg
        # Opt-in model-assisted urgency (S-06 option C). None keeps the deterministic layer only.
        self.risk_assessor = risk_assessor
        self.registry = registry if registry is not None else diagnostic_registry()
        self.agent = build_companion(cfg, self.registry)
        self.partner = build_partner(cfg)  # the same runtime in a no-tools practice mode
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
        if (
            isinstance(ctx, CompanionToolContext)
            and ctx.mode == "companion"
            and assess_save_intent(user_input) == "clear"
        ):
            ctx.turn_hint = (
                TURN_HINT_CLEAR  # A-03a handoff; the approval dialog still decides (A-03b)
            )
        risk_task: asyncio.Task[HybridResult] | None = None
        if self.risk_assessor is not None and not urgency.immediate:
            # Runs beside the main model call; its answer is needed only when the reply completes.
            risk_task = asyncio.create_task(
                hybrid_assess([*prior_user_messages, user_input], self.risk_assessor)
            )
            if isinstance(ctx, CompanionToolContext) and ctx.mode == "roleplay":
                # A practice partner must leave the role before it answers, so wait here.
                urgency = combine(urgency, (await risk_task).assessment)
                risk_task = None
        if (
            isinstance(ctx, CompanionToolContext)
            and ctx.mode == "roleplay"
            and (
                urgency.immediate
                or "recent_high_risk" in urgency.signals
                or (ctx.roleplay is not None and ctx.roleplay.safety_locked)
            )
        ):
            # Leave the role without asking the model: a practice partner never handles danger,
            # and it does not resume right after a high-risk turn while the conversation is
            # still on watch.
            for event in self._exit_role(ctx, emitter, urgency):
                yield event
            return
        async for event in self._stream(
            ctx=ctx,
            sdk_input=user_input,
            session=session,
            emitter=emitter,
            urgency=urgency,
            risk_task=risk_task,
        ):
            yield event

    def _exit_role(
        self, ctx: CompanionToolContext, emitter: EventEmitter, urgency: UrgencyAssessment
    ) -> list[StreamEvent]:
        content = with_emergency_block(EXIT_ROLE_TEXT)
        return [
            emitter.emit(
                "run.started",
                {
                    "run_id": ctx.run_id,
                    "conversation_id": ctx.conversation_id,
                    "message_id": emitter.message_id,
                },
            ),
            emitter.emit(
                "message.completed",
                {
                    "message_id": emitter.message_id,
                    "content": content,
                    "citations": [],
                    "structured": CompanionTurn(reply=content, urgency=urgency.level, citations=[]),
                },
            ),
            emitter.emit(
                "run.usage",
                {
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                    "requests": 0,
                    "tool_calls": 0,
                    "latency_ms": 0,
                },
            ),
            emitter.emit("run.completed", {"status": "completed"}),
        ]

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
                rejection_message=(
                    "Người dùng đã chọn KHÔNG lưu. Đó là lựa chọn của họ, không phải lỗi hệ thống. "
                    "Chưa có gì được ghi. Hãy ghi nhận lựa chọn đó một cách tôn trọng, không nói "
                    "hệ thống bị lỗi, không ép, và hỏi họ có muốn sửa gì thì soạn lại."
                ),
            )
        emitter = EventEmitter(
            ctx.run_id, message_id or checkpoint.message_id, self.registry, checkpoint.seq
        )
        for pending in interruptions:
            emitter.remember_call(_call_id(pending.raw_item), pending.tool_name or "unknown")
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
        risk_task: "asyncio.Task[HybridResult] | None" = None,
    ) -> AsyncIterator[StreamEvent]:
        if ctx.run_id in self._active:
            if risk_task is not None:
                risk_task.cancel()
            raise ValueError("run already active")
        risk_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "requests": 0}
        if isinstance(ctx.budget, RunToolBudget):
            ctx.budget.max_calls = min(ctx.budget.max_calls, self.cfg.agent.max_tool_calls_per_run)
        cancel_signal = asyncio.Event()
        self._active[ctx.run_id] = cancel_signal
        if isinstance(ctx, CompanionToolContext):
            ctx.cancel_check = cancel_signal.is_set
        started = perf_counter()
        result: RunResultStreaming | None = None
        next_event: asyncio.Task[SDKStreamEvent] | None = None
        cancel_waiter: asyncio.Task[bool] | None = None
        stream: AsyncGenerator[SDKStreamEvent, None] | None = None
        cancelled = False

        def usage_data() -> dict[str, int]:
            usage = result.context_wrapper.usage if result is not None else None
            return {
                "input_tokens": (usage.input_tokens if usage is not None else 0)
                + risk_usage["input_tokens"],
                "output_tokens": (usage.output_tokens if usage is not None else 0)
                + risk_usage["output_tokens"],
                "total_tokens": (usage.total_tokens if usage is not None else 0)
                + risk_usage["total_tokens"],
                "requests": (usage.requests if usage is not None else 0) + risk_usage["requests"],
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
                roleplay = isinstance(ctx, CompanionToolContext) and ctx.mode == "roleplay"
                result = Runner.run_streamed(
                    self.partner if roleplay else self.agent,
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
                grace_deadline: float | None = None
                forced = False
                while True:
                    next_event = asyncio.create_task(read_event())
                    while True:
                        waiting: set[asyncio.Task[Any]] = {next_event}
                        if cancel_waiter is not None:
                            waiting.add(cancel_waiter)
                        interval = self.cfg.agent.heartbeat_interval_s
                        if grace_deadline is not None:
                            interval = max(0.0, min(interval, grace_deadline - perf_counter()))
                        done, _ = await asyncio.wait(
                            waiting, timeout=interval, return_when=asyncio.FIRST_COMPLETED
                        )
                        if cancel_waiter is not None and cancel_waiter in done:
                            # Ask nicely first: let the current turn or tool finish...
                            result.cancel("after_turn")
                            cancelled = True
                            cancel_waiter = None
                            grace_deadline = perf_counter() + self.cfg.agent.cancel_grace_s
                        if next_event in done:
                            break
                        if grace_deadline is not None and perf_counter() >= grace_deadline:
                            if not forced:
                                # ...then stop it: a slow tool or model call cannot outlive a cancel.
                                result.cancel("immediate")
                                forced = True
                        elif not done:
                            yield emitter.emit("heartbeat", {})
                    try:
                        sdk_event = next_event.result()
                    except StopAsyncIteration:
                        break
                    translated = emitter.translate(sdk_event)
                    if translated is not None:
                        yield translated
                next_event = None

                if risk_task is not None and cancelled:
                    risk_task.cancel()  # a cancelled turn does not wait for the second opinion
                    risk_task = None
                if risk_task is not None:
                    hybrid = await risk_task
                    risk_task = None
                    urgency = combine(urgency, hybrid.assessment)
                    if hybrid.model_called and hybrid.degraded is None:
                        for key in ("input_tokens", "output_tokens", "total_tokens"):
                            risk_usage[key] += hybrid.usage.get(key, 0)
                        risk_usage["requests"] += 1
                    elif hybrid.degraded is not None:
                        # Never silently "safe": the failure code is logged (no message content).
                        logging.getLogger(__name__).warning(
                            "risk assessor degraded", extra={"code": hybrid.degraded}
                        )

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
                    # A persona may say worried things; only the user's side is screened in practice.
                    final = (
                        urgency if roleplay else combine(urgency, assess_reply(resolved.content))
                    )
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
            # Class and public code only: never the message, it may carry user or provider text.
            logging.getLogger(__name__).warning(
                "run failed code=%s type=%s", code, type(error).__name__
            )
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
            if risk_task is not None and not risk_task.done():
                risk_task.cancel()
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
