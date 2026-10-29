"""Bounded active-store retention, independent of collection and administration flags."""

from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import User
from app.modules.feedback.models import AppFeedback, FeedbackSubmissionReceipt
from app.modules.guests.policy import database_time


async def purge_feedback(db: AsyncSession, *, batch_size: int = 500) -> int:
    """Delete at most one batch of feedback and one batch of old registered receipts.

    The caller commits. Feedback cascades to its receipts/review events; deleting a receipt never
    deletes feedback. Guest receipts are removed by guest purge, rather than normal 30-day aging.
    Return the number of feedback rows removed (receipt aging is not a feedback deletion).
    """
    if not 1 <= batch_size <= 500:
        raise ValueError("batch_size must be between 1 and 500")
    instant = await database_time(db)
    ids = (
        await db.scalars(
            select(AppFeedback.id)
            .where(AppFeedback.created_at <= instant - timedelta(days=180))
            .order_by(AppFeedback.created_at, AppFeedback.id)
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
    ).all()
    if ids:
        await db.execute(delete(AppFeedback).where(AppFeedback.id.in_(ids)))
    receipts = (
        await db.scalars(
            select(FeedbackSubmissionReceipt.id)
            .join(User, User.id == FeedbackSubmissionReceipt.user_id)
            .where(
                User.account_kind == "registered",
                FeedbackSubmissionReceipt.created_at <= instant - timedelta(days=30),
            )
            .order_by(FeedbackSubmissionReceipt.created_at, FeedbackSubmissionReceipt.id)
            .limit(batch_size)
            .with_for_update(of=FeedbackSubmissionReceipt, skip_locked=True)
        )
    ).all()
    if receipts:
        await db.execute(
            delete(FeedbackSubmissionReceipt).where(FeedbackSubmissionReceipt.id.in_(receipts))
        )
    return len(ids)
