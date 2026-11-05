"""In-process sliding-window limits. The MVP runs one backend process (deploy/README.md)."""

import math
import time
from collections import deque

from app.core.errors import DomainError


class AttemptLimiter:
    def __init__(
        self,
        limit: int,
        window_seconds: float,
        code: str = "RATE_LIMITED",
        message: str = "Bạn đã thử quá nhiều lần. Vui lòng đợi vài phút.",
        *, max_keys: int = 10_000,
    ):
        self.limit, self.window = limit, window_seconds
        self.code, self.message = code, message
        self.attempts: dict[str, deque[float]] = {}
        self.max_keys = max_keys
        self.prune_after = 0.0

    def check(self, *keys: str) -> None:
        stamp = time.monotonic()
        new_keys = set(keys) - self.attempts.keys()
        if len(self.attempts) + len(new_keys) > self.max_keys:
            if stamp >= self.prune_after:
                self.attempts = {k: v for k, v in self.attempts.items() if v and v[-1] > stamp - self.window}
                self.prune_after = stamp + min(self.window, 1)
            if len(self.attempts) + len(set(keys) - self.attempts.keys()) > self.max_keys:
                # Never evict a live cooldown: eviction would reset an attacker's budget.
                raise DomainError(429, self.code, self.message, True, retry_after=max(1, math.ceil(self.window)))
        for key in keys:
            bucket = self.attempts.setdefault(key, deque())
            while bucket and bucket[0] <= stamp - self.window:
                bucket.popleft()
            if len(bucket) >= self.limit:
                raise DomainError(429, self.code, self.message, True,
                                  retry_after=max(1, math.ceil(bucket[0] + self.window - stamp)))
        for key in keys:
            self.attempts[key].append(stamp)
