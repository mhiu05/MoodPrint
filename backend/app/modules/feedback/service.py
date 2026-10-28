"""Atomic feedback submission: one receipt and one row per owner decision, bounded and replay-safe.

Everything runs inside the caller's owner-locked transaction (``core.security.transaction``), so a
guest whose deadline passes before the commit rolls back the feedback, the receipt *and* the
accepted-submission counter together. The stored feedback row carries no identity; only the
receipt (owner + idempotency key + payload digest) ties it to the submitter, for as long as the
receipt lives.
"""

import json
from datetime import timedelta
from uuid import uuid4

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DomainError
from app.core.security import digest
from app.infrastructure.database.models import User
from app.modules.feedback.models import AppFeedback, FeedbackSubmissionReceipt
from app.modules.feedback.schemas import FeedbackInput, FeedbackReceipt, FeedbackSubmissionState
from app.modules.guests.limits import (
    _digest,
    bangkok_day,
    canonical_client_key,
    fixed_window,
    reserve_bucket,
)
from app.modules.guests.policy import database_time

ACCEPTED_PER_NETWORK_HOUR = 20
ATTEMPTS_PER_IDENTITY_MINUTE = 3
REGISTERED_RECEIPT_DAYS = 30


def _limited(code: str, message: str, wait: timedelta) -> DomainError:
    return DomainError(
        429, code, message, True, retry_after=max(1, int(wait.total_seconds()) + 1)
    )


async def reserve_attempt(db: AsyncSession, request: Request, user_id) -> None:
    """Count one attempt for this identity in its own committed transaction.

    A refused or conflicting request still consumes an attempt, so this runs before (and outside)
    the submission transaction, which would roll the count back with its failure. The key is a
    rotating HMAC of (scope, UTC minute, identity): no raw identifier, expired within the minute.
    """
    now = await database_time(db)
    window = fixed_window(now, 60)
    if not await reserve_bucket(
        db,
        scope="feedback_attempt",
        key_hash=_digest(request, window[0], "feedback_attempt", f"identity:{user_id}"),
        window=window,
        limit=ATTEMPTS_PER_IDENTITY_MINUTE,
    ):
        raise _limited(
            "FEEDBACK_RATE_LIMITED",
            "Bạn gửi quá nhanh. Vui lòng thử lại sau ít phút.",
            window[1] - now,
        )


def canonical_digest(body: FeedbackInput) -> str:
    payload = body.model_dump(mode="json")
    return digest(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")))


async def submit_feedback(
    db: AsyncSession,
    user: User,
    body: FeedbackInput,
    key: str,
    *,
    request: Request,
    app_version: str,
) -> tuple[FeedbackReceipt, bool]:
    """Return ``(receipt, created)``; a replay of the same key and payload returns ``created=False``.

    Deviation from the plan's signature: the network bucket key is an HMAC over the database-clock
    window, so the request (not a precomputed key) is passed in.
    """
    payload_digest = canonical_digest(body)
    existing = await db.scalar(
        select(FeedbackSubmissionReceipt).where(
            FeedbackSubmissionReceipt.user_id == user.id,
            FeedbackSubmissionReceipt.idempotency_key == key,
        )
    )
    if existing is not None:
        if existing.payload_digest != payload_digest:
            raise DomainError(
                409, "IDEMPOTENCY_CONFLICT", "Mã xác nhận đã được dùng với nội dung khác."
            )
        feedback = await db.get(AppFeedback, existing.feedback_id)
        if feedback is not None:
            return FeedbackReceipt(feedback_id=feedback.id, created_at=feedback.created_at), False

    now = await database_time(db)
    if user.account_kind == "guest":
        # One successful submission per guest lifecycle: the receipt lives exactly as long as the trial.
        if await db.scalar(
            select(FeedbackSubmissionReceipt.id)
            .where(FeedbackSubmissionReceipt.user_id == user.id)
            .limit(1)
        ):
            raise DomainError(
                409, "FEEDBACK_ALREADY_SUBMITTED", "Bạn đã gửi góp ý trong lượt dùng thử này."
            )
    else:
        day_start, day_end = bangkok_day(now)
        if await db.scalar(
            select(FeedbackSubmissionReceipt.id)
            .where(
                FeedbackSubmissionReceipt.user_id == user.id,
                FeedbackSubmissionReceipt.created_at >= day_start,
            )
            .limit(1)
        ):
            raise _limited(
                "FEEDBACK_DAILY_LIMIT",
                "Bạn đã gửi góp ý hôm nay. Cảm ơn bạn, hãy quay lại vào ngày mai.",
                day_end - now,
            )

    window = fixed_window(now, 3600)
    if not await reserve_bucket(
        db,
        scope="feedback",
        key_hash=canonical_client_key(request, window[0], "feedback"),
        window=window,
        limit=ACCEPTED_PER_NETWORK_HOUR,
    ):
        raise _limited(
            "FEEDBACK_RATE_LIMITED",
            "Có quá nhiều góp ý từ mạng này. Vui lòng thử lại sau.",
            window[1] - now,
        )

    feedback = AppFeedback(
        id=uuid4(),
        rating=body.rating,
        categories=list(body.categories),
        comment=body.comment,
        app_version=app_version[:64] or "unknown",
        context=body.context,
        account_kind=user.account_kind,
        disclosure_version=body.disclosure_version,
    )
    db.add(feedback)
    await db.flush()
    db.add(
        FeedbackSubmissionReceipt(
            user_id=user.id,
            idempotency_key=key,
            payload_digest=payload_digest,
            feedback_id=feedback.id,
        )
    )
    await db.flush()
    await db.refresh(feedback, ["created_at"])
    return FeedbackReceipt(feedback_id=feedback.id, created_at=feedback.created_at), True


async def submission_state(db: AsyncSession, user: User) -> FeedbackSubmissionState:
    """Own receipt existence only: a guest's lifecycle, a registered user's last 30 days."""
    query = select(func.max(FeedbackSubmissionReceipt.created_at)).where(
        FeedbackSubmissionReceipt.user_id == user.id
    )
    if user.account_kind != "guest":
        cutoff = await database_time(db) - timedelta(days=REGISTERED_RECEIPT_DAYS)
        query = query.where(FeedbackSubmissionReceipt.created_at > cutoff)
    last = await db.scalar(query)
    return FeedbackSubmissionState(submitted=last is not None, last_submitted_at=last)
