"""Durable proposal decisions and owner-managed approved memory resources."""

import json
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings import enqueue_memory, invalidate_memory
from app.ai.memory_models import MemoryProposal
from app.ai.schemas import MemoryDTO, MemoryEdit, ProposalConfirm
from app.contracts import DTO, ActionReceipt, BotId, VersionInput
from app.core.errors import DomainError
from app.core.security import (
    Actor,
    assert_purpose,
    digest,
    idempotency_key,
    lock_actor,
    previous_receipt,
    require_actor,
    save_receipt,
    transaction,
)
from app.infrastructure.database.models import Consent, ConsentEvent, Memory, now

router = APIRouter()


class ProposalDTO(DTO):
    id: UUID
    bot_id: BotId
    text: str
    version: int
    status: str
    expires_at: datetime


async def create_proposal(
    db: AsyncSession,
    actor: Actor,
    bot_id: str,
    text: str,
    data_version: int,
) -> MemoryProposal:
    """Create only a preview, in the caller's short transaction; never approve it."""
    user = await lock_actor(db, actor)
    await assert_purpose(db, user, "AI")
    from app.ai.agents import caps

    if not caps(bot_id).memory and bot_id != "rure":
        raise DomainError(422, "MEMORY_BOT_FORBIDDEN", "Trợ lý này không được đề xuất ghi nhớ.")
    if not 1 <= len(text.strip()) <= 120:
        raise DomainError(422, "INVALID_PROPOSAL", "Nội dung đề xuất chưa hợp lệ.")
    if user.data_version != data_version:
        raise DomainError(409, "CONTEXT_CHANGED", "Quyền hoặc dữ liệu đã thay đổi.")
    consents = {
        c.purpose: c.version
        for c in (
            await db.scalars(
                select(Consent).where(
                    Consent.user_id == user.id, Consent.purpose.in_(("AI", "MEM"))
                )
            )
        ).all()
    }
    await expire_proposals(db, user.id)
    count = await db.scalar(
        select(func.count())
        .select_from(MemoryProposal)
        .where(MemoryProposal.user_id == user.id, MemoryProposal.status == "pending")
    )
    if count and count >= 100:
        raise DomainError(429, "PROPOSAL_LIMIT", "Hãy xử lý các đề xuất đang chờ trước.")
    expires = now() + timedelta(minutes=15)
    if user.account_kind == "guest" and user.guest_expires_at is not None:
        expires = min(expires, user.guest_expires_at)
    proposal = MemoryProposal(
        user_id=user.id,
        bot_id=bot_id,
        text=text.strip(),
        data_version=data_version,
        ai_consent_version=consents.get("AI", 0),
        mem_consent_version=consents.get("MEM", 0),
        expires_at=expires,
    )
    db.add(proposal)
    await db.flush()
    return proposal


async def expire_proposals(db: AsyncSession, user_id: UUID | None = None) -> int:
    """Clear expired preview content; usable from the periodic retention worker."""
    from sqlalchemy import update

    query = update(MemoryProposal).where(
        MemoryProposal.status == "pending", MemoryProposal.expires_at <= now()
    )
    if user_id is not None:
        query = query.where(MemoryProposal.user_id == user_id)
    result = await db.execute(
        query.values(
            status="expired", text="", version=MemoryProposal.version + 1, decided_at=now()
        )
    )
    return result.rowcount  # type: ignore[attr-defined, no-any-return]


async def purge_proposals(db: AsyncSession) -> int:
    """Bound content-free decision tombstones and their replay window to 30 days."""
    ids = (
        await db.scalars(
            select(MemoryProposal.id)
            .where(
                MemoryProposal.status != "pending",
                MemoryProposal.decided_at <= now() - timedelta(days=30),
            )
            .order_by(MemoryProposal.id)
            .limit(1000)
            .with_for_update(skip_locked=True)
        )
    ).all()
    if ids:
        await db.execute(delete(MemoryProposal).where(MemoryProposal.id.in_(ids)))
    return len(ids)


def _changed(request: Request, actor: Actor):
    request.app.state.ai.invalidate(str(actor.user_id))


@router.get("/memories", response_model=list[MemoryDTO])
async def memories(request: Request, actor: Actor = Depends(require_actor)):
    async with transaction(request, actor) as (db, user):
        rows = (
            await db.scalars(
                select(Memory)
                .where(Memory.user_id == user.id, Memory.status == "active")
                .order_by(Memory.id)
            )
        ).all()
        return [MemoryDTO.model_validate(row) for row in rows]


@router.get("/proposals", response_model=list[ProposalDTO])
async def proposals(request: Request, actor: Actor = Depends(require_actor)):
    async with transaction(request, actor) as (db, user):
        await expire_proposals(db, user.id)
        rows = (
            await db.scalars(
                select(MemoryProposal)
                .where(MemoryProposal.user_id == user.id)
                .order_by(
                    (MemoryProposal.status == "pending").desc(),
                    MemoryProposal.created_at.desc(),
                    MemoryProposal.id,
                )
                .limit(100)
            )
        ).all()
        return [ProposalDTO.model_validate(row) for row in rows]


async def _proposal(db: AsyncSession, actor: Actor, identity: UUID) -> MemoryProposal:
    proposal = await db.scalar(
        select(MemoryProposal)
        .where(MemoryProposal.id == identity, MemoryProposal.user_id == actor.user_id)
        .with_for_update()
    )
    if proposal is None:
        raise DomainError(404, "NOT_FOUND", "Không tìm thấy đề xuất.")
    return proposal


def _payload_digest(payload: dict) -> str:
    return digest(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")))


def _replay(proposal: MemoryProposal, status: str, payload: dict) -> ActionReceipt | None:
    if proposal.status == "pending":
        return None
    if proposal.status == "expired":
        raise DomainError(410, "PROPOSAL_EXPIRED", "Đề xuất đã hết hạn.")
    if proposal.status != status:
        raise DomainError(409, "PROPOSAL_DECIDED", "Đề xuất đã được xử lý.")
    if proposal.decision_digest != _payload_digest(payload):
        raise DomainError(409, "IDEMPOTENCY_CONFLICT", "Đề xuất đã được xử lý với nội dung khác.")
    return ActionReceipt.model_validate(proposal.receipt)


@router.post("/proposals/{proposal_id}/confirm", response_model=ActionReceipt)
async def confirm(
    proposal_id: UUID,
    body: ProposalConfirm,
    request: Request,
    actor: Actor = Depends(require_actor),
):
    key, payload = idempotency_key(request), body.model_dump(mode="json")
    expired = False
    async with transaction(request, actor) as (db, user):
        proposal = await _proposal(db, actor, proposal_id)
        old = _replay(proposal, "approved", payload)
        if old:
            return old
        if proposal.expires_at <= now():
            await expire_proposals(db, user.id)
            expired = True
        else:
            consents = await assert_purpose(db, user, "AI")
            # Any withdrawal/re-grant since the preview stales it. Sibling approvals and
            # unrelated mood/profile revisions do not, so each preview stays decidable.
            if (
                proposal.version != body.expected_version
                or consents["AI"].version != proposal.ai_consent_version
                or consents["MEM"].version != proposal.mem_consent_version
            ):
                raise DomainError(409, "STALE_VERSION", "Đề xuất hoặc quyền đã thay đổi.")
            if proposal.bot_id == "caunoi":
                raise DomainError(403, "MEMORY_BOT_FORBIDDEN", "Trợ lý này không được ghi nhớ.")
            if not consents["MEM"].enabled:
                # Approving this item is the explicit authorization to retain and
                # retrieve approved memories. The decision is audited in one commit.
                memory_consent = consents["MEM"]
                memory_consent.enabled = True
                memory_consent.policy_version = "v1"
                memory_consent.version += 1
                user.data_version += 1
                db.add(ConsentEvent(user_id=user.id, purpose="MEM", enabled=True,
                                    version=memory_consent.version, policy_version="v1"))
                # Other previews created under the same unwithdrawn permission
                # decision remain individually reviewable after the first approval.
                await db.execute(
                    update(MemoryProposal)
                    .where(
                        MemoryProposal.user_id == user.id,
                        MemoryProposal.id != proposal.id,
                        MemoryProposal.status == "pending",
                        MemoryProposal.mem_consent_version == proposal.mem_consent_version,
                    )
                    .values(mem_consent_version=memory_consent.version)
                )
            text = body.edited_text if body.edited_text is not None else proposal.text
            record = Memory(
                user_id=user.id,
                bot_id=proposal.bot_id,
                text=text,
                proposal_id=proposal.id,
            )
            db.add(record)
            await db.flush()
            receipt = ActionReceipt(
                action_id=uuid4(), resource_id=str(record.id), resource_version=record.version
            )
            proposal.status, proposal.version, proposal.decided_at = (
                "approved",
                proposal.version + 1,
                now(),
            )
            # The approved resource owns its text; previews are no longer needed.
            proposal.text = ""
            proposal.decision_digest = _payload_digest(payload)
            proposal.receipt = receipt.model_dump(mode="json", by_alias=True)
            save_receipt(db, user, f"proposal:{proposal_id}", key, payload, proposal.receipt)
            user.data_version += 1
            await enqueue_memory(db, record, request.app.state.settings)
    if expired:
        raise DomainError(410, "PROPOSAL_EXPIRED", "Đề xuất đã hết hạn.")
    _changed(request, actor)
    return receipt


@router.post("/proposals/{proposal_id}/reject", response_model=ActionReceipt)
async def reject_proposal(
    proposal_id: UUID,
    body: VersionInput,
    request: Request,
    actor: Actor = Depends(require_actor),
):
    key, payload = idempotency_key(request), body.model_dump(mode="json")
    expired = False
    async with transaction(request, actor) as (db, user):
        proposal = await _proposal(db, actor, proposal_id)
        old = _replay(proposal, "rejected", payload)
        if old:
            return old
        if proposal.expires_at <= now():
            await expire_proposals(db, user.id)
            expired = True
        else:
            if proposal.version != body.expected_version:
                raise DomainError(409, "STALE_VERSION", "Đề xuất đã thay đổi.")
            proposal.status, proposal.text = "rejected", ""
            proposal.version, proposal.decided_at = proposal.version + 1, now()
            receipt = ActionReceipt(
                action_id=uuid4(), resource_id=str(proposal.id), resource_version=proposal.version
            )
            proposal.decision_digest = _payload_digest(payload)
            proposal.receipt = receipt.model_dump(mode="json", by_alias=True)
            save_receipt(db, user, f"proposal:reject:{proposal_id}", key, payload, proposal.receipt)
    if expired:
        raise DomainError(410, "PROPOSAL_EXPIRED", "Đề xuất đã hết hạn.")
    return receipt


@router.patch("/memories/{memory_id}", response_model=MemoryDTO)
async def edit_memory(
    memory_id: UUID,
    body: MemoryEdit,
    request: Request,
    actor: Actor = Depends(require_actor),
):
    key, payload = idempotency_key(request), body.model_dump(mode="json")
    async with transaction(request, actor) as (db, user):
        item = await db.scalar(
            select(Memory)
            .where(Memory.id == memory_id, Memory.user_id == user.id, Memory.status == "active")
            .with_for_update()
        )
        if item is None:
            raise DomainError(404, "NOT_FOUND", "Không tìm thấy mục ghi nhớ.")
        old = await previous_receipt(db, user, f"memory:{memory_id}", key, payload)
        if not old:
            if item.version != body.expected_version:
                raise DomainError(409, "STALE_VERSION", "Mục ghi nhớ đã thay đổi.")
            await invalidate_memory(db, item.id)
            item.text, item.version = body.text, item.version + 1
            user.data_version += 1
            await db.flush()
            await enqueue_memory(db, item, request.app.state.settings)
            save_receipt(
                db,
                user,
                f"memory:{memory_id}",
                key,
                payload,
                {"resourceId": str(item.id), "version": item.version},
            )
        result = MemoryDTO.model_validate(item)
    _changed(request, actor)
    return result


@router.delete("/memories/{memory_id}", response_model=ActionReceipt)
async def delete_memory(
    memory_id: UUID,
    body: VersionInput,
    request: Request,
    actor: Actor = Depends(require_actor),
):
    key, payload = idempotency_key(request), body.model_dump(mode="json")
    async with transaction(request, actor) as (db, user):
        item = await db.scalar(
            select(Memory)
            .where(Memory.id == memory_id, Memory.user_id == user.id)
            .with_for_update()
        )
        if item is None:
            raise DomainError(404, "NOT_FOUND", "Không tìm thấy mục ghi nhớ.")
        old = await previous_receipt(db, user, f"memory:delete:{memory_id}", key, payload)
        if old:
            return ActionReceipt.model_validate(old)
        if item.version != body.expected_version:
            raise DomainError(409, "STALE_VERSION", "Mục ghi nhớ đã thay đổi.")
        await invalidate_memory(db, item.id)
        item.text, item.status, item.version = "", "deleted", item.version + 1
        user.data_version += 1
        receipt = ActionReceipt(
            action_id=uuid4(), resource_id=str(item.id), resource_version=item.version
        )
        save_receipt(
            db,
            user,
            f"memory:delete:{memory_id}",
            key,
            payload,
            receipt.model_dump(mode="json", by_alias=True),
        )
    _changed(request, actor)
    return receipt
