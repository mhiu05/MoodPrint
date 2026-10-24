"""Content-free provider observations, including starts whose usage is unknown."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class UsageEvent:
    kind: Literal["request_started", "response_received", "tool_started"]
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    tool_name: str | None = None


UsageObserver = Callable[[UsageEvent], Awaitable[None]]
