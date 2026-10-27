"""SDK model wrapper that runs the guest dispatch guard immediately before every provider request.

The guard performs the reservation marker and the fresh lifetime decision; this wrapper invokes
it as the last awaited step before delegating to the real model, after the SDK's own queue work.
It forwards the SDK's positional/keyword arguments untouched so the pinned interface is preserved.
The remote request that follows is physical dispatch, outside the logical authorization boundary.
"""

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from agents import Model
from agents.items import ModelResponse, TResponseStreamEvent


class GuestGuardedModel(Model):
    def __init__(self, delegate: Model, before_dispatch: Callable[[], Awaitable[None]]):
        self.delegate, self.before_dispatch = delegate, before_dispatch

    async def get_response(self, *args: Any, **kwargs: Any) -> ModelResponse:
        await self.before_dispatch()
        return await self.delegate.get_response(*args, **kwargs)

    async def stream_response(
        self, *args: Any, **kwargs: Any
    ) -> AsyncIterator[TResponseStreamEvent]:
        await self.before_dispatch()
        async for event in self.delegate.stream_response(*args, **kwargs):
            yield event

    async def close(self) -> None:
        closer = getattr(self.delegate, "close", None)
        if closer is not None:
            await closer()
