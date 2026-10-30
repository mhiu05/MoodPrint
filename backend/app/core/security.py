import hashlib
import hmac
import json
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DomainError
from app.infrastructure.database.models import AuthSession, Consent, Idempotency, User, now
from app.modules.guests import policy as guest_policy
from app.modules.guests.deadlines import final_guest_authorization, guest_deadline
from app.modules.guests.policy import assert_guest_active


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


@dataclass(frozen=True)
class Actor:
    user_id: UUID
    session_id: UUID
    auth_version: int
    # Server-owned kind loaded with the session; never taken from a request or provider metadata.
    account_kind: str = "registered"


async def verify_session(db: AsyncSession, session: AuthSession, user: User) -> None:
    # The immutable trial deadline is judged first, on the database clock, so a retained guest
    # row at T reports GUEST_EXPIRED (and clears cookies) rather than a generic expiry.
    await assert_guest_active(db, user)
    at = await guest_policy.database_time(db) if user.account_kind == "guest" else now()
    if (
        session.revoked
        or session.expires_at <= at
        or session.auth_version != user.auth_version
        or user.status != "active"
    ):
        raise DomainError(401, "SESSION_EXPIRED", "Phiên đã kết thúc. Vui lòng đăng nhập lại.")
    if user.suspended_until and user.suspended_until > at:
        raise DomainError(
            403, "ACCOUNT_SUSPENDED", "Tài khoản đang bị tạm khóa theo quy tắc cộng đồng."
        )
    # Supabase logout/revocation removes auth.sessions. A JWT signature alone is insufficient.
    exists = await db.scalar(
        text("select moodprint.is_provider_session_active(:sid,:uid)"),
        {"sid": session.id, "uid": user.id},
    )
    if not exists:
        raise DomainError(401, "SESSION_EXPIRED", "Phiên đã kết thúc. Vui lòng đăng nhập lại.")


async def load_actor(request: Request, db: AsyncSession) -> tuple[Actor, User]:
    """Authenticate on a connection the caller keeps.

    Session reads build the view on this same checkout. A second checkout queues
    behind the pool when many sessions are read at once.
    """
    token = request.cookies.get("moodprint_session")
    if not token:
        raise DomainError(401, "AUTH_REQUIRED", "Vui lòng đăng nhập.")
    identity = (
        await db.execute(
            select(AuthSession, User)
            .join(User, User.id == AuthSession.user_id)
            .where(AuthSession.token_hash == digest(token))
        )
    ).one_or_none()
    if identity is None:
        raise DomainError(401, "SESSION_EXPIRED", "Phiên đã kết thúc. Vui lòng đăng nhập lại.")
    session, user = identity
    await verify_session(db, session, user)
    if user.account_kind == "guest":
        # Conservative bound for the outermost output guard (never a lifetime grant).
        request.state.guest_output = await guest_deadline(db, user)
    idle = timedelta(hours=request.app.state.settings.session_idle_hours)
    if user.account_kind == "registered" and session.expires_at < now() + idle - timedelta(
        minutes=15
    ):
        # Sliding idle expiry, written at most every 15 minutes per session. A guest session
        # is capped at the immutable trial deadline and is never renewed.
        await db.execute(
            update(AuthSession)
            .where(AuthSession.id == session.id, AuthSession.revoked.is_(False))
            .values(expires_at=now() + idle)
        )
        # Matching hides users inactive for 30 days; same 15-minute write cadence.
        await db.execute(update(User).where(User.id == user.id).values(last_seen_at=now()))
        await db.commit()
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        csrf = request.headers.get("X-CSRF-Token", "")
        if not csrf or not hmac.compare_digest(digest(csrf), session.csrf_hash):
            raise DomainError(403, "CSRF_DENIED", "Phiên xác nhận đã thay đổi. Vui lòng tải lại.")
        origin = request.headers.get("Origin")
        if origin and origin.rstrip("/") != request.app.state.settings.frontend_origin.rstrip("/"):
            raise DomainError(403, "ORIGIN_DENIED", "Nguồn yêu cầu không hợp lệ.")
    return Actor(user.id, session.id, user.auth_version, user.account_kind), user


async def require_actor(request: Request) -> Actor:
    if not request.cookies.get("moodprint_session"):
        raise DomainError(401, "AUTH_REQUIRED", "Vui lòng đăng nhập.")
    async with request.app.state.database.require()() as db:
        actor, _user = await load_actor(request, db)
        return actor


async def require_registered_actor(actor: Actor = Depends(require_actor)) -> Actor:
    """Social, shared-activity, safety and staff surfaces are for permanent accounts only.

    ``require_actor`` runs first, so an expired guest is answered 401 GUEST_EXPIRED before this
    403. Frontend hiding is never the control; this is the default-deny gate.
    """
    if actor.account_kind != "registered":
        raise DomainError(
            403,
            "REGISTERED_REQUIRED",
            "Tạo tài khoản để dùng tính năng này. Lượt dùng thử không có tìm bạn và nhắn tin.",
        )
    return actor


async def lock_actor(
    db: AsyncSession, actor: Actor, *, eligible: bool = True, lock: bool = True
) -> User:
    # lock=False is for read-only polling that must not contend with writers.
    statement = select(User).where(User.id == actor.user_id)
    user = await db.scalar(statement.with_for_update() if lock else statement)
    return await verify_actor(db, actor, user, eligible=eligible)


async def verify_actor(
    db: AsyncSession, actor: Actor, user: User | None, *, eligible: bool = True
) -> User:
    """Revalidate an actor after the caller acquires its account gate.

    Pair/discovery transactions already load users in canonical lock order. Reusing
    that row avoids a second account SELECT without caching or skipping revocation,
    provider-session, eligibility or deletion checks.
    """
    session = await db.get(AuthSession, actor.session_id)
    if (
        not user
        or user.id != actor.user_id
        or not session
        or session.user_id != actor.user_id
        or actor.auth_version != user.auth_version
    ):
        raise DomainError(401, "SESSION_EXPIRED", "Phiên đã kết thúc.")
    await verify_session(db, session, user)
    if eligible and user.age_band not in ("teen", "adult"):
        raise DomainError(
            403, "ELIGIBILITY_REQUIRED", "Tài khoản chưa đủ điều kiện sử dụng tính năng này."
        )
    if eligible and user.deletion_pending:
        raise DomainError(
            409,
            "DELETION_IN_PROGRESS",
            "Dữ liệu đang được xóa. Bạn có thể kiểm tra trạng thái trong quyền riêng tư.",
        )
    return user


@asynccontextmanager
async def transaction(request: Request, actor: Actor, *, eligible: bool = True, lock: bool = True):
    async with request.app.state.database.require()() as db, db.begin():
        user = await lock_actor(db, actor, eligible=eligible, lock=lock)
        deadline = await guest_deadline(db, user)
        if deadline is not None:
            # Lock waits and statements may never outlive the remaining trial.
            bound = str(max(1, int(deadline.remaining_seconds * 1000)))
            await db.execute(text("select set_config('statement_timeout', :ms, true)"), {"ms": bound})
            await db.execute(text("select set_config('lock_timeout', :ms, true)"), {"ms": bound})
        yield db, user
        if deadline is not None:
            # Reached only on a normal exit: a body that crossed T rolls back mutation and receipt.
            await final_guest_authorization(db, user)


async def assert_purpose(db: AsyncSession, user: User, purpose: str) -> dict[str, Consent]:
    values = {
        c.purpose: c
        for c in (await db.scalars(select(Consent).where(Consent.user_id == user.id))).all()
    }
    needed = [purpose] + (["AI"] if purpose in ("MEM", "VOICE") else [])
    if any(not values.get(p) or not values[p].enabled for p in needed):
        raise DomainError(403, "CONSENT_REQUIRED", "Bạn chưa bật quyền cần thiết.")
    if purpose == "MATCH" and user.age_band != "adult":
        raise DomainError(
            403, "ADULT_REQUIRED", "Tính năng kết nối chỉ dành cho tài khoản đủ điều kiện."
        )
    if purpose == "MATCH" and user.social_restricted_until and user.social_restricted_until > now():
        raise DomainError(
            403, "SOCIAL_RESTRICTED", "Tính năng kết nối của bạn đang tạm bị hạn chế."
        )
    return values


def idempotency_key(request: Request) -> str:
    key = request.headers.get("Idempotency-Key", "")
    if not key or len(key) > 128:
        raise DomainError(422, "IDEMPOTENCY_REQUIRED", "Yêu cầu cần mã xác nhận hợp lệ.")
    return key


async def previous_receipt(
    db: AsyncSession, user: User, operation: str, key: str, payload: Any
) -> dict | None:
    hashed = digest(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")))
    record = await db.scalar(
        select(Idempotency).where(
            Idempotency.user_id == user.id,
            Idempotency.operation == operation,
            Idempotency.key == key,
        )
    )
    if record and record.created_at + timedelta(hours=24) <= now():
        await db.delete(record)
        await db.flush()
        record = None
    if record:
        if record.digest != hashed:
            raise DomainError(
                409, "IDEMPOTENCY_CONFLICT", "Mã xác nhận đã được dùng với nội dung khác."
            )
        return record.receipt
    return None


def save_receipt(
    db: AsyncSession, user: User, operation: str, key: str, payload: Any, receipt: dict
) -> None:
    hashed = digest(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")))
    db.add(
        Idempotency(user_id=user.id, operation=operation, key=key, digest=hashed, receipt=receipt)
    )
