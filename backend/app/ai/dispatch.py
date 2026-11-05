"""Physical model-call admission for one API + one dedicated proactive process.

No database checkout is held by this gate. It is not cross-process coordination:
the candidate API50/proactive2 split (52 total) requires one of each, never replicas.
"""

import asyncio
import logging
import time
from contextlib import asynccontextmanager

from agents import Model, RunHooks

from app.core.errors import DomainError

log = logging.getLogger("moodprint")


def overloaded():
    return DomainError(503, "AI_OVERLOADED", "Trợ lý đang hơi đông. Bạn hãy thử lại sau ít giây.",
                       True, retry_after=2)


class ProviderDispatchGate:
    def __init__(self, capacity: int, max_queue: int, background_capacity: int):
        if capacity < 1 or max_queue < 0 or not 1 <= background_capacity <= capacity:
            raise ValueError("Invalid dispatch capacity")
        self.capacity, self.max_queue = capacity, max_queue
        self.background_capacity = background_capacity
        self.active = self.waiting = self.background_active = self.peak = self.calls = 0
        self.condition = asyncio.Condition()

    @asynccontextmanager
    async def acquire(self, *, wait_seconds: float, background: bool = False):
        started = time.monotonic()

        def available():
            return self.active < self.capacity and (not background or self.background_active < self.background_capacity)

        async with self.condition:
            if not available():
                if self.waiting >= self.max_queue:
                    raise overloaded()
                self.waiting += 1
                try:
                    async with asyncio.timeout(wait_seconds):
                        await self.condition.wait_for(available)
                except TimeoutError:
                    raise overloaded() from None
                finally:
                    self.waiting -= 1
            self.active += 1
            self.background_active += int(background)
            self.calls += 1
            self.peak = max(self.peak, self.active)
        log.info("metric=ai_dispatch_queue_ms value=%.3f", (time.monotonic() - started) * 1000)
        try:
            yield
        finally:
            async with self.condition:
                self.active -= 1
                self.background_active -= int(background)
                self.condition.notify_all()


class DispatchModel(Model):
    """Wrap each actual SDK model exchange, including nested specialist/tool turns."""
    def __init__(self, delegate, gate, timeout, background=False):
        self.delegate, self.gate, self.timeout, self.background = delegate, gate, timeout, background
        self.fences = {}

    def prepare(self, input_items, fence):
        # Pinned SDK passes this exact filtered list to the hook and model exchange.
        # Key by identity, not content: concurrent users with identical prompts cannot
        # borrow one another's authority. No global/current-user mutable callback.
        if len(self.fences) >= self.gate.max_queue + self.gate.capacity:
            raise overloaded()
        self.fences[id(input_items)] = fence

    def take_fence(self, args, kwargs):
        input_items = kwargs.get("input") if "input" in kwargs else args[1]
        fence = self.fences.pop(id(input_items), None)
        if fence is None:
            raise DomainError(503, "AI_DISPATCH_UNSUPPORTED", "Chưa xác minh được quyền cho lượt này.")
        return fence

    async def get_response(self, *args, **kwargs):
        fence = self.take_fence(args, kwargs)
        async with self.gate.acquire(wait_seconds=self.timeout, background=self.background):
            await fence()
            started = time.monotonic()
            try:
                return await self.delegate.get_response(*args, **kwargs)
            finally:
                log.info("metric=ai_provider_duration_ms value=%.3f", (time.monotonic() - started) * 1000)

    async def stream_response(self, *args, **kwargs):
        fence = self.take_fence(args, kwargs)
        async with self.gate.acquire(wait_seconds=self.timeout, background=self.background):
            await fence()
            started, first = time.monotonic(), False
            source = self.delegate.stream_response(*args, **kwargs)
            try:
                async for event in source:
                    if not first and getattr(event, "type", "") == "response.output_text.delta":
                        first = True
                        log.info("metric=ai_sdk_first_delta_ms value=%.3f", (time.monotonic() - started) * 1000)
                    yield event
            finally:
                try:
                    closer = getattr(source, "aclose", None)
                    if closer:
                        await closer()
                finally:
                    log.info("metric=ai_provider_duration_ms value=%.3f", (time.monotonic() - started) * 1000)

    async def close(self):
        self.fences.clear()
        await self.delegate.close()


class PostQueueHooks(RunHooks):
    """Move the original per-operation authorization + request-start marker AFTER queue.

    Forward every other hook of the pinned SDK unchanged. Do not invoke start twice:
    it contains model-call caps, live journal/grant checks and financial observations.
    """
    def __init__(self, delegate):
        self.delegate = delegate

    async def on_llm_start(self, context, agent, system_prompt, input_items):
        model = agent.model
        if not isinstance(model, DispatchModel):
            raise DomainError(503, "AI_DISPATCH_UNSUPPORTED", "Đường gọi AI chưa hỗ trợ hàng đợi an toàn.")

        async def fence():
            await self.delegate.on_llm_start(context, agent, system_prompt, input_items)

        model.prepare(input_items, fence)

    async def on_llm_end(self, *args, **kwargs):
        return await self.delegate.on_llm_end(*args, **kwargs)

    async def on_agent_start(self, *args, **kwargs):
        return await self.delegate.on_agent_start(*args, **kwargs)

    async def on_agent_end(self, *args, **kwargs):
        return await self.delegate.on_agent_end(*args, **kwargs)

    async def on_handoff(self, *args, **kwargs):
        return await self.delegate.on_handoff(*args, **kwargs)

    async def on_tool_start(self, *args, **kwargs):
        return await self.delegate.on_tool_start(*args, **kwargs)

    async def on_tool_end(self, *args, **kwargs):
        return await self.delegate.on_tool_end(*args, **kwargs)
