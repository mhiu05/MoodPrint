"""One bounded filter cohort for feedback pages and metrics; no submitter joins."""

import base64
import binascii
import json
import re
from datetime import UTC, datetime, time, timedelta
from typing import Any, Literal, cast
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import Date, and_, any_, func, literal, or_, select
from sqlalchemy import cast as sql_cast
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DomainError
from app.core.security import digest, previous_receipt, save_receipt
from app.infrastructure.database.models import User
from app.modules.feedback.models import AppFeedback, FeedbackReviewEvent
from app.modules.feedback.schemas import (
    CATEGORY_ORDER,
    AccountKindCounts,
    Category,
    DateBucket,
    FeedbackAdminView,
    FeedbackFilters,
    FeedbackPage,
    FeedbackStatusInput,
    FeedbackSummary,
    VersionBucket,
)
from app.modules.guests.policy import database_time
from app.modules.moderation.staff import Staff, assert_feedback_admin

BANGKOK = ZoneInfo("Asia/Bangkok")


def view(row: AppFeedback) -> FeedbackAdminView:
    return FeedbackAdminView.model_validate(row, from_attributes=True)


async def cohort(db: AsyncSession, filters: FeedbackFilters) -> tuple[list[Any], str]:
    end = filters.to_date or (await database_time(db)).astimezone(BANGKOK).date()
    try:
        start = filters.from_date or end - timedelta(days=29)
        next_day = end + timedelta(days=1)
    except OverflowError:
        raise DomainError(422, "VALIDATION_ERROR", "Khoảng ngày không hợp lệ.") from None
    if start > end or (end - start).days + 1 > 180:
        raise DomainError(422, "VALIDATION_ERROR", "Khoảng thời gian phải từ 1 đến 180 ngày.")
    lower = datetime.combine(start, time.min, BANGKOK).astimezone(UTC)
    upper = datetime.combine(next_day, time.min, BANGKOK).astimezone(UTC)
    conditions: list[Any] = [AppFeedback.created_at >= lower, AppFeedback.created_at < upper]
    for column, value in (
        (AppFeedback.app_version, filters.app_version),
        (AppFeedback.account_kind, filters.account_kind),
        (AppFeedback.rating, filters.rating),
        (AppFeedback.status, filters.status),
    ):
        if value is not None:
            conditions.append(column == value)
    if filters.status is None and not filters.include_spam:
        conditions.append(AppFeedback.status != "spam")
    if filters.category is not None:
        conditions.append(literal(filters.category) == any_(AppFeedback.categories))
    normalized = filters.model_dump(mode="json") | {"from_date": str(start), "to_date": str(end)}
    fingerprint = digest(json.dumps(normalized, sort_keys=True, separators=(",", ":")))
    return conditions, fingerprint


def encode_cursor(row: AppFeedback, fingerprint: str) -> str:
    data = {"createdAt": row.created_at.isoformat(), "id": str(row.id), "filterHash": fingerprint}
    return (
        base64.urlsafe_b64encode(json.dumps(data, separators=(",", ":")).encode())
        .decode()
        .rstrip("=")
    )


def decode_cursor(value: str, fingerprint: str) -> tuple[datetime, UUID]:
    try:
        if len(value) > 1024 or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
            raise ValueError
        raw = json.loads(
            base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
        )
        if not isinstance(raw, dict) or set(raw) != {"createdAt", "id", "filterHash"}:
            raise ValueError
        if raw["filterHash"] != fingerprint:
            raise ValueError
        instant, uid = datetime.fromisoformat(raw["createdAt"]), UUID(raw["id"])
        if instant.tzinfo is None:
            raise ValueError
        return instant, uid
    except (ValueError, TypeError, binascii.Error, OverflowError):
        raise DomainError(
            422, "INVALID_CURSOR", "Trang tiếp theo không hợp lệ. Hãy tải lại danh sách."
        ) from None


async def list_feedback(
    db: AsyncSession, filters: FeedbackFilters, cursor: str | None, limit: int
) -> FeedbackPage:
    if not 1 <= limit <= 50:
        raise DomainError(422, "VALIDATION_ERROR", "Mỗi trang tối đa 50 góp ý.")
    conditions, fingerprint = await cohort(db, filters)
    if cursor is not None:
        instant, uid = decode_cursor(cursor, fingerprint)
        conditions.append(
            or_(
                AppFeedback.created_at < instant,
                and_(AppFeedback.created_at == instant, AppFeedback.id < uid),
            )
        )
    rows = (
        await db.scalars(
            select(AppFeedback)
            .where(*conditions)
            .order_by(AppFeedback.created_at.desc(), AppFeedback.id.desc())
            .limit(limit + 1)
        )
    ).all()
    page = rows[:limit]
    return FeedbackPage(
        items=[view(row) for row in page],
        next_cursor=encode_cursor(page[-1], fingerprint) if len(rows) > limit else None,
    )


def mean(value) -> float | None:
    return float(value) if value is not None else None


async def summarize_feedback(db: AsyncSession, filters: FeedbackFilters) -> FeedbackSummary:
    conditions, _ = await cohort(db, filters)
    count, average = (
        await db.execute(select(func.count(), func.avg(AppFeedback.rating)).where(*conditions))
    ).one()
    ratings: dict[Literal["1", "2", "3", "4", "5"], int] = {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}
    for rating, amount in (
        await db.execute(
            select(AppFeedback.rating, func.count()).where(*conditions).group_by(AppFeedback.rating)
        )
    ).all():
        ratings[cast(Literal["1", "2", "3", "4", "5"], str(rating))] = amount
    categories: dict[Category, int] = {}
    values = (
        await db.execute(
            select(
                *(
                    func.count().filter(literal(category) == any_(AppFeedback.categories))
                    for category in CATEGORY_ORDER
                )
            )
            .select_from(AppFeedback)
            .where(*conditions)
        )
    ).one()
    categories = {
        cast(Category, category): amount
        for category, amount in zip(CATEGORY_ORDER, values, strict=True)
    }
    kinds = {
        kind: amount
        for kind, amount in (
            await db.execute(
                select(AppFeedback.account_kind, func.count())
                .where(*conditions)
                .group_by(AppFeedback.account_kind)
            )
        ).all()
    }
    day = sql_cast(func.timezone("Asia/Bangkok", AppFeedback.created_at), Date)
    dates = (
        await db.execute(
            select(day, func.count(), func.avg(AppFeedback.rating))
            .where(*conditions)
            .group_by(day)
            .order_by(day)
        )
    ).all()
    versions = (
        await db.execute(
            select(AppFeedback.app_version, func.count(), func.avg(AppFeedback.rating))
            .where(*conditions)
            .group_by(AppFeedback.app_version)
            .order_by(func.count().desc(), AppFeedback.app_version)
            .limit(51)
        )
    ).all()
    version_buckets = [
        VersionBucket(app_version=version, count=amount, mean_rating=mean(average))
        for version, amount, average in versions[:50]
    ]
    if len(versions) > 50:
        top = [version for version, _, _ in versions[:49]]
        other_count, other_mean = (
            await db.execute(
                select(func.count(), func.avg(AppFeedback.rating)).where(
                    *conditions, AppFeedback.app_version.not_in(top)
                )
            )
        ).one()
        version_buckets = version_buckets[:49] + [
            VersionBucket(app_version="(other)", count=other_count, mean_rating=mean(other_mean))
        ]
    return FeedbackSummary(
        count=count,
        mean_rating=mean(average),
        rating_counts=ratings,
        category_counts=categories,
        account_kind_counts=AccountKindCounts(
            guest=kinds.get("guest", 0), registered=kinds.get("registered", 0)
        ),
        by_date=[
            DateBucket(date=str(date), count=amount, mean_rating=mean(value))
            for date, amount, value in dates
        ],
        by_version=version_buckets,
    )


async def review_feedback(
    db: AsyncSession, staff: Staff, id: UUID, body: FeedbackStatusInput, key: str
) -> FeedbackAdminView:
    await assert_feedback_admin(db, staff.actor, lock=True)
    user = await db.get(User, staff.user_id)
    assert user is not None  # asserted and owner-locked by assert_feedback_admin
    operation, payload = f"feedback:review:{id}", body.model_dump(mode="json")
    previous = await previous_receipt(db, user, operation, key, payload)
    row = await db.scalar(
        select(AppFeedback)
        .where(AppFeedback.id == id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise DomainError(404, "NOT_FOUND", "Không tìm thấy góp ý.")
    # Resource/receipt lookup may wait: revalidate the live session/role/reauth before deciding.
    await assert_feedback_admin(db, staff.actor, lock=True)
    if previous is not None:
        return view(row)
    if row.version != body.expected_version:
        raise DomainError(
            409, "STALE_VERSION", "Góp ý đã thay đổi. Hãy tải lại trước khi cập nhật."
        )
    if row.status != body.status:
        old_status = row.status
        row.status, row.version, row.reviewed_at = (
            body.status,
            row.version + 1,
            await database_time(db),
        )
        db.add(
            FeedbackReviewEvent(
                feedback_id=row.id,
                staff_id=staff.user_id,
                action="status",
                from_status=old_status,
                to_status=row.status,
                resulting_version=row.version,
            )
        )
    save_receipt(db, user, operation, key, payload, {"id": str(row.id), "version": row.version})
    await db.flush()
    return view(row)
