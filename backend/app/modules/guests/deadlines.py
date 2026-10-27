"""Conservative in-flight deadline bounds for a guest. They never grant lifetime, only cut it short.

A DB clock sample plus local monotonic elapsed time bounds cancellation and output. The local
monotonic reading is taken *before* the database round trip, so the round trip can never extend
the bound beyond the true T. Browser time is never used.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from app.core.errors import DomainError
from app.infrastructure.database.models import User
from app.modules.guests import policy


@dataclass(frozen=True)
class GuestDeadline:
    expires_at: datetime | None
    remaining_seconds: float
    monotonic_deadline: float

    def remaining(self, clock: Callable[[], float] = time.monotonic) -> float:
        """Seconds left on the local monotonic clock; compare synchronously right before sending."""
        return self.monotonic_deadline - clock()


async def guest_deadline(
    db, user: User, *, clock: Callable[[], float] = time.monotonic
) -> GuestDeadline | None:
    """The bound for a guest (None for registered). Raises GUEST_EXPIRED at or after T."""
    if user.account_kind != "guest":
        return None
    before = clock()
    at = await policy.database_time(db)
    if user.guest_expires_at is None or at >= user.guest_expires_at:
        raise policy.guest_expired()
    remaining = (user.guest_expires_at - at).total_seconds()
    return GuestDeadline(user.guest_expires_at, remaining, before + remaining)


async def final_guest_authorization(db, user: User) -> None:
    """Fresh database-clock decision immediately before a conditional write or commit."""
    await policy.assert_guest_active(db, user)


async def guard_guest_dispatch(database, actor) -> GuestDeadline | None:
    """Fresh DB sample right before an external send (model, tool, STT, embedding, export).

    Returns the deadline bound; the caller makes one more synchronous ``remaining() > 0`` check
    immediately before invoking the send, with no awaited queue in between. Registered actors
    return None. Cancellation can never recall a request the remote side already accepted.
    """
    if actor.account_kind != "guest":
        return None
    async with database.require()() as db:
        user = await db.get(User, actor.user_id)
        if user is None or user.status != "active":
            raise DomainError(401, "SESSION_EXPIRED", "Phiên đã kết thúc.")
        deadline = await guest_deadline(db, user)
    if deadline is None or deadline.remaining() <= 0:
        raise policy.guest_expired()
    return deadline
