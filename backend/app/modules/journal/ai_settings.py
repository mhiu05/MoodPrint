"""Independent, owner-versioned preferences for derived journal processing."""

from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import Field
from sqlalchemy import delete, func, select, update

from app.contracts import DTO
from app.core.errors import DomainError
from app.core.security import (
    Actor,
    idempotency_key,
    previous_receipt,
    require_registered_actor,
    save_receipt,
    transaction,
)
from app.infrastructure.database.models import AiRun, Consent, Memory, now
from app.modules.auth.age import is_adult_eligible
from app.modules.consent.policy import consent_enabled
from app.modules.journal.ai_models import JournalAiJob, JournalAiSettings, JournalEntryEmbedding
from app.modules.journal.models import JournalEntry

router = APIRouter()


class JournalAiSettingsView(DTO):
    embedding_enabled: bool
    auto_memory_enabled: bool
    embedding_available: bool
    auto_memory_available: bool
    notice_version: Literal["journal-ai-v1"] = "journal-ai-v1"
    version: int
    indexed_entries: int
    pending_entries: int
    auto_memories: int


class JournalAiSettingsInput(DTO):
    embedding_enabled: bool
    auto_memory_enabled: bool
    notice_version: Literal["journal-ai-v1"]
    expected_version: int = Field(ge=1)


async def journal_ai_eligible(db, user) -> bool:
    if (user.account_kind != "registered" or user.status != "active"
            or user.deletion_pending or not await is_adult_eligible(db, user)):
        return False
    consent = await db.get(Consent, (user.id, "AI"))
    return bool(consent and consent.policy_version == "v1" and consent_enabled("AI", consent.enabled))


async def journal_ai_allowed(db, user, settings, kind: Literal["embed", "memories"]) -> int | None:
    if not await journal_ai_eligible(db, user):
        return None
    pref = await db.get(JournalAiSettings, user.id)
    if kind == "embed":
        allowed = settings.journal_semantic_available and (pref is None or pref.embedding_enabled)
    else:
        # Automatic extraction is introduced together with its labels in JI-30/31.
        allowed = False
    return (pref.version if pref else 1) if allowed else None


async def settings_view(db, user, settings) -> JournalAiSettingsView:
    pref = await db.get(JournalAiSettings, user.id)
    version = pref.version if pref else 1
    indexed = await db.scalar(select(func.count()).select_from(JournalEntryEmbedding).join(
        JournalEntry, JournalEntry.id == JournalEntryEmbedding.entry_id,
    ).where(JournalEntryEmbedding.user_id == user.id, JournalEntry.user_id == user.id,
            JournalEntry.status == "saved", JournalEntry.version == JournalEntryEmbedding.entry_version,
            JournalEntryEmbedding.settings_version == version,
            JournalEntryEmbedding.model == settings.voyage_model,
            JournalEntryEmbedding.dimensions == settings.voyage_dimensions))
    pending = await db.scalar(select(func.count(func.distinct(JournalAiJob.entry_id))).where(
        JournalAiJob.user_id == user.id, JournalAiJob.kind == "embed",
        JournalAiJob.status.in_(("pending", "running", "retry")),
    ))
    memories = await db.scalar(select(func.count()).select_from(Memory).where(
        Memory.user_id == user.id, Memory.origin == "journal_auto", Memory.status == "active",
    ))
    return JournalAiSettingsView(
        embedding_enabled=pref.embedding_enabled if pref else True,
        auto_memory_enabled=pref.auto_memory_enabled if pref else True,
        embedding_available=settings.journal_semantic_available and await journal_ai_eligible(db, user),
        auto_memory_available=False, version=version,
        indexed_entries=indexed or 0, pending_entries=pending or 0, auto_memories=memories or 0,
    )


@router.get("/journal/ai-settings", response_model=JournalAiSettingsView)
async def get_settings(request: Request, actor: Actor = Depends(require_registered_actor)):
    async with transaction(request, actor) as (db, user):
        return await settings_view(db, user, request.app.state.settings)


@router.put("/journal/ai-settings", response_model=JournalAiSettingsView)
async def put_settings(body: JournalAiSettingsInput, request: Request, actor: Actor = Depends(require_registered_actor)):
    key, payload = idempotency_key(request), body.model_dump(mode="json")
    async with transaction(request, actor) as (db, user):
        old = await previous_receipt(db, user, "journal:ai-settings", key, payload)
        if old:
            return JournalAiSettingsView.model_validate(old)
        pref = await db.get(JournalAiSettings, user.id)
        if (pref.version if pref else 1) != body.expected_version:
            raise DomainError(409, "STALE_VERSION", "Tùy chọn đã thay đổi. Hãy tải lại.")
        if pref is None:
            pref = JournalAiSettings(user_id=user.id, version=1)
            db.add(pref)
        pref.embedding_enabled, pref.auto_memory_enabled = body.embedding_enabled, body.auto_memory_enabled
        pref.notice_version, pref.updated_at = body.notice_version, now()
        pref.version += 1
        kinds = []
        if not body.embedding_enabled:
            await db.execute(delete(JournalEntryEmbedding).where(JournalEntryEmbedding.user_id == user.id))
            kinds.append("embed")
        if not body.auto_memory_enabled:
            kinds.append("memories")
        if kinds:
            await db.execute(update(JournalAiJob).where(
                JournalAiJob.user_id == user.id, JournalAiJob.kind.in_(kinds),
                JournalAiJob.status.in_(("pending", "retry", "running")),
            ).values(status="cancelled", lease_token=None, lease_until=None))
        user.data_version += 1
        await db.execute(update(AiRun).where(AiRun.user_id == user.id, AiRun.status == "running").values(
            status="cancelled", version=AiRun.version + 1,
        ))
        await db.flush()
        result = await settings_view(db, user, request.app.state.settings)
        save_receipt(db, user, "journal:ai-settings", key, payload, result.model_dump(mode="json", by_alias=True))
    request.app.state.ai.invalidate(str(actor.user_id))
    return result
