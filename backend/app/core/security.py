import hashlib
import hmac
import json
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from uuid import UUID

from fastapi import Request
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DomainError
from app.infrastructure.database.models import AuthSession, Consent, Idempotency, User, now


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


@dataclass(frozen=True)
class Actor:
    user_id: UUID
    session_id: UUID
    auth_version: int


async def verify_session(db: AsyncSession, session: AuthSession, user: User) -> None:
    if (
        session.revoked
        or session.expires_at <= now()
        or session.auth_version != user.auth_version
        or user.status != "active"
    ):
        raise DomainError(401, "SESSION_EXPIRED", "Phiên đã kết thúc. Vui lòng đăng nhập lại.")
    # Supabase logout/revocation removes auth.sessions. A JWT signature alone is insufficient.
    exists = await db.scalar(
        text("select moodprint.is_provider_session_active(:sid,:uid)"),
        {"sid": session.id, "uid": user.id},
    )
    if not exists:
        raise DomainError(401, "SESSION_EXPIRED", "Phiên đã kết thúc. Vui lòng đăng nhập lại.")


async def require_actor(request: Request) -> Actor:
    token = request.cookies.get("moodprint_session")
    if not token:
        raise DomainError(401, "AUTH_REQUIRED", "Vui lòng đăng nhập.")
    async with request.app.state.database.require()() as db:
        session = await db.scalar(
            select(AuthSession).where(AuthSession.token_hash == digest(token))
        )
        if session is None:
            raise DomainError(401, "SESSION_EXPIRED", "Phiên đã kết thúc. Vui lòng đăng nhập lại.")
        user = await db.get(User, session.user_id)
        if user is None:
            raise DomainError(401, "AUTH_REQUIRED", "Vui lòng đăng nhập.")
        await verify_session(db, session, user)
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            csrf = request.headers.get("X-CSRF-Token", "")
            if not csrf or not hmac.compare_digest(digest(csrf), session.csrf_hash):
                raise DomainError(
                    403, "CSRF_DENIED", "Phiên xác nhận đã thay đổi. Vui lòng tải lại."
                )
            origin = request.headers.get("Origin")
            if origin and origin.rstrip("/") != request.app.state.settings.frontend_origin.rstrip(
                "/"
            ):
                raise DomainError(403, "ORIGIN_DENIED", "Nguồn yêu cầu không hợp lệ.")
        return Actor(user.id, session.id, user.auth_version)


async def lock_actor(db: AsyncSession, actor: Actor, *, eligible: bool = True) -> User:
    user = await db.scalar(select(User).where(User.id == actor.user_id).with_for_update())
    session = await db.get(AuthSession, actor.session_id)
    if not user or not session or actor.auth_version != user.auth_version:
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
async def transaction(request: Request, actor: Actor, *, eligible: bool = True):
    async with request.app.state.database.require()() as db, db.begin():
        user = await lock_actor(db, actor, eligible=eligible)
        yield db, user


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
