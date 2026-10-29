"""Durable shared admission for guest creation: HMAC-keyed counters in PostgreSQL.

No raw address, user identifier or device fingerprint is stored. Keys are rotating HMACs of
(scope, window, canonical network); only ``request.client`` is trusted, so a spoofed forwarding
header can neither evade nor change a counter. GE-07.1 extends this module with trial quotas.
"""

import asyncio
import hashlib
import hmac
import ipaddress
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from fastapi import Request
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts import GuestQuota
from app.core.errors import DomainError
from app.core.security import digest
from app.infrastructure.database.models import User
from app.modules.guests.models import GuestAbuseBucket, GuestOperationLink, GuestUsage
from app.modules.guests.policy import database_time, guest_expired

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


async def reserve_guest_creation(db: AsyncSession, request: Request, attempt_id: UUID) -> datetime:
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
    # Keep this exact sample for the in-process definite-rejection refund. The
    # provider-start/orphan clock must be sampled separately after admission waits.
    return now


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


async def release_guest_creation(db: AsyncSession, request: Request, reserved_at: datetime) -> None:
    """Refund the creation count only when the provider explicitly rejected (nothing was created)."""
    for scope, window in (
        ("creation_hour", fixed_window(reserved_at, 3600)),
        ("creation_day", bangkok_day(reserved_at)),
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


# ---- trial quotas (GE-07.1): durable lifetime counters + short operation claims -------------------

ADMISSION_LOCK = 724_031  # one shared advisory lock serializes every guest paid admission
QUOTA_LEASE_SECONDS = 45
QUOTA_HEARTBEAT_SECONDS = 5
SEMANTIC_MEMORY_CAP = 20


@dataclass(frozen=True)
class QuotaClaim:
    operation_key_hash: str
    lease_token: UUID


def _busy(code: str, message: str, wait: int = 5) -> DomainError:
    return DomainError(429, code, message, True, retry_after=wait)


async def reserve_guest_quota(
    db: AsyncSession,
    user: User,
    *,
    kind: str,
    operation_key: str,
    payload_digest: str,
    settings,
    voice_milliseconds: int = 0,
    semantic_document: bool = True,
) -> QuotaClaim:
    """Admit one AI turn / voice clip / embedding for this trial, atomically and durably.

    Counters live in ``guest_usage`` (lifetime, never per day, never reset by restart, a new tab or
    rotated credentials). A repeated operation key with the same payload returns the existing claim
    without a second increment; a different payload conflicts. Nothing is refunded after dispatch.
    """
    key_hash = digest(operation_key)
    existing = await db.get(GuestOperationLink, (user.id, kind, key_hash))
    if existing is not None:
        if existing.payload_digest != payload_digest:
            raise DomainError(
                409, "IDEMPOTENCY_CONFLICT", "Mã thao tác đã được dùng với nội dung khác."
            )
        if kind == "voice" and existing.state in ("dispatched", "completed"):
            raise DomainError(
                409,
                "VOICE_ALREADY_PROCESSED",
                "Bản ghi âm này đã được xử lý. Hãy ghi một bản mới.",
            )
        return QuotaClaim(key_hash, existing.lease_token)
    await db.execute(select(func.pg_advisory_xact_lock(ADMISSION_LOCK)))
    now = await database_time(db)
    usage = await db.scalar(select(GuestUsage).where(GuestUsage.user_id == user.id).with_for_update())
    if usage is None:
        raise DomainError(409, "GUEST_REQUIRED", "Không tìm thấy lượt dùng thử.")
    caps = {
        "ai": (settings.guest_ai_per_minute, settings.guest_ai_concurrency, settings.guest_ai_global_concurrency),
        "voice": (settings.guest_voice_per_minute, settings.guest_voice_concurrency, settings.guest_voice_global_concurrency),
        "embed": (settings.guest_ai_per_minute, 1, settings.guest_ai_global_concurrency),
    }
    per_minute, per_user, global_cap = caps[kind]
    recent = await db.scalar(
        select(func.count())
        .select_from(GuestOperationLink)
        .where(
            GuestOperationLink.user_id == user.id,
            GuestOperationLink.kind == kind,
            GuestOperationLink.created_at > now - timedelta(seconds=60),
        )
    )
    if (recent or 0) >= per_minute:
        raise _busy("GUEST_RATE_LIMITED", "Bạn đang thao tác hơi nhanh. Vui lòng đợi một chút.", 10)
    live = (
        GuestOperationLink.kind == kind,
        GuestOperationLink.state.in_(("claimed", "dispatched")),
        GuestOperationLink.lease_until > now,
    )
    mine = await db.scalar(
        select(func.count()).select_from(GuestOperationLink).where(GuestOperationLink.user_id == user.id, *live)
    )
    if (mine or 0) >= per_user:
        raise _busy("GUEST_BUSY", "Đang xử lý yêu cầu trước của bạn. Vui lòng đợi xong rồi thử lại.")
    everyone = await db.scalar(select(func.count()).select_from(GuestOperationLink).where(*live))
    if (everyone or 0) >= global_cap:
        raise _busy("GUEST_CAPACITY", "Hệ thống dùng thử đang bận. Vui lòng thử lại sau ít phút.", 15)
    exhausted = DomainError(
        429, "GUEST_QUOTA_EXHAUSTED", "Bạn đã dùng hết lượt thử của phiên này.", False
    )
    if kind == "ai":
        if usage.ai_turns >= settings.guest_ai_turns:
            raise exhausted
        usage.ai_turns += 1
    elif kind == "voice":
        if (
            usage.voice_clips >= settings.guest_voice_clips
            or usage.voice_milliseconds + voice_milliseconds > settings.guest_voice_seconds * 1000
        ):
            raise exhausted
        usage.voice_clips += 1
        usage.voice_milliseconds += voice_milliseconds
    elif semantic_document:
        if usage.semantic_memories >= SEMANTIC_MEMORY_CAP:
            raise exhausted
        usage.semantic_memories += 1
    token = uuid4()
    db.add(
        GuestOperationLink(
            user_id=user.id,
            kind=kind,
            operation_key_hash=key_hash,
            payload_digest=payload_digest,
            state="claimed",
            worker_id=uuid4(),
            lease_token=token,
            lease_until=now + timedelta(seconds=QUOTA_LEASE_SECONDS),
        )
    )
    await db.flush()
    return QuotaClaim(key_hash, token)


async def finish_guest_quota(
    db: AsyncSession, user_id: UUID, kind: str, operation_key_hash: str, lease_token: UUID
) -> None:
    """Mark a claim complete in its own owner-ordered transaction; a missing/fenced link is a no-op."""
    await db.execute(
        update(GuestOperationLink)
        .where(
            GuestOperationLink.user_id == user_id,
            GuestOperationLink.kind == kind,
            GuestOperationLink.operation_key_hash == operation_key_hash,
            GuestOperationLink.lease_token == lease_token,
            GuestOperationLink.state.in_(("claimed", "dispatched")),
        )
        .values(state="completed")
    )


async def renew_guest_quota(database, user_id: UUID, kind: str, claim: QuotaClaim) -> tuple[float, bool]:
    """Renew only an existing live fenced claim; a dead/missing owner or lease never revives."""
    from app.modules.guests.accounting import _locked
    from app.modules.guests.policy import assert_guest_active
    before = time.monotonic()
    async with database.require()() as db, db.begin():
        user = await db.scalar(select(User).where(User.id == user_id).with_for_update())
        if user is None or user.status != "active":
            raise DomainError(409, "GUEST_OPERATION_FENCED", "Lượt xử lý đã kết thúc.")
        await assert_guest_active(db, user)
        key = (user_id, kind, claim.operation_key_hash)
        link = await db.get(GuestOperationLink, key)
        reservation = None
        if link and link.reservation_id:
            _day, reservation = await _locked(db, link.reservation_id)
        link = await db.get(GuestOperationLink, key, with_for_update=True, populate_existing=True)
        now = await database_time(db)
        if (link is None or link.lease_token != claim.lease_token or link.state not in ("claimed", "dispatched")
                or link.lease_until <= now or (reservation is not None and reservation.state not in ("reserved", "dispatched"))):
            raise DomainError(409, "GUEST_OPERATION_FENCED", "Lượt xử lý đã kết thúc.")
        link.lease_until = min(user.guest_expires_at, now + timedelta(seconds=QUOTA_LEASE_SECONDS))
        if reservation is not None:
            reservation.lease_until = link.lease_until
        cutoff = before + max(0, (link.lease_until - now).total_seconds())
        trial_ends = link.lease_until == user.guest_expires_at
    return cutoff, trial_ends


@asynccontextmanager
async def maintain_guest_quota(database, user_id: UUID, kind: str, claim: QuotaClaim | None):
    """Five-second heartbeat while logically active; losing the fence cancels the owning task."""
    if claim is None:
        yield
        return
    cutoff, trial_ends = await renew_guest_quota(database, user_id, kind, claim)
    caller = asyncio.current_task()
    failure: DomainError | None = None
    async def heartbeat():
        nonlocal failure, cutoff, trial_ends
        try:
            while True:
                # A blocked DB/pool/owner lock must not let the current provider outlive
                # its existing slot while another admission treats that slot as free.
                async with asyncio.timeout(max(0, cutoff - time.monotonic())):
                    await asyncio.sleep(QUOTA_HEARTBEAT_SECONDS)
                    cutoff, trial_ends = await renew_guest_quota(database, user_id, kind, claim)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            # The local cutoff can conservatively precede DB T by the round trip.
            # Keep the reason captured when that lease was granted, rather than race
            # another timer to decide whether the trial or only the slot ended.
            failure = error if isinstance(error, DomainError) else (
                guest_expired() if isinstance(error, TimeoutError) and trial_ends else
                DomainError(409, "GUEST_OPERATION_FENCED", "Lượt xử lý đã kết thúc.")
            )
            if caller is not None:
                caller.cancel()
    task = asyncio.create_task(heartbeat())
    try:
        yield
    except asyncio.CancelledError:
        if failure is not None:
            raise failure from None
        raise
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def guest_quota_view(db: AsyncSession, user: User, settings) -> GuestQuota:
    usage = await db.get(GuestUsage, user.id)
    turns, clips, millis = (
        (usage.ai_turns, usage.voice_clips, usage.voice_milliseconds) if usage else (0, 0, 0)
    )
    return GuestQuota(
        ai_turns_remaining=max(0, settings.guest_ai_turns - turns),
        voice_clips_remaining=max(0, settings.guest_voice_clips - clips),
        voice_seconds_remaining=max(0, settings.guest_voice_seconds * 1000 - millis) / 1000,
    )
