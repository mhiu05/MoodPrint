from datetime import date, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select

from app.contracts import ActionReceipt, MoodDTO, MoodInput, VersionInput
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


@router.get("/moods/summary")
async def summary(
    request: Request,
    days: int = Query(default=7, ge=1, le=90),
    actor: Actor = Depends(require_actor),
):
    async with transaction(request, actor) as (db, user):
        today = datetime.now(ZoneInfo(user.timezone)).date()
        start = today - timedelta(days=days - 1)
        rows = (
            await db.scalars(
                select(Mood).where(
                    Mood.user_id == user.id, Mood.local_date >= start, Mood.local_date <= today
                )
            )
        ).all()
        by_day = {row.local_date: row.value for row in rows}
        result = {
            "from": str(start),
            "to": str(today),
            "count": len(rows),
            "mean": sum(r.value for r in rows) / len(rows) if rows else None,
            "insightAvailable": len(rows) >= 3,
            "buckets": [
                {
                    "localDate": str(start + timedelta(days=i)),
                    "value": by_day.get(start + timedelta(days=i)),
                }
                for i in range(days)
            ],
        }
    return result


@router.put("/moods/{local_date}", response_model=MoodDTO)
async def save_mood(
    local_date: date, body: MoodInput, request: Request, actor: Actor = Depends(require_actor)
):
    today = datetime.now(ZoneInfo(body.timezone)).date()
    if local_date > today:
        raise DomainError(422, "FUTURE_DATE", "Không thể ghi tâm trạng cho ngày chưa đến.")
    if local_date < today - timedelta(days=89):
        raise DomainError(422, "DATE_EXPIRED", "Chỉ có thể ghi tâm trạng trong 90 ngày gần đây.")
    key, payload = idempotency_key(request), body.model_dump(mode="json")
    operation = f"mood:{local_date}"
    async with transaction(request, actor) as (db, user):
        old = await previous_receipt(db, user, operation, key, payload)
        mood = await db.scalar(
            select(Mood).where(Mood.user_id == user.id, Mood.local_date == local_date)
        )
        if not old:
            if (mood.version if mood else 0) != body.expected_version:
                raise DomainError(409, "STALE_VERSION", "Tâm trạng đã thay đổi.")
            if mood:
                mood.version += 1
                mood.value, mood.note, mood.timezone = body.value, body.note.strip(), body.timezone
            else:
                mood = Mood(
                    user_id=user.id,
                    local_date=local_date,
                    value=body.value,
                    note=body.note.strip(),
                    timezone=body.timezone,
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
