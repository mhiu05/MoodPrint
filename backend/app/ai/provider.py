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

from app.ai.prompts import LEGACY_BOTS, instructions
from app.ai.schemas import AiOutput
from app.ai.usage import UsageEvent, UsageObserver
from app.core.config import Settings
from app.core.errors import DomainError

RUN_TIMEOUT_SECONDS = 30.0
_DURABLE_CLAIM = re.compile(
    r"(?:^|[.!?\n]\s*)(?:(?:mình|tôi|i)\s+)?"
    r"(?:đã\s+(?:lưu|ghi nhớ|xuất bản|gửi lời mời|kết nối)|"
    r"(?:have\s+)?(?:saved|published|sent\s+(?:the\s+)?invitation))\b",
    re.IGNORECASE,
)


@output_guardrail
async def _no_unreceipted_claim(
    context: RunContextWrapper[Any], agent: Agent[Any], output: AiOutput
) -> GuardrailFunctionOutput:
    # No current model-facing tool performs a durable write. This narrow check
    # catches common unsupported success statements; schema validation separately
    # rejects forged receipt/action fields. It is not a semantic safety classifier.
    return GuardrailFunctionOutput(
        output_info={"code": "UNRECEIPTED_ACTION_CLAIM"},
        tripwire_triggered=bool(_DURABLE_CLAIM.search(output.text)),
    )


class _BudgetHooks(RunHooks[Any]):
    def __init__(self, on_progress: Callable[[], Awaitable[None]], observer: UsageObserver | None = None):
        self.model_calls = 0
        self.tool_calls = 0
        self.on_progress = on_progress
        self.observer = observer

    async def on_llm_start(
        self,
        context: RunContextWrapper[Any],
        agent: Agent[Any],
        system_prompt: str | None,
        input_items: list[TResponseInputItem],
    ) -> None:
        self.model_calls += 1
        if self.model_calls > 3:
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
        if self.tool_calls > 2:
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
        set_tracing_disabled(True)

    async def run(
        self,
        *,
        bot_id: str,
        history: list[dict],
        tools: list[FunctionTool],
        context: Any,
        on_progress: Callable[[], Awaitable[None]],
        model_override: Model | str | None = None,
        usage_observer: UsageObserver | None = None,
    ) -> AiOutput:
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
            async with AsyncOpenAI(api_key=key, max_retries=0, timeout=30) as client:
                model = OpenAIResponsesModel(model_override or self.settings.openai_model, client)
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
    ) -> AiOutput:
        agent = Agent[Any](
            name=f"MoodPrint:{bot_id}",
            instructions=instructions(bot_id, self.prompt_variant),
            model=model,
            tools=list(tools),
            output_type=AiOutput,
            output_guardrails=[_no_unreceipted_claim],
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
            return AiOutput.model_validate(result.final_output)
        except BaseException as error:
            await _cancel_and_drain(result)
            if isinstance(error, UserError) and isinstance(error.__cause__, DomainError):
                raise error.__cause__ from None
            raise
