"""Owner-authenticated control endpoints for direct private media uploads."""

from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request
from pydantic import Field, field_validator, model_validator
from sqlalchemy import func, select

from app.contracts import DTO, ActionReceipt, EmptyInput
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
from app.modules.journal.models import JournalMedia
from app.modules.journal.schemas import JournalMediaDTO, MediaType
from app.modules.journal.service import get_owned_entry, queue_media_deletion
from app.modules.journal.storage import MEDIA_LIMITS, MIME_EXTENSIONS, READ_TTL, unavailable

router = APIRouter()


class MediaInput(DTO):
    type: MediaType
    mime_type: str = Field(max_length=127)
    size_bytes: int = Field(gt=0, le=50 * 1024**2, strict=True)
    duration_seconds: float | None = Field(None, ge=0, le=3600, allow_inf_nan=False)

    @field_validator("mime_type")
    @classmethod
    def normalize_mime(cls, value: str):
        return value.split(";", 1)[0].strip().lower()

    @model_validator(mode="after")
    def validate_type(self):
        allowed = MIME_EXTENSIONS.get(self.mime_type)
        if not allowed or allowed[0] != self.type or self.size_bytes > MEDIA_LIMITS[self.type]:
            raise ValueError("Loại tệp hoặc dung lượng chưa phù hợp.")
        return self


class MediaReservation(DTO):
    media: JournalMediaDTO
    upload_url: str
    token: str
    resumable_url: str
    object_path: str
    bucket: Literal["journal-media"]


class MediaAccess(DTO):
    url: str
    expires_in: int = READ_TTL


def storage_for(request):
    storage = getattr(request.app.state, "journal_storage", None)
    if storage is None:
        raise unavailable()
    return storage


async def owned_media(db, user, entry_id, media_id):
    await get_owned_entry(db, user, entry_id)
    row = await db.scalar(
        select(JournalMedia).where(
            JournalMedia.id == media_id,
            JournalMedia.entry_id == entry_id,
            JournalMedia.user_id == user.id,
        )
    )
    if row is None:
        raise DomainError(404, "NOT_FOUND", "Không tìm thấy tệp đính kèm.")
    return row


@router.post("/journal/entries/{entry_id}/media", response_model=MediaReservation, status_code=201)
async def reserve_media(
    entry_id: UUID, body: MediaInput, request: Request, actor: Actor = Depends(require_actor)
):
    key, payload = idempotency_key(request), body.model_dump(mode="json")
    operation = f"journal:media:{entry_id}"
    async with transaction(request, actor) as (db, user):
        entry = await get_owned_entry(db, user, entry_id)
        storage = storage_for(request)
        old = await previous_receipt(db, user, operation, key, payload)
        if old:
            item = await owned_media(db, user, entry_id, UUID(old["resourceId"]))
        else:
            count = await db.scalar(
                select(func.count())
                .select_from(JournalMedia)
                .where(JournalMedia.entry_id == entry_id)
            )
            if count >= 10:
                raise DomainError(
                    422, "MEDIA_LIMIT", "Mỗi khoảnh khắc có thể đính kèm tối đa 10 tệp."
                )
            media_id = uuid4()
            path = f"users/{user.id}/{entry_id}/{body.type}/{media_id}.{MIME_EXTENSIONS[body.mime_type][1]}"
            item = JournalMedia(
                id=media_id,
                entry_id=entry_id,
                user_id=user.id,
                object_path=path,
                type=body.type,
                mime_type=body.mime_type,
                size_bytes=body.size_bytes,
                duration_seconds=body.duration_seconds,
            )
            db.add(item)
            entry.updated_at = now()
            user.data_version += 1
            await db.flush()
            save_receipt(db, user, operation, key, payload, {"resourceId": str(media_id)})
        media_id, path = item.id, item.object_path
    request.app.state.ai.invalidate(str(actor.user_id))
    capability = await storage.sign_upload(path)
    async with transaction(request, actor) as (db, user):
        item = await owned_media(db, user, entry_id, media_id)
        dto = JournalMediaDTO.model_validate(item)
    return MediaReservation(media=dto, **capability)


@router.post(
    "/journal/entries/{entry_id}/media/{media_id}/complete", response_model=JournalMediaDTO
)
async def complete_media(
    entry_id: UUID,
    media_id: UUID,
    body: EmptyInput,
    request: Request,
    actor: Actor = Depends(require_actor),
):
    async with transaction(request, actor) as (db, user):
        item = await owned_media(db, user, entry_id, media_id)
        if item.status == "ready":
            return JournalMediaDTO.model_validate(item)
        path = item.object_path
        storage = storage_for(request)
    info = await storage.info(path)
    mismatch = False
    async with transaction(request, actor) as (db, user):
        item = await owned_media(db, user, entry_id, media_id)
        if info is None:
            raise DomainError(
                409, "UPLOAD_INCOMPLETE", "Tệp chưa tải lên xong. Bạn hãy thử lại.", retryable=True
            )
        if info.get("size") != item.size_bytes or info.get("contentType") != item.mime_type:
            await queue_media_deletion(db, item)
            await db.delete(item)
            user.data_version += 1
            mismatch = True
        else:
            if item.status != "ready":
                item.status = "ready"
                user.data_version += 1
            dto = JournalMediaDTO.model_validate(item)
    request.app.state.ai.invalidate(str(actor.user_id))
    if mismatch:
        raise DomainError(422, "MEDIA_MISMATCH", "Tệp tải lên không khớp. Bạn hãy chọn lại tệp.")
    return dto


@router.get("/journal/entries/{entry_id}/media/{media_id}/access", response_model=MediaAccess)
async def access_media(
    entry_id: UUID, media_id: UUID, request: Request, actor: Actor = Depends(require_actor)
):
    async with transaction(request, actor) as (db, user):
        item = await owned_media(db, user, entry_id, media_id)
        if item.status != "ready":
            raise DomainError(409, "UPLOAD_INCOMPLETE", "Tệp chưa tải lên xong.")
        path = item.object_path
        storage = storage_for(request)
    url = await storage.sign_read(path)
    async with transaction(request, actor) as (db, user):
        await owned_media(db, user, entry_id, media_id)
    return MediaAccess(url=url)


@router.delete("/journal/entries/{entry_id}/media/{media_id}", response_model=ActionReceipt)
async def delete_media(
    entry_id: UUID,
    media_id: UUID,
    body: EmptyInput,
    request: Request,
    actor: Actor = Depends(require_actor),
):
    key, payload = idempotency_key(request), body.model_dump(mode="json")
    operation = f"journal:media:delete:{media_id}"
    async with transaction(request, actor) as (db, user):
        old = await previous_receipt(db, user, operation, key, payload)
        if old:
            return ActionReceipt.model_validate(old)
        item = await owned_media(db, user, entry_id, media_id)
        await queue_media_deletion(db, item)
        await db.delete(item)
        user.data_version += 1
        receipt = ActionReceipt(action_id=uuid4(), resource_id=str(media_id), resource_version=1)
        save_receipt(
            db, user, operation, key, payload, receipt.model_dump(mode="json", by_alias=True)
        )
    request.app.state.ai.invalidate(str(actor.user_id))
    return receipt
