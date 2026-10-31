"""Explicit removal of every proactive store for one user (account and guest purge)."""

from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.collaboration.models import AiCollaboration, AiSharingPermission
from app.ai.proactive.models import (
    AiConversationRead,
    AiMessageSource,
    AiProactiveJob,
    AiProactiveSchedule,
    AiProactiveSettings,
)

# Children before parents: jobs reference schedules/runs, sources and receipts reference runs.
# Collaboration receipts and sharing opt-ins (Phase 2) go with the same owner-scoped purge.
OWNED = (AiCollaboration, AiSharingPermission, AiMessageSource, AiConversationRead, AiProactiveJob, AiProactiveSchedule, AiProactiveSettings)


async def purge_proactive(db: AsyncSession, uid: UUID) -> None:
    for model in OWNED:
        await db.execute(delete(model).where(model.user_id == uid))
