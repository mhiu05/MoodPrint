from datetime import date, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select

from app.contracts import ActionReceipt, MoodDTO, MoodInput, MoodSummaryDTO, VersionInput
from app.core.errors import DomainError
from app.core.security import (
    Actor,
    idempotency_key,
    previous_receipt,
    require_actor,
    save_receipt,
    transaction,
)
from app.infrastructure.database.models import Mood

router = APIRouter()


@router.get("/moods", response_model=list[MoodDTO])
async def list_moods(request: Request, actor: Actor = Depends(require_actor)):
    async with transaction(request, actor) as (db, user):
        today = datetime.now(ZoneInfo(user.timezone)).date()
        rows = (
            await db.scalars(
                select(Mood)
                .where(
                    Mood.user_id == user.id,
                    Mood.local_date >= today - timedelta(days=89),
                    Mood.local_date <= today,
                )
                .order_by(Mood.local_date)
            )
        ).all()
        result = [MoodDTO.model_validate(r) for r in rows]
    return result


@router.get("/moods/summary", response_model=MoodSummaryDTO)
async def summary(
    request: Request,
    days: int = Query(default=7, ge=1, le=90),
    start: date | None = Query(default=None, alias="from"),
    end: date | None = Query(default=None, alias="to"),
    actor: Actor = Depends(require_actor),
):
    async with transaction(request, actor) as (db, user):
        today = datetime.now(ZoneInfo(user.timezone)).date()
        if (start is None) != (end is None):
            raise DomainError(422, "INVALID_RANGE", "Cần chọn cả ngày bắt đầu và ngày kết thúc.")
        if start is None or end is None:
            start, end = today - timedelta(days=days - 1), today
        if start > end or end > today or start < today - timedelta(days=89):
            raise DomainError(
                422, "INVALID_RANGE", "Chỉ có thể xem tâm trạng trong 90 ngày gần đây."
            )
        rows = (
            await db.scalars(
                select(Mood).where(
                    Mood.user_id == user.id, Mood.local_date >= start, Mood.local_date <= end
                )
            )
        ).all()
        by_day = {row.local_date: row.value for row in rows}
        values = [row.value for row in rows]
        span = (end - start).days + 1
        result = MoodSummaryDTO.model_validate(
            {
                "from": start,
                "to": end,
                "count": len(values),
                "mean": round(sum(values) / len(values), 2) if values else None,
                "min": min(values, default=None),
                "max": max(values, default=None),
                "insightAvailable": len(values) >= 3,
                "buckets": [
                    {
                        "localDate": start + timedelta(days=i),
                        "value": by_day.get(start + timedelta(days=i)),
                    }
                    for i in range(span)
                ],
            }
        )
    return result


@router.put("/moods/{local_date}", response_model=MoodDTO)
async def save_mood(
    local_date: date, body: MoodInput, request: Request, actor: Actor = Depends(require_actor)
):
    key, payload = idempotency_key(request), body.model_dump(mode="json")
    operation = f"mood:{local_date}"
    async with transaction(request, actor) as (db, user):
        # The account timezone, not the request, owns day boundaries so that list,
        # summary, export, retention and the AI scope agree on what "today" is.
        today = datetime.now(ZoneInfo(user.timezone)).date()
        if local_date > today:
            raise DomainError(422, "FUTURE_DATE", "Không thể ghi tâm trạng cho ngày chưa đến.")
        if local_date < today - timedelta(days=89):
            raise DomainError(
                422, "DATE_EXPIRED", "Chỉ có thể ghi tâm trạng trong 90 ngày gần đây."
            )
        old = await previous_receipt(db, user, operation, key, payload)
        mood = await db.scalar(
            select(Mood).where(Mood.user_id == user.id, Mood.local_date == local_date)
        )
        if not old:
            if (mood.version if mood else 0) != body.expected_version:
                raise DomainError(409, "STALE_VERSION", "Tâm trạng đã thay đổi.")
            if mood:
                mood.version += 1
                mood.value, mood.note, mood.timezone = body.value, body.note, user.timezone
            else:
                mood = Mood(
                    user_id=user.id,
                    local_date=local_date,
                    value=body.value,
                    note=body.note,
                    timezone=user.timezone,
                )
                db.add(mood)
            user.data_version += 1
            await db.flush()
            save_receipt(
                db,
                user,
                operation,
                key,
                payload,
                {"resourceId": str(mood.id), "version": mood.version},
            )
        if mood is None:
            raise DomainError(409, "RESOURCE_CHANGED", "Tâm trạng đã được xóa.")
        result = MoodDTO.model_validate(mood)
    request.app.state.ai.invalidate(str(actor.user_id))
    return result


@router.delete("/moods/{local_date}", response_model=ActionReceipt)
async def delete_mood(
    local_date: date, body: VersionInput, request: Request, actor: Actor = Depends(require_actor)
):
    key, payload = idempotency_key(request), body.model_dump(mode="json")
    operation = f"mood:delete:{local_date}"
    async with transaction(request, actor) as (db, user):
        old = await previous_receipt(db, user, operation, key, payload)
        if old:
            return ActionReceipt.model_validate(old)
        mood = await db.scalar(
            select(Mood).where(Mood.user_id == user.id, Mood.local_date == local_date)
        )
        if not mood:
            raise DomainError(404, "NOT_FOUND", "Không tìm thấy tâm trạng.")
        if mood.version != body.expected_version:
            raise DomainError(409, "STALE_VERSION", "Tâm trạng đã thay đổi.")
        receipt = ActionReceipt(
            action_id=uuid4(), resource_id=str(mood.id), resource_version=mood.version + 1
        )
        await db.delete(mood)
        user.data_version += 1
        save_receipt(
            db, user, operation, key, payload, receipt.model_dump(mode="json", by_alias=True)
        )
    request.app.state.ai.invalidate(str(actor.user_id))
    return receipt
