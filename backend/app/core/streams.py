"""Per-user SSE slots for the single backend process (see deploy/README.md)."""

from uuid import UUID

from app.core.errors import DomainError


class StreamSlots:
    def __init__(self, limit: int):
        self.limit = limit
        self.active: dict[UUID, int] = {}

    def reserve(self, user_id: UUID):
        """Reserve synchronously, before any await, so concurrent requests cannot overshoot."""
        if self.active.get(user_id, 0) >= self.limit:
            raise DomainError(
                429, "STREAM_LIMIT", "Có quá nhiều kết nối đang mở. Hãy đóng bớt tab.", True
            )
        self.active[user_id] = self.active.get(user_id, 0) + 1
        released = False

        def release() -> None:
            nonlocal released
            if released:
                return
            released = True
            remaining = self.active.get(user_id, 1) - 1
            if remaining > 0:
                self.active[user_id] = remaining
            else:
                self.active.pop(user_id, None)

        return release
