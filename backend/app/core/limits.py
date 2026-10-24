"""In-process sliding-window limits. The MVP runs one backend process (deploy/README.md)."""

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
    ):
        self.limit, self.window = limit, window_seconds
        self.code, self.message = code, message
        self.attempts: dict[str, deque[float]] = {}

    def check(self, *keys: str) -> None:
        stamp = time.monotonic()
        for key in keys:
            bucket = self.attempts.setdefault(key, deque())
            while bucket and bucket[0] <= stamp - self.window:
                bucket.popleft()
            if len(bucket) >= self.limit:
                raise DomainError(429, self.code, self.message, True)
        for key in keys:
            self.attempts[key].append(stamp)
        if len(self.attempts) > 10_000:
            self.attempts = {
                k: v for k, v in self.attempts.items() if v and v[-1] > stamp - self.window
            }
