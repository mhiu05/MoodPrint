"""Browser-owned provisioning intents: short-lived coordination, never an application identity."""

import hashlib
import secrets
from datetime import datetime

from fastapi import Request, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DomainError
from app.modules.guests import limits
from app.modules.guests.availability import experience_view
from app.modules.guests.models import GuestProvisioningAttempt
from app.modules.guests.policy import database_time

COOKIE = "moodprint_guest_intent"
COOKIE_PATH = "/api/v1/auth"
INTENT_SECONDS = 600
TERMINAL_STATES = ("rejected", "resolved", "incident_required", "orphan_pending")


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def invalid_intent() -> DomainError:
    return DomainError(
        422, "GUEST_INTENT_INVALID", "Phiên bắt đầu dùng thử đã hết hạn. Vui lòng thử lại."
    )


def require_public_write(request: Request) -> None:
    """Exact Origin, a custom header and JSON only: a cross-site form or simple request cannot pass."""
    settings = request.app.state.settings
    origin = request.headers.get("Origin")
    if not origin or origin.rstrip("/") != settings.frontend_origin.rstrip("/"):
        raise DomainError(403, "ORIGIN_DENIED", "Nguồn yêu cầu không hợp lệ.")
    if request.headers.get("X-Guest-Intent") != "1":
        raise DomainError(403, "GUEST_INTENT_HEADER_REQUIRED", "Yêu cầu không hợp lệ.")
    site = request.headers.get("Sec-Fetch-Site")
    if site and site not in ("same-origin", "none"):
        raise DomainError(403, "ORIGIN_DENIED", "Nguồn yêu cầu không hợp lệ.")
    if not request.headers.get("Content-Type", "").lower().startswith("application/json"):
        raise DomainError(415, "UNSUPPORTED_MEDIA_TYPE", "Yêu cầu không hợp lệ.")


async def create_guest_intent_row(db: AsyncSession) -> str:
    """Persist one unbound intent with a random server-side provider correlation; return its token."""
    token = secrets.token_urlsafe(32)
    db.add(
        GuestProvisioningAttempt(
            intent_hash=hash_token(token), provider_correlation=secrets.token_hex(32)
        )
    )
    await db.flush()
    return token


async def create_guest_intent(request: Request, response: Response) -> None:
    """Issue (or reuse) the 10-minute intent cookie. Creates no identity and calls no provider."""
    require_public_write(request)
    if not experience_view(request).guest_available:
        raise DomainError(503, "GUEST_DISABLED", "Dùng thử tạm thời chưa mở. Vui lòng quay lại sau.")
    settings = request.app.state.settings
    presented = request.cookies.get(COOKIE)
    async with request.app.state.database.require()() as db, db.begin():
        reusable = None
        if presented:
            reusable = await db.scalar(
                select(GuestProvisioningAttempt).where(
                    GuestProvisioningAttempt.intent_hash == hash_token(presented),
                    GuestProvisioningAttempt.state == "intent",
                    GuestProvisioningAttempt.idempotency_hash.is_(None),
                    GuestProvisioningAttempt.intent_expires_at > func.clock_timestamp(),
                )
            )
        token: str
        if reusable is not None and presented:
            token = presented
            remaining = int((reusable.intent_expires_at - await database_time(db)).total_seconds())
        else:
            await limits.reserve_guest_intent(db, request)
            token = await create_guest_intent_row(db)
            remaining = INTENT_SECONDS
    response.set_cookie(
        COOKIE,
        token,
        httponly=True,
        secure=settings.cookie_secure or settings.app_env == "production",
        samesite="strict",
        max_age=max(0, min(INTENT_SECONDS, remaining)),
        path=COOKIE_PATH,
    )


async def claim_guest_attempt(
    db: AsyncSession, *, intent_token: str, key: str, payload_digest: str
) -> GuestProvisioningAttempt:
    """Lock the attempt owned by this cookie and bind it to exactly one key and payload.

    An unknown, expired or foreign token is invalid (a key alone proves nothing); a finished
    attempt is terminal and needs an explicit new intent; a changed key or payload conflicts.
    """
    attempt = await db.scalar(
        select(GuestProvisioningAttempt)
        .where(GuestProvisioningAttempt.intent_hash == hash_token(intent_token))
        .with_for_update()
    )
    now: datetime = await database_time(db)
    if attempt is None or attempt.intent_expires_at <= now:
        raise invalid_intent()
    if attempt.state in TERMINAL_STATES:
        raise DomainError(
            409,
            "GUEST_INTENT_TERMINAL",
            "Lần bắt đầu này đã kết thúc. Hãy bắt đầu lượt dùng thử mới.",
        )
    key_hash = hash_token(key)
    if attempt.idempotency_hash is None:
        attempt.idempotency_hash, attempt.payload_digest = key_hash, payload_digest
    elif attempt.idempotency_hash != key_hash or attempt.payload_digest != payload_digest:
        raise DomainError(
            409, "IDEMPOTENCY_CONFLICT", "Yêu cầu này đã được gửi với nội dung khác. Vui lòng tải lại."
        )
    return attempt
