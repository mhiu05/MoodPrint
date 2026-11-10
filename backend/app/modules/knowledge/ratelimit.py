"""In-process search throttle. This is a cost guard, not a security boundary."""

from __future__ import annotations

import asyncio
import time


class SearchLimiter:
    def __init__(self, per_minute: int, concurrency: int = 8) -> None:
        self.per_minute = per_minute
        self.hits: dict[str, list[float]] = {}
        self.gate = asyncio.Semaphore(concurrency)

    def allow(self, user_id: str, now: float | None = None) -> bool:
        moment = time.monotonic() if now is None else now
        recent = [item for item in self.hits.get(user_id, []) if moment - item < 60]
        if len(recent) >= self.per_minute:
            self.hits[user_id] = recent
            return False
        recent.append(moment)
        self.hits[user_id] = recent
        return True


LIMITER = SearchLimiter(20)
