from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select, update

from app.contracts import (
    ActionReceipt,
    PrivateItemDTO,
    PrivateItemEdit,
    PrivateItemInput,
    VersionInput,
)
from app.core.errors import DomainError
from app.core.security import (
    Actor,
    idempotency_key,
    previous_receipt,
    require_actor,
    save_receipt,
    transaction,
)
from app.infrastructure.database.models import Memory, PrivateItem
from app.modules.profiles.taxonomy import TAXONOMY, TaxonomyDTO
from app.modules.social.service import invalidate_user_social

router = APIRouter()


@router.get("/taxonomy", response_model=TaxonomyDTO)
async def taxonomy():
    return TAXONOMY


@router.get("/profiles/private-items", response_model=list[PrivateItemDTO])
async def list_items(request: Request, actor: Actor = Depends(require_actor)):
    async with transaction(request, actor) as (db, user):
        rows = (
            await db.scalars(
                select(PrivateItem)
                .where(PrivateItem.user_id == user.id, PrivateItem.status != "deleted")
                .order_by(PrivateItem.id)
            )
        ).all()
        result = [PrivateItemDTO.model_validate(r) for r in rows]
    return result


@router.post("/profiles/private-items", response_model=PrivateItemDTO, status_code=201)
async def create_item(
    body: PrivateItemInput, request: Request, actor: Actor = Depends(require_actor)
):
    key, payload = idempotency_key(request), body.model_dump(mode="json")
    async with transaction(request, actor) as (db, user):
        old = await previous_receipt(db, user, "private:create", key, payload)
        if old:
            item = await db.get(PrivateItem, UUID(old["resourceId"]))
            if not item or item.status == "deleted":
                raise DomainError(409, "RESOURCE_CHANGED", "Nội dung đã thay đổi.")
        else:
            item = PrivateItem(user_id=user.id, text=body.text)
            db.add(item)
            await db.flush()
            save_receipt(db, user, "private:create", key, payload, {"resourceId": str(item.id)})
        result = PrivateItemDTO.model_validate(item)
    return result


async def modify_item(
    item_id: UUID,
    body: PrivateItemEdit | VersionInput,
    request: Request,
    actor: Actor,
    deleting: bool,
):
    key, payload = idempotency_key(request), body.model_dump(mode="json")
    operation = f"private:{'delete' if deleting else 'edit'}:{item_id}"
    async with transaction(request, actor) as (db, user):
        item = await db.scalar(
            select(PrivateItem).where(PrivateItem.id == item_id, PrivateItem.user_id == user.id)
        )
        if item is None:
            raise DomainError(404, "NOT_FOUND", "Không tìm thấy nội dung.")
        old = await previous_receipt(db, user, operation, key, payload)
        if not old:
            if item.version != body.expected_version or item.status == "deleted":
                raise DomainError(409, "STALE_VERSION", "Nội dung đã thay đổi.")
            item.version += 1
            item.status = "deleted" if deleting else "edited"
            item.text = body.text if isinstance(body, PrivateItemEdit) else ""
            user.data_version += 1
            user.profile_version += 1
            await invalidate_user_social(db, user.id)
            await db.execute(
                update(Memory)
                .where(Memory.source_id == item_id)
                .values(status="deleted", text="", version=Memory.version + 1)
            )
            receipt = {
                "actionId": str(uuid4()),
                "resourceId": str(item.id),
                "resourceVersion": item.version,
                "status": "succeeded",
            }
            save_receipt(db, user, operation, key, payload, receipt)
        else:
            receipt = old
        result = (
            ActionReceipt.model_validate(receipt)
            if deleting
            else PrivateItemDTO.model_validate(item)
        )
    request.app.state.ai.invalidate(str(actor.user_id))
    return result


@router.patch("/profiles/private-items/{item_id}", response_model=PrivateItemDTO)
async def edit_item(
    item_id: UUID, body: PrivateItemEdit, request: Request, actor: Actor = Depends(require_actor)
):
    return await modify_item(item_id, body, request, actor, False)


@router.delete("/profiles/private-items/{item_id}", response_model=ActionReceipt)
async def delete_item(
    item_id: UUID, body: VersionInput, request: Request, actor: Actor = Depends(require_actor)
):
    return await modify_item(item_id, body, request, actor, True)
