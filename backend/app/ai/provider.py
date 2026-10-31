"""One buffered, privacy-configured Agents SDK runtime for all five bots."""

import asyncio
import re
from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import Any, cast

from agents import (
    Agent,
    FunctionTool,
    GuardrailFunctionOutput,
    Model,
    ModelRetrySettings,
    ModelSettings,
    RunConfig,
    RunContextWrapper,
    RunHooks,
    Runner,
    UserError,
    output_guardrail,
    set_tracing_disabled,
)
from agents.items import TResponseInputItem
from agents.models.openai_responses import OpenAIResponsesModel
from agents.result import RunResultStreaming
from agents.tool import Tool
from openai import AsyncOpenAI
from openai.types.shared import Reasoning

from app.ai.conversation import conversation_intent, requested_presentation
from app.ai.evidence import MoodAnalysisPlan, render_mood_analysis, source_instructions
from app.ai.journal import (
    NhipOutput,
    NhipReply,
    has_journal_link,
    journal_instructions,
    journal_read_refused,
    render_journal_output,
    render_journal_reply,
)
from app.ai.prompts import (
    LEGACY_BOTS,
    MULTI_MESSAGE_GUIDANCE,
    conversation_instructions,
    instructions,
)
from app.ai.schemas import AiOutput, AiReply, CompanionReply
from app.ai.usage import UsageEvent, UsageObserver
from app.core.config import Settings
from app.core.errors import DomainError
from app.core.outbound import openai_http_client

RUN_TIMEOUT_SECONDS = 30.0
_DURABLE_CLAIM = re.compile(
    r"(?:^|[.!?\n]\s*)(?:(?:mình|tôi|i)\s+)?"
    r"(?:đã\s+(?:lưu|ghi nhớ|xuất bản|gửi lời mời|kết nối)|"
    r"(?:have\s+)?(?:saved|published|sent\s+(?:the\s+)?invitation))\b",
    re.IGNORECASE,
)


def output_texts(output: Any) -> list[str]:
    """Every user-visible text of a single-message or multi-bubble model output."""
    messages = getattr(output, "messages", None)
    if messages is not None:
        return [bubble.text for bubble in messages]
    return [output.text]


@output_guardrail
async def _no_unreceipted_claim(
    context: RunContextWrapper[Any], agent: Agent[Any], output: AiOutput | CompanionReply
) -> GuardrailFunctionOutput:
    # No current model-facing tool performs a durable write. This narrow check
    # catches common unsupported success statements in every bubble; schema
    # validation separately rejects forged receipt/action fields. It is not a
    # semantic safety classifier.
    return GuardrailFunctionOutput(
        output_info={"code": "UNRECEIPTED_ACTION_CLAIM"},
        tripwire_triggered=any(_DURABLE_CLAIM.search(text) for text in output_texts(output)),
    )


class _BudgetHooks(RunHooks[Any]):
    def __init__(
        self,
        on_progress: Callable[[], Awaitable[None]],
        observer: UsageObserver | None = None,
        *,
        model_limit: int = 3,
        tool_limit: int = 2,
    ):
        self.model_calls = 0
        self.tool_calls = 0
        self.on_progress = on_progress
        self.observer = observer
        # Chat keeps 3/2 (ai_usage CHECK); a specialist consultation is 1 model call, 0 tools.
        self.model_limit = model_limit
        self.tool_limit = tool_limit

    async def on_llm_start(
        self,
        context: RunContextWrapper[Any],
        agent: Agent[Any],
        system_prompt: str | None,
        input_items: list[TResponseInputItem],
    ) -> None:
        self.model_calls += 1
        if self.model_calls > self.model_limit:
            raise DomainError(429, "MODEL_LIMIT", "Đã hết số phản hồi cho lượt này.")
        # The caller can revalidate live authorization without receiving model I/O.
        await self.on_progress()
        if self.observer:
            await self.observer(UsageEvent(kind="request_started"))

    async def on_llm_end(self, context, agent, response) -> None:
        if self.observer:
            usage = response.usage
            await self.observer(UsageEvent(
                kind="response_received", input_tokens=usage.input_tokens,
                cached_input_tokens=usage.input_tokens_details.cached_tokens,
                output_tokens=usage.output_tokens,
            ))

    async def on_tool_start(
        self,
        context: RunContextWrapper[Any],
        agent: Agent[Any],
        tool: Tool,
    ) -> None:
        self.tool_calls += 1
        if self.tool_calls > self.tool_limit:
            raise DomainError(429, "TOOL_LIMIT", "Đã hết số thao tác cho lượt này.")
        if self.observer:
            await self.observer(UsageEvent(kind="tool_started", tool_name=tool.name))


async def _cancel_and_drain(result: RunResultStreaming) -> None:
    result.cancel()
    # The SDK owns its background tasks. Draining completes its cancellation and
    # resource cleanup; retain the original exception rather than a drain error.
    with suppress(Exception, asyncio.CancelledError):
        async for _ in result.stream_events():
            pass


class SdkProvider:
    def __init__(self, settings: Settings, *, usage_observer: UsageObserver | None = None, prompt_variant: str | None = None):
        self.settings = settings
        self.usage_observer = usage_observer
        self.prompt_variant = prompt_variant
        # One keep-alive client per runtime: per-turn clients paid a TLS handshake each turn.
        self._client: AsyncOpenAI | None = None
        set_tracing_disabled(True)

    def _openai(self, key: str) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=key,
                max_retries=0,
                http_client=openai_http_client(self.settings.provider_force_ipv4),
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            client, self._client = self._client, None
            await client.close()

    async def run(self, **kwargs: Any) -> AiOutput:
        """Legacy single-message view (evals/scripts): bubbles joined as ai-events-v1 sends them."""
        return (await self.run_reply(**kwargs)).joined()

    async def run_reply(
        self,
        *,
        bot_id: str,
        history: list[dict],
        tools: list[FunctionTool],
        context: Any,
        on_progress: Callable[[], Awaitable[None]],
        model_override: Model | str | None = None,
        usage_observer: UsageObserver | None = None,
    ) -> AiReply:
        if bot_id not in LEGACY_BOTS:
            raise DomainError(404, "BOT_NOT_FOUND", "Không tìm thấy trợ lý.")
        set_tracing_disabled(True)
        async def observe(event: UsageEvent):
            if usage_observer:
                await usage_observer(event)
            if self.usage_observer:
                await self.usage_observer(event)

        async with asyncio.timeout(RUN_TIMEOUT_SECONDS):
            if isinstance(model_override, Model):
                return await self._stream(
                    bot_id, history, tools, context, on_progress, model_override, observe
                )
            key = self.settings.openai_api_key.get_secret_value()
            if (
                not key
                or not (model_override or self.settings.openai_model)
                or not self.settings.ai_available_for(getattr(getattr(context, "actor", None), "user_id", None))
            ):
                raise DomainError(503, "AI_UNAVAILABLE", "Trò chuyện AI hiện chưa khả dụng.")
            model = OpenAIResponsesModel(
                model_override or self.settings.openai_model, self._openai(key)
            )
            return await self._stream(bot_id, history, tools, context, on_progress, model, observe)

    async def _stream(
        self,
        bot_id: str,
        history: list[dict],
        tools: list[FunctionTool],
        context: Any,
        on_progress: Callable[[], Awaitable[None]],
        model: Model,
        observer: UsageObserver,
    ) -> AiReply:
        guard = getattr(context, "before_dispatch", None)
        if guard is not None:
            from app.ai.guest_model import GuestGuardedModel

            model = GuestGuardedModel(model, guard)
        has_scope = bot_id == "nhip" and getattr(context, "mood_scope", None) is not None
        runtime_context = hasattr(context, 'sources')
        intent = conversation_intent(bot_id, history, scoped=has_scope) if runtime_context else 'analysis'
        analytical = intent == 'analysis'
        scoped_mood = has_scope and analytical
        journal_mode = bot_id == "nhip" and runtime_context and not has_scope
        journal_allowed = journal_mode and not journal_read_refused(history)
        if journal_mode:
            context.journal_read_allowed = journal_allowed
        selected_tools: list[Tool] = [tool for tool in tools if (analytical or tool.name != 'read_mood_summary') and (journal_allowed or tool.name != 'search_journal_entries')]
        runtime_guidance = conversation_instructions(bot_id, intent) if runtime_context else ''
        # Flag off: byte-identical single-message contract. Scoped mood analysis is always
        # rendered by the backend as one message.
        multi = self.settings.ai_multi_message_enabled and not scoped_mood
        output_type: type = (
            MoodAnalysisPlan if scoped_mood
            else (NhipReply if multi else NhipOutput) if journal_mode
            else CompanionReply if multi
            else AiOutput
        )
        agent = Agent[Any](
            name=f"MoodPrint:{bot_id}",
            instructions=instructions(bot_id, self.prompt_variant) + source_instructions(context, bot_id, mood_analysis=analytical) + (journal_instructions(context) if journal_mode else "") + runtime_guidance + (MULTI_MESSAGE_GUIDANCE if multi else ""),
            model=model,
            tools=selected_tools,
            output_type=output_type,
            output_guardrails=[] if scoped_mood else [_no_unreceipted_claim],
            model_settings=ModelSettings(
                store=False,
                parallel_tool_calls=False,
                max_tokens=1200,
                timeout=30,
                retry=ModelRetrySettings(max_retries=0),
            ),
        )
        result = Runner.run_streamed(
            agent,
            input=cast(list[TResponseInputItem], history),
            context=context,
            max_turns=3,
            hooks=_BudgetHooks(on_progress, observer),
            run_config=RunConfig(tracing_disabled=True, trace_include_sensitive_data=False),
        )
        try:
            # Raw deltas and intermediate tool text remain inside the SDK. Only
            # the complete schema-validated result is returned to the caller.
            async for _ in result.stream_events():
                pass
            if scoped_mood:
                plan = MoodAnalysisPlan.model_validate(result.final_output)
                if runtime_context:
                    brief, omit_mean = requested_presentation(history)
                    if brief:
                        plan.detail = 'brief'
                    if omit_mean:
                        plan.include_mean = False
                return AiReply(parts=[render_mood_analysis(plan, context)])
            if journal_mode:
                if multi:
                    return AiReply(parts=render_journal_reply(NhipReply.model_validate(result.final_output), context))
                return AiReply(parts=[render_journal_output(NhipOutput.model_validate(result.final_output), context)])
            if multi:
                reply = CompanionReply.model_validate(result.final_output)
                parts = [AiOutput(text=bubble.text, cards=bubble.cards) for bubble in reply.messages]
            else:
                parts = [AiOutput.model_validate(result.final_output)]
            if any(has_journal_link(part.text) for part in parts):
                raise DomainError(409, "JOURNAL_EVIDENCE_REQUIRED", "Chưa đọc được nguồn nhật ký cho lượt này.")
            return AiReply(parts=parts)
        except BaseException as error:
            await _cancel_and_drain(result)
            if isinstance(error, UserError) and isinstance(error.__cause__, DomainError):
                raise error.__cause__ from None
            raise

    async def run_proactive(
        self,
        *,
        bot_id: str,
        slot: str,
        input_item: dict,
        output_type: type,
        teen: bool,
        on_progress: Callable[[], Awaitable[None]],
        model_override: Model | str | None = None,
        usage_observer: UsageObserver | None = None,
        user_id: Any = None,
    ) -> Any:
        """One check-in: no transcript, no tools, no tracing; a single system-built input item."""
        from app.ai.prompts import proactive_instructions

        if bot_id not in LEGACY_BOTS:
            raise DomainError(404, "BOT_NOT_FOUND", "Không tìm thấy trợ lý.")
        set_tracing_disabled(True)
        if isinstance(model_override, Model):
            model: Model = model_override
        else:
            key = self.settings.openai_api_key.get_secret_value()
            if not key or not (model_override or self.settings.openai_model) or not self.settings.ai_available_for(user_id):
                raise DomainError(503, "AI_UNAVAILABLE", "Trò chuyện AI hiện chưa khả dụng.")
            model = OpenAIResponsesModel(model_override or self.settings.openai_model, self._openai(key))
        agent = Agent[Any](
            name=f"MoodPrint:{bot_id}:proactive",
            instructions=instructions(bot_id, self.prompt_variant) + proactive_instructions(bot_id, slot, teen=teen),
            model=model,
            tools=[],
            output_type=output_type,
            output_guardrails=[_no_unreceipted_claim],
            # Short, structured messages: low effort cuts latency and reasoning-token overruns
            # (measured: 2 of 91 default-effort generations hit max_output_tokens or the timeout).
            model_settings=ModelSettings(
                store=False, max_tokens=1200, timeout=30, retry=ModelRetrySettings(max_retries=0),
                reasoning=Reasoning(effort="low"),
            ),
        )

        async def observe(event: UsageEvent):
            if usage_observer:
                await usage_observer(event)
            if self.usage_observer:
                await self.usage_observer(event)

        async with asyncio.timeout(RUN_TIMEOUT_SECONDS):
            result = Runner.run_streamed(
                agent,
                input=cast(list[TResponseInputItem], [input_item]),
                max_turns=2,
                hooks=_BudgetHooks(on_progress, observe),
                run_config=RunConfig(tracing_disabled=True, trace_include_sensitive_data=False),
            )
            try:
                async for _ in result.stream_events():
                    pass
                return cast(Any, output_type).model_validate(result.final_output)
            except BaseException as error:
                await _cancel_and_drain(result)
                if isinstance(error, UserError) and isinstance(error.__cause__, DomainError):
                    raise error.__cause__ from None
                raise

    async def run_specialist(
        self,
        *,
        name: str,
        instructions: str,
        input_item: dict,
        output_type: type,
        context: Any,
        on_progress: Callable[[], Awaitable[None]],
        usage_observer: UsageObserver | None,
        limit_seconds: float,
        model_override: Model | str | None = None,
        user_id: Any = None,
    ) -> Any:
        """One bounded consultation (phase-2/05 §6): purpose-only instructions, no persona, no
        tools, no transcript, one model call, no tracing, no retries, a hard timeout."""
        set_tracing_disabled(True)
        if isinstance(model_override, Model):
            model: Model = model_override
        else:
            key = self.settings.openai_api_key.get_secret_value()
            if not key or not (model_override or self.settings.openai_model) or not self.settings.ai_available_for(user_id):
                raise DomainError(503, "AI_UNAVAILABLE", "Trò chuyện AI hiện chưa khả dụng.")
            model = OpenAIResponsesModel(model_override or self.settings.openai_model, self._openai(key))
        agent = Agent[Any](
            name=name,
            instructions=instructions,
            model=model,
            tools=[],
            output_type=output_type,
            # 600 includes reasoning tokens (R-15: 300 risks response.incomplete); output is
            # still bounded by the schema (≤ 240 characters of text).
            model_settings=ModelSettings(
                store=False, max_tokens=600, timeout=limit_seconds, retry=ModelRetrySettings(max_retries=0),
                reasoning=Reasoning(effort="low"),
            ),
        )

        async def observe(event: UsageEvent):
            if usage_observer:
                await usage_observer(event)
            if self.usage_observer:
                await self.usage_observer(event)

        async with asyncio.timeout(limit_seconds):
            result = Runner.run_streamed(
                agent,
                input=cast(list[TResponseInputItem], [input_item]),
                context=context,
                max_turns=1,
                hooks=_BudgetHooks(on_progress, observe, model_limit=1, tool_limit=0),
                run_config=RunConfig(tracing_disabled=True, trace_include_sensitive_data=False),
            )
            try:
                async for _ in result.stream_events():
                    pass
                return cast(Any, output_type).model_validate(result.final_output)
            except BaseException as error:
                await _cancel_and_drain(result)
                if isinstance(error, UserError) and isinstance(error.__cause__, DomainError):
                    raise error.__cause__ from None
                raise
