"""Durable shared admission for guest creation: HMAC-keyed counters in PostgreSQL.

No raw address, user identifier or device fingerprint is stored. Keys are rotating HMACs of
(scope, window, canonical network); only ``request.client`` is trusted, so a spoofed forwarding
header can neither evade nor change a counter. GE-07.1 extends this module with trial quotas.
"""

import hashlib
import hmac
import ipaddress
from datetime import UTC, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import Request
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DomainError
from app.modules.guests.models import GuestAbuseBucket
from app.modules.guests.policy import database_time

BANGKOK = ZoneInfo("Asia/Bangkok")

# (limit, window seconds). Fixed UTC windows; hour/day creation windows follow Bangkok civil time.
INTENT_PER_IP = (10, 600)
INTENT_GLOBAL = (100, 60)
FAILED_SIGNUP_PER_IP = (10, 600)
CREATION_PER_HOUR = 3
CREATION_PER_DAY = 10
GLOBAL_NETWORK = "global"


def _network(host: str | None) -> str:
    """Canonical network: IPv4-mapped IPv6 as IPv4, other IPv6 by its /64, no forwarding headers."""
    try:
        address = ipaddress.ip_address(host or "")
    except ValueError:
        return "unknown:" + (host or "").lower()[:64]
    if isinstance(address, ipaddress.IPv6Address):
        if address.ipv4_mapped:
            return str(address.ipv4_mapped)
        return str(ipaddress.ip_network(f"{address}/64", strict=False))
    return str(address)


def _digest(request_or_app, window_start: datetime, scope: str, network: str) -> str:
    app = getattr(request_or_app, "app", request_or_app)
    secret = app.state.settings.guest_abuse_hmac_key.get_secret_value()
    if not secret:
        raise DomainError(503, "GUEST_DISABLED", "Dùng thử tạm thời chưa mở. Vui lòng quay lại sau.")
    message = f"{scope}|{int(window_start.timestamp())}|{network}"
    return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()


def canonical_client_key(request: Request, window_start: datetime, scope: str) -> str:
    host = request.client.host if request.client else None
    return _digest(request, window_start, scope, _network(host))


def global_key(request: Request, window_start: datetime, scope: str) -> str:
    return _digest(request, window_start, scope, GLOBAL_NETWORK)


def fixed_window(now: datetime, seconds: int) -> tuple[datetime, datetime]:
    epoch = int(now.timestamp())
    start = datetime.fromtimestamp(epoch - epoch % seconds, UTC)
    return start, start + timedelta(seconds=seconds)


def bangkok_day(now: datetime) -> tuple[datetime, datetime]:
    local = now.astimezone(BANGKOK).replace(hour=0, minute=0, second=0, microsecond=0)
    start = local.astimezone(UTC)
    return start, start + timedelta(days=1)


def limit_error(wait: timedelta) -> DomainError:
    return DomainError(
        429,
        "GUEST_CREATION_LIMIT",
        "Có quá nhiều lượt dùng thử từ mạng này. Vui lòng thử lại sau.",
        True,
        retry_after=max(1, int(wait.total_seconds()) + 1),
    )


async def reserve_bucket(
    db: AsyncSession,
    *,
    scope: str,
    key_hash: str,
    window: tuple[datetime, datetime],
    limit: int,
) -> bool:
    """Atomically count one admission; False (nothing written) once the window's limit is full."""
    start, end = window
    inserted = insert(GuestAbuseBucket).values(
        scope=scope, key_hash=key_hash, window_start=start, count=1, reserved=0, expires_at=end
    )
    statement = inserted.on_conflict_do_update(
        index_elements=[
            GuestAbuseBucket.scope,
            GuestAbuseBucket.key_hash,
            GuestAbuseBucket.window_start,
        ],
        set_={"count": GuestAbuseBucket.count + 1},
        where=GuestAbuseBucket.count < limit,
    ).returning(GuestAbuseBucket.count)
    return (await db.scalar(statement)) is not None


async def reserve_guest_intent(db: AsyncSession, request: Request) -> None:
    """Shared admission for a new intent: global per minute first, then per network."""
    now = await database_time(db)
    limit, seconds = INTENT_GLOBAL
    window = fixed_window(now, seconds)
    if not await reserve_bucket(
        db,
        scope="intent_global",
        key_hash=global_key(request, window[0], "intent_global"),
        window=window,
        limit=limit,
    ):
        raise limit_error(window[1] - now)
    limit, seconds = INTENT_PER_IP
    window = fixed_window(now, seconds)
    if not await reserve_bucket(
        db,
        scope="intent",
        key_hash=canonical_client_key(request, window[0], "intent"),
        window=window,
        limit=limit,
    ):
        raise limit_error(window[1] - now)


async def reserve_guest_creation(db: AsyncSession, request: Request, attempt_id: UUID) -> None:
    """Count one trial against the network's hour and day caps.

    Called exactly once per attempt, in the transaction that moves it to ``signup_started``; the
    count is kept (never refunded) once an upstream request may have been sent, and rolls back
    with that transaction when this raises.
    """
    now = await database_time(db)
    for scope, window, limit in (
        ("creation_hour", fixed_window(now, 3600), CREATION_PER_HOUR),
        ("creation_day", bangkok_day(now), CREATION_PER_DAY),
    ):
        if not await reserve_bucket(
            db,
            scope=scope,
            key_hash=canonical_client_key(request, window[0], scope),
            window=window,
            limit=limit,
        ):
            raise limit_error(window[1] - now)


async def assert_failed_signups_allowed(db: AsyncSession, request: Request) -> None:
    """Refuse a new upstream signup once this network keeps failing its challenge or signups."""
    now = await database_time(db)
    limit, seconds = FAILED_SIGNUP_PER_IP
    window = fixed_window(now, seconds)
    count = await db.scalar(
        select(GuestAbuseBucket.count).where(
            GuestAbuseBucket.scope == "failed_signup",
            GuestAbuseBucket.key_hash == canonical_client_key(request, window[0], "failed_signup"),
            GuestAbuseBucket.window_start == window[0],
        )
    )
    if count is not None and count >= limit:
        raise limit_error(window[1] - now)


async def record_failed_signup(db: AsyncSession, request: Request) -> None:
    now = await database_time(db)
    window = fixed_window(now, FAILED_SIGNUP_PER_IP[1])
    await reserve_bucket(
        db,
        scope="failed_signup",
        key_hash=canonical_client_key(request, window[0], "failed_signup"),
        window=window,
        limit=1_000_000,
    )


async def release_guest_creation(db: AsyncSession, request: Request) -> None:
    """Refund the creation count only when the provider explicitly rejected (nothing was created)."""
    now = await database_time(db)
    for scope, window in (
        ("creation_hour", fixed_window(now, 3600)),
        ("creation_day", bangkok_day(now)),
    ):
        await db.execute(
            update(GuestAbuseBucket)
            .where(
                GuestAbuseBucket.scope == scope,
                GuestAbuseBucket.key_hash == canonical_client_key(request, window[0], scope),
                GuestAbuseBucket.window_start == window[0],
                GuestAbuseBucket.count > 0,
            )
            .values(count=GuestAbuseBucket.count - 1)
        )
