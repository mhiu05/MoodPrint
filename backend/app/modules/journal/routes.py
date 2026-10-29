from datetime import date
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select

from app.contracts import ActionReceipt, VersionInput
from app.core.errors import DomainError
from app.core.security import (
    Actor,
    idempotency_key,
    previous_receipt,
    require_actor,
    save_receipt,
    transaction,
)
from app.infrastructure.database.models import now
from app.modules.journal.models import JournalEntry, JournalMedia
from app.modules.journal.schemas import (
    JournalEntryDTO,
    JournalEntryEdit,
    JournalEntryInput,
    JournalEntryPage,
)
from app.modules.journal.service import (
    active_dates,
    delete_entries,
    entries_dto,
    entry_dto,
    get_owned_entry,
    validate_date,
)

router = APIRouter()


@router.get("/journal/entries", response_model=JournalEntryPage)
async def list_entries(
    request: Request,
    start: date | None = Query(
        None,
        alias="from",
        description="Inclusive start within the current account-local 90-day window; defaults to today minus 89 days.",
    ),
    end: date | None = Query(
        None,
        alias="to",
        description="Inclusive end within the current account-local 90-day window; defaults to today.",
    ),
    q: str = Query("", max_length=200),
    mood: int | None = Query(None, ge=1, le=5),
    media: Literal["any", "image", "audio", "video"] | None = None,
    status: Literal["draft", "saved", "all"] = "saved",
    offset: int = Query(0, ge=0, le=10000),
    limit: int = Query(20, ge=1, le=50),
    actor: Actor = Depends(require_actor),
):
    """List active entries; reversed, expired or future date ranges return INVALID_RANGE.

    Range bounds follow the current account timezone. An entry retains the timezone captured at
    creation, including after the account timezone changes or the entry is edited.
    """
    async with transaction(request, actor) as (db, user):
        earliest, today = active_dates(user)
        start, end = start or earliest, end or today
        if start < earliest or end > today or start > end:
            raise DomainError(422, "INVALID_RANGE", "Chọn khoảng ngày trong 90 ngày gần đây.")
        conditions = [
            JournalEntry.user_id == user.id,
            JournalEntry.local_date >= start,
            JournalEntry.local_date <= end,
        ]
        if status != "all":
            conditions.append(JournalEntry.status == status)
        if q.strip():
            conditions.append(JournalEntry.text.icontains(q.strip(), autoescape=True))
        if mood is not None:
            conditions.append(JournalEntry.mood == mood)
        if media:
            media_query = select(JournalMedia.id).where(
                JournalMedia.entry_id == JournalEntry.id,
                JournalMedia.user_id == user.id,
                JournalMedia.status == "ready",
            )
            if media != "any":
                media_query = media_query.where(JournalMedia.type == media)
            conditions.append(media_query.exists())
        total = await db.scalar(select(func.count()).select_from(JournalEntry).where(*conditions))
        rows = (
            await db.scalars(
                select(JournalEntry)
                .where(*conditions)
                .order_by(
                    JournalEntry.local_date.desc(),
                    JournalEntry.created_at.desc(),
                    JournalEntry.id.desc(),
                )
                .offset(offset)
                .limit(limit)
            )
        ).all()
        return JournalEntryPage(
            items=await entries_dto(db, list(rows)), total=total or 0, offset=offset, limit=limit
        )


@router.post("/journal/entries", response_model=JournalEntryDTO, status_code=201)
async def create_entry(
    body: JournalEntryInput, request: Request, actor: Actor = Depends(require_actor)
):
    key, payload = idempotency_key(request), body.model_dump(mode="json")
    async with transaction(request, actor) as (db, user):
        validate_date(user, body.local_date)
        old = await previous_receipt(db, user, "journal:create", key, payload)
        if old:
            row = await get_owned_entry(db, user, UUID(old["resourceId"]))
        else:
            row = JournalEntry(user_id=user.id, timezone=user.timezone, **body.model_dump())
            db.add(row)
            user.data_version += 1
            await db.flush()
            save_receipt(
                db,
                user,
                "journal:create",
                key,
                payload,
                {"resourceId": str(row.id), "version": row.version},
            )
        result = await entry_dto(db, row)
    request.app.state.ai.invalidate(str(actor.user_id))
    return result


@router.get("/journal/entries/{entry_id}", response_model=JournalEntryDTO)
async def get_entry(entry_id: UUID, request: Request, actor: Actor = Depends(require_actor)):
    async with transaction(request, actor) as (db, user):
        return await entry_dto(db, await get_owned_entry(db, user, entry_id))


@router.put("/journal/entries/{entry_id}", response_model=JournalEntryDTO)
async def update_entry(
    entry_id: UUID, body: JournalEntryEdit, request: Request, actor: Actor = Depends(require_actor)
):
    key, payload = idempotency_key(request), body.model_dump(mode="json")
    operation = f"journal:update:{entry_id}"
    async with transaction(request, actor) as (db, user):
        row = await get_owned_entry(db, user, entry_id)
        validate_date(user, body.local_date)
        old = await previous_receipt(db, user, operation, key, payload)
        if not old:
            if row.version != body.expected_version:
                raise DomainError(
                    409, "STALE_VERSION", "Khoảnh khắc đã thay đổi. Hãy tải lại trước khi lưu."
                )
            for name, value in body.model_dump(exclude={"expected_version"}).items():
                setattr(row, name, value)
            row.updated_at = now()
            row.version += 1
            user.data_version += 1
            await db.flush()
            save_receipt(
                db,
                user,
                operation,
                key,
                payload,
                {"resourceId": str(row.id), "version": row.version},
            )
        result = await entry_dto(db, row)
    request.app.state.ai.invalidate(str(actor.user_id))
    return result


@router.delete("/journal/entries/{entry_id}", response_model=ActionReceipt)
async def delete_entry(
    entry_id: UUID, body: VersionInput, request: Request, actor: Actor = Depends(require_actor)
):
    key, payload = idempotency_key(request), body.model_dump(mode="json")
    operation = f"journal:delete:{entry_id}"
    async with transaction(request, actor) as (db, user):
        old = await previous_receipt(db, user, operation, key, payload)
        if old:
            return ActionReceipt.model_validate(old)
        row = await get_owned_entry(db, user, entry_id)
        if row.version != body.expected_version:
            raise DomainError(
                409, "STALE_VERSION", "Khoảnh khắc đã thay đổi. Hãy tải lại trước khi xóa."
            )
        receipt = ActionReceipt(
            action_id=uuid4(), resource_id=str(row.id), resource_version=row.version + 1
        )
        await delete_entries(db, [row])
        user.data_version += 1
        save_receipt(
            db, user, operation, key, payload, receipt.model_dump(mode="json", by_alias=True)
        )
    request.app.state.ai.invalidate(str(actor.user_id))
    return receipt
