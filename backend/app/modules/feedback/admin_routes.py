"""Feedback review is separate from moderation and never joins submitter/private activity."""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import ValidationError
from sqlalchemy import text

from app.core.errors import DomainError
from app.core.security import idempotency_key
from app.modules.feedback.queries import list_feedback, review_feedback, summarize_feedback
from app.modules.feedback.schemas import (
    AccountKind,
    Category,
    FeedbackAdminView,
    FeedbackFilters,
    FeedbackPage,
    FeedbackStatusInput,
    FeedbackSummary,
    Status,
)
from app.modules.moderation.staff import Staff, assert_feedback_admin, require_staff

router = APIRouter(prefix="/admin/feedback")
feedback_admin = require_staff("admin", feature="feedback")


def feedback_filters(
    from_date: date | None = Query(None, alias="fromDate"),
    to_date: date | None = Query(None, alias="toDate"),
    app_version: str | None = Query(None, alias="appVersion", min_length=1, max_length=64),
    account_kind: AccountKind | None = Query(None, alias="accountKind"),
    rating: int | None = Query(None, ge=1, le=5),
    status: Status | None = None,
    category: Category | None = None,
    include_spam: bool = Query(False, alias="includeSpam"),
) -> FeedbackFilters:
    try:
        return FeedbackFilters(
            from_date=from_date,
            to_date=to_date,
            app_version=app_version,
            account_kind=account_kind,
            rating=rating,
            status=status,
            category=category,
            include_spam=include_spam,
        )
    except ValidationError:
        raise DomainError(422, "VALIDATION_ERROR", "Bộ lọc chưa hợp lệ.") from None


@router.get("", response_model=FeedbackPage)
async def feedback_list(
    request: Request,
    staff: Staff = Depends(feedback_admin),
    filters: FeedbackFilters = Depends(feedback_filters),
    cursor: str | None = Query(None, max_length=1024),
    limit: int = Query(25, ge=1, le=50),
):
    async with request.app.state.database.require()() as db:
        await assert_feedback_admin(db, staff.actor)
        return await list_feedback(db, filters, cursor, limit)


@router.get("/summary", response_model=FeedbackSummary)
async def feedback_summary(
    request: Request,
    staff: Staff = Depends(feedback_admin),
    filters: FeedbackFilters = Depends(feedback_filters),
):
    async with request.app.state.database.require()() as db:
        # All aggregates in this response observe one cohort even while another admin reviews.
        await db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
        await assert_feedback_admin(db, staff.actor)
        return await summarize_feedback(db, filters)


@router.patch("/{id}", response_model=FeedbackAdminView)
async def feedback_review(
    id: UUID,
    body: FeedbackStatusInput,
    request: Request,
    staff: Staff = Depends(feedback_admin),
):
    key = idempotency_key(request)
    async with request.app.state.database.require()() as db, db.begin():
        return await review_feedback(db, staff, id, body, key)
