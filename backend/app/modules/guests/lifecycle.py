"""Hard purge of a guest's complete active-store footprint in one owner-locked transaction.

Unlike the registered tombstone worker this removes the identity itself. The inventory below is
checked against every ORM table by tests, so a new table must be classified here or the suite
fails. Provider identity deletion goes through the narrow, guarded SQL helper in the same
transaction (it is the same database as Supabase Auth), so a helper failure rolls back every row.
No provider or network call happens while locks are held.
"""

import logging
from typing import Literal
from uuid import UUID

from sqlalchemy import and_, delete, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embedding_models import EmbeddingJob, MemoryEmbedding
from app.ai.memory_models import MemoryProposal
from app.ai.models import AiConversation, AiMessageRecord, AiPreference, AiTurn
from app.infrastructure.database.models import (
    AgeDeclaration,
    AiRun,
    AiUsage,
    AuthSession,
    Consent,
    ConsentEvent,
    Idempotency,
    Memory,
    Mood,
    Outbox,
    PrivateItem,
    User,
)
from app.modules.activities.models import ActivityParticipant, ActivityResponse, ActivitySession
from app.modules.guests.models import (
    GuestCleanupJob,
    GuestOperationLink,
    GuestProvisioningAttempt,
    GuestUsage,
)
from app.modules.guests.policy import database_time
from app.modules.moderation.models import (
    IdentityField,
    ModerationAction,
    Report,
    RevealAccess,
    StaffRole,
)
from app.modules.social.models import (
    Block,
    CandidateReference,
    Connection,
    ConnectionRead,
    ConnectionRequest,
    HumanMessage,
    MatchingDraft,
    Pair,
    PublishedProfile,
)
from app.modules.users.models import DataJob

log = logging.getLogger("moodprint")

PurgeResult = Literal["removed", "incident_required", "fenced"]

# Every ORM table, classified. The cleanup test fails when a table is missing from this map.
#   purged    - rows owned by (or derived for) the guest, deleted by this module
#   social    - forbidden for guests; guest-only graphs are deleted, a registered counterpart is
#               retained evidence and turns the purge into an incident (never a blind cascade)
#   detached  - holds no identity and is never deleted here (liability, counters, aggregates)
#   owner     - the user row itself, deleted last
INVENTORY: dict[str, str] = {
    "users": "owner",
    "auth_sessions": "purged",
    "age_declarations": "purged",
    "consents": "purged",
    "consent_events": "purged",
    "private_items": "purged",
    "moods": "purged",
    "memories": "purged",
    "memory_proposals": "purged",
    "memory_embeddings": "purged",
    "memory_embedding_jobs": "purged",
    "ai_preferences": "purged",
    "ai_conversations": "purged",
    "ai_messages": "purged",
    "ai_turns": "purged",
    "ai_runs": "purged",
    "ai_usage": "purged",
    "idempotency_keys": "purged",
    "outbox": "purged",
    "data_jobs": "purged",
    "identity_fields": "purged",
    "staff_roles": "purged",
    "matching_drafts": "purged",
    "published_profiles": "purged",
    "candidate_references": "purged",
    "guest_provisioning_attempts": "purged",
    "guest_cleanup_jobs": "purged",
    "guest_usage": "purged",
    "guest_operation_links": "purged",
    "pairs": "social",
    "connections": "social",
    "connection_requests": "social",
    "connection_reads": "social",
    "human_messages": "social",
    "blocks": "social",
    "reports": "social",
    "moderation_actions": "social",
    "reveal_access": "social",
    "activity_sessions": "social",
    "activity_participants": "social",
    "activity_responses": "social",
    "guest_abuse_buckets": "detached",
    "guest_budget_days": "detached",
    "guest_cost_reservations": "detached",
    "matching_stats_daily": "detached",
}


async def _foreign_evidence(db: AsyncSession, uid: UUID) -> bool:
    """True when a social/safety row ties this guest to any user who is not itself a guest."""
    others = select(User.id).where(User.account_kind != "guest")
    checks = (
        select(Pair.id).where(
            or_(
                and_(Pair.low_user_id == uid, Pair.high_user_id.in_(others)),
                and_(Pair.high_user_id == uid, Pair.low_user_id.in_(others)),
            )
        ),
        select(Connection.id).where(
            or_(
                and_(Connection.low_user_id == uid, Connection.high_user_id.in_(others)),
                and_(Connection.high_user_id == uid, Connection.low_user_id.in_(others)),
            )
        ),
        select(ConnectionRequest.id).where(
            or_(
                and_(ConnectionRequest.sender_id == uid, ConnectionRequest.recipient_id.in_(others)),
                and_(ConnectionRequest.recipient_id == uid, ConnectionRequest.sender_id.in_(others)),
            )
        ),
        select(Block.blocker_id).where(
            or_(
                and_(Block.blocker_id == uid, Block.blocked_id.in_(others)),
                and_(Block.blocked_id == uid, Block.blocker_id.in_(others)),
            )
        ),
        select(Report.id).where(
            or_(
                and_(Report.reporter_id == uid, Report.subject_id.in_(others)),
                and_(Report.subject_id == uid, Report.reporter_id.in_(others)),
            )
        ),
        select(RevealAccess.id).where(
            or_(
                and_(RevealAccess.owner_id == uid, RevealAccess.recipient_id.in_(others)),
                and_(RevealAccess.recipient_id == uid, RevealAccess.owner_id.in_(others)),
            )
        ),
        select(ModerationAction.id).where(
            or_(ModerationAction.subject_id == uid, ModerationAction.staff_id == uid)
        ),
        select(ActivitySession.id).where(
            or_(
                and_(ActivitySession.inviter_id == uid, ActivitySession.invitee_id.in_(others)),
                and_(ActivitySession.invitee_id == uid, ActivitySession.inviter_id.in_(others)),
            )
        ),
    )
    for check in checks:
        if await db.scalar(check.limit(1)) is not None:
            return True
    return False


async def _delete_guest_only_social(db: AsyncSession, uid: UUID) -> None:
    """Remove a malformed guest-only social graph, children first (FK order)."""
    rooms = (
        await db.scalars(
            select(Connection.id).where(or_(Connection.low_user_id == uid, Connection.high_user_id == uid))
        )
    ).all()
    pairs = (
        await db.scalars(select(Pair.id).where(or_(Pair.low_user_id == uid, Pair.high_user_id == uid)))
    ).all()
    sessions = (
        await db.scalars(
            select(ActivitySession.id).where(
                or_(
                    ActivitySession.inviter_id == uid,
                    ActivitySession.invitee_id == uid,
                    ActivitySession.connection_id.in_(rooms),
                )
            )
        )
    ).all()
    await db.execute(
        delete(ActivityResponse).where(
            or_(ActivityResponse.user_id == uid, ActivityResponse.session_id.in_(sessions))
        )
    )
    await db.execute(
        delete(ActivityParticipant).where(
            or_(ActivityParticipant.user_id == uid, ActivityParticipant.session_id.in_(sessions))
        )
    )
    await db.execute(delete(ActivitySession).where(ActivitySession.id.in_(sessions)))
    await db.execute(
        delete(RevealAccess).where(
            or_(
                RevealAccess.owner_id == uid,
                RevealAccess.recipient_id == uid,
                RevealAccess.connection_id.in_(rooms),
            )
        )
    )
    await db.execute(
        delete(HumanMessage).where(
            or_(HumanMessage.sender_id == uid, HumanMessage.connection_id.in_(rooms))
        )
    )
    await db.execute(
        delete(ConnectionRead).where(
            or_(ConnectionRead.user_id == uid, ConnectionRead.connection_id.in_(rooms))
        )
    )
    await db.execute(
        delete(ConnectionRequest).where(
            or_(
                ConnectionRequest.sender_id == uid,
                ConnectionRequest.recipient_id == uid,
                ConnectionRequest.pair_id.in_(pairs),
            )
        )
    )
    await db.execute(delete(Connection).where(Connection.id.in_(rooms)))
    await db.execute(delete(Pair).where(Pair.id.in_(pairs)))
    await db.execute(delete(Block).where(or_(Block.blocker_id == uid, Block.blocked_id == uid)))
    await db.execute(
        delete(ModerationAction).where(
            or_(ModerationAction.subject_id == uid, ModerationAction.staff_id == uid)
        )
    )
    await db.execute(delete(Report).where(or_(Report.reporter_id == uid, Report.subject_id == uid)))


async def _delete_owned(db: AsyncSession, uid: UUID) -> None:
    conversations = (
        await db.scalars(select(AiConversation.id).where(AiConversation.user_id == uid))
    ).all()
    await db.execute(
        delete(AiMessageRecord).where(AiMessageRecord.conversation_id.in_(conversations))
    )
    for model in (
        AiTurn,
        AiUsage,
        AiRun,
        AiConversation,
        AiPreference,
        EmbeddingJob,
        MemoryEmbedding,
        MemoryProposal,
        Memory,
        PrivateItem,
        Mood,
        IdentityField,
        StaffRole,
        Idempotency,
        Outbox,
        DataJob,
        ConsentEvent,
        Consent,
        AgeDeclaration,
        MatchingDraft,
        PublishedProfile,
        GuestOperationLink,
        GuestUsage,
        AuthSession,
    ):
        await db.execute(delete(model).where(model.user_id == uid))
    await db.execute(
        delete(CandidateReference).where(
            or_(CandidateReference.user_id == uid, CandidateReference.peer_id == uid)
        )
    )
    # Never leave a SET NULL row behind that still names the provider subject or correlation.
    await db.execute(
        delete(GuestProvisioningAttempt).where(GuestProvisioningAttempt.user_id == uid)
    )


async def purge_guest(db: AsyncSession, user_id: UUID, lease_token: UUID) -> PurgeResult:
    """Purge one guest under the owner lock; the caller commits (or rolls back) the transaction.

    ``fenced``: not this worker's lease, not a guest, or access is still legitimately open.
    ``incident_required``: real counterpart evidence exists; nothing destructive was done and the
    guest stays permanently non-active (never reactivated, never a tombstone exception).
    ``removed``: every guest-owned row, session, job, attempt and the provider identity are gone.
    """
    user = await db.scalar(select(User).where(User.id == user_id).with_for_update())
    job = await db.get(GuestCleanupJob, user_id, with_for_update=True)
    if user is None:
        return "removed"  # idempotent replay of a completed purge
    now = await database_time(db)
    if (
        user.account_kind != "guest"
        or job is None
        or job.lease_token != lease_token
        or job.lease_until is None
        or job.lease_until <= now
    ):
        return "fenced"
    if user.status == "active" and now < (user.guest_expires_at or now):
        return "fenced"
    if user.status == "active":
        user.status = "deleting"
        user.auth_version += 1
    await db.execute(
        update(AuthSession).where(AuthSession.user_id == user_id).values(revoked=True)
    )
    if await _foreign_evidence(db, user_id):
        job.state, job.alerted_at, job.last_error = "incident_required", now, "peer_evidence"
        job.lease_token, job.lease_until = None, None
        log.warning("metric=guest_incident reason=peer_evidence")
        return "incident_required"
    await _delete_guest_only_social(db, user_id)
    await _delete_owned(db, user_id)
    removed = await db.scalar(
        text("select moodprint.delete_guest_provider_identity(:user_id)"), {"user_id": user_id}
    )
    if removed is not True:
        raise RuntimeError("provider identity still present")
    await db.execute(delete(User).where(User.id == user_id))  # cascades the cleanup job
    return "removed"
