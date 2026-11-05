"""Lease-fenced local deletion worker. Provider/backups remain separate tracked gates."""

import logging
from datetime import timedelta
from uuid import uuid4

from app.infrastructure.database.models import (
    AgeDeclaration,
    AiRun,
    AiUsage,
    AuthSession,
    Idempotency,
    Memory,
    Mood,
    User,
    now,
)
from app.modules.feedback.models import FeedbackSubmissionReceipt
from app.modules.journal.service import purge_owned_journal
from app.modules.moderation.models import IdentityField, RevealAccess
from app.modules.social.models import (
    Connection,
    ConnectionRequest,
    HumanMessage,
    MatchingDraft,
    PublishedProfile,
)
from app.modules.social.service import invalidate_user_social
from app.modules.users.models import DataJob
from sqlalchemy import and_, delete, func, or_, select, text, update

logger = logging.getLogger("moodprint.lifecycle")


async def _release_exhausted(db) -> None:
    """A job out of attempts must not leave the user locked behind deletion_pending."""
    jobs = (
        await db.scalars(
            select(DataJob)
            .where(
                DataJob.kind == "deletion",
                DataJob.attempts >= 5,
                DataJob.status == "running",
                DataJob.lease_until < now(),
            )
            .with_for_update(skip_locked=True)
            .limit(10)
        )
    ).all()
    for job in jobs:
        job.status, job.lease_until, job.version = "failed", None, job.version + 1
        await db.execute(
            update(User).where(User.id == job.user_id).values(deletion_pending=False)
        )
        logger.error("deletion_job_failed scope=%s attempts=%s", job.scope, job.attempts)


async def process_deletions(app):
    sessions = app.state.database.require()
    async with sessions() as db, db.begin():
        job = await db.scalar(
            select(DataJob)
            .where(
                DataJob.kind == "deletion",
                DataJob.attempts < 5,
                or_(
                    DataJob.status == "queued",
                    and_(DataJob.status == "running", DataJob.lease_until < now()),
                ),
            )
            .order_by(DataJob.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if job is None:
            await _release_exhausted(db)
            return
        job.status = "running"
        job.attempts += 1
        job.lease_token = uuid4()
        job.lease_until = now() + timedelta(seconds=30)
        identity, uid, fence = job.id, job.user_id, job.lease_token
    async with sessions() as db, db.begin():
        user = await db.scalar(select(User).where(User.id == uid).with_for_update())
        job = await db.scalar(select(DataJob).where(DataJob.id == identity).with_for_update())
        if job.lease_token != fence or job.status != "running":
            return
        scopes = {job.scope}
        if job.scope in ("all_private", "account"):
            scopes = {"memories", "moods", "journal", "identity", "matching"}
            from app.ai.models import AiConversation, AiPreference, AiTurn
            from app.ai.proactive.lifecycle import purge_proactive

            # Schedules reveal daily routines; provenance names journal entries.
            await purge_proactive(db, uid)
            from app.ai.search.maps_jobs import detach_searches
            await detach_searches(db, uid)
            await db.execute(delete(AiConversation).where(AiConversation.user_id == uid))
            await db.execute(delete(AiPreference).where(AiPreference.user_id == uid))
            from app.modules.journal.ai_models import JournalAiSettings

            await db.execute(delete(JournalAiSettings).where(JournalAiSettings.user_id == uid))
            # Temporary-chat turn digests have no conversation row to cascade from.
            await db.execute(delete(AiTurn).where(AiTurn.user_id == uid))
        if "memories" in scopes:
            from app.ai.journal_memory import fence_deleted_memories
            from app.ai.memory_models import MemoryProposal

            await fence_deleted_memories(db, uid)
            await db.execute(delete(MemoryProposal).where(MemoryProposal.user_id == uid))
            await db.execute(delete(Memory).where(Memory.user_id == uid))
        if "moods" in scopes:
            await db.execute(delete(Mood).where(Mood.user_id == uid))
        if "journal" in scopes:
            await purge_owned_journal(db, uid)
        if "identity" in scopes:
            await db.execute(
                update(RevealAccess)
                .where(or_(RevealAccess.owner_id == uid, RevealAccess.recipient_id == uid))
                .values(status="revoked", version=RevealAccess.version + 1)
            )
            await db.execute(delete(IdentityField).where(IdentityField.user_id == uid))
        if "matching" in scopes:
            from app.modules.activities import hooks
            from app.modules.activities.models import ActivityParticipant, ActivityResponse

            await hooks.abort_for_user(db, uid, "account_deleted")
            from app.modules.social.models import ConnectionRead

            await db.execute(delete(ConnectionRead).where(ConnectionRead.user_id == uid))
            await db.execute(delete(ActivityResponse).where(ActivityResponse.user_id == uid))
            await db.execute(
                update(ActivityParticipant)
                .where(ActivityParticipant.user_id == uid)
                .values(feedback=None, feedback_at=None)
            )
            await invalidate_user_social(db, uid)
            user.profile_version += 1
            await db.execute(delete(MatchingDraft).where(MatchingDraft.user_id == uid))
            await db.execute(delete(PublishedProfile).where(PublishedProfile.user_id == uid))
            await db.execute(
                update(Connection)
                .where(
                    or_(Connection.low_user_id == uid, Connection.high_user_id == uid),
                    Connection.status == "open",
                )
                .values(status="closed", version=Connection.version + 1)
            )
            await db.execute(
                update(ConnectionRequest)
                .where(
                    or_(ConnectionRequest.sender_id == uid, ConnectionRequest.recipient_id == uid),
                    ConnectionRequest.status == "pending",
                )
                .values(status="invalidated", version=ConnectionRequest.version + 1)
            )
        if job.scope == "account":
            # The retained voluntary rating has no owner; remove only its temporary owner link.
            await db.execute(delete(FeedbackSubmissionReceipt).where(FeedbackSubmissionReceipt.user_id == uid))
            retained_runs = set()
            if await db.scalar(select(func.to_regclass("moodprint.ai_usage"))):
                from app.ai.accounting import liability_scope

                # The user remains a tombstone. Keep only financial metadata needed
                # by the active cap; deleting it would refund already dispatched work.
                # Usage -> run lock order matches terminal settlement and recovery.
                retained_runs = set((await db.scalars(select(AiUsage.run_id).where(
                    # Current budget=0 is not permission to erase historical debt.
                    # Keep relevant settled legacy rows too: a later cap activation
                    # must revalue them or fail closed, never see a free empty ledger.
                    AiUsage.user_id == uid, liability_scope(now()),
                ).order_by(AiUsage.run_id).with_for_update())).all())
                if retained_runs:
                    parents = dict((await db.execute(select(AiRun.id, AiRun.parent_run_id)
                                   .where(AiRun.user_id == uid))).all())
                    pending = list(retained_runs)
                    while pending:
                        parent = parents.get(pending.pop())
                        if parent is not None and parent not in retained_runs:
                            retained_runs.add(parent)
                            pending.append(parent)
                await db.execute(delete(AiUsage).where(AiUsage.user_id == uid,
                                                       AiUsage.run_id.not_in(retained_runs)))
                await db.execute(update(AiRun).where(AiRun.id.in_(retained_runs),
                                                    AiRun.status == "running")
                                 .values(status="cancelled", version=2))
            await db.execute(delete(AgeDeclaration).where(AgeDeclaration.user_id == uid))
            from app.modules.journal.quota import OPERATIONS

            await db.execute(delete(Idempotency).where(Idempotency.user_id == uid, Idempotency.operation.in_(tuple(OPERATIONS.values()))))
            await db.execute(
                update(HumanMessage).where(HumanMessage.sender_id == uid).values(text="[Đã xóa]")
            )
            await db.execute(
                update(AuthSession).where(AuthSession.user_id == uid).values(revoked=True)
            )
            # Financial anchors and their ancestors must survive cascades. The
            # existing bounded metadata retention removes old completed anchors.
            await db.execute(delete(AiRun).where(AiRun.user_id == uid,
                                                AiRun.id.not_in(retained_runs)))
            user.status = "deleted"
            user.alias = "Đã xóa"
            await db.flush()
            # Same transaction: the Supabase identity goes only if all app data went too.
            await db.execute(
                text("select moodprint.delete_provider_identity(:uid)"), {"uid": uid}
            )
            job.status = "completed"
        else:
            job.status = "completed"
        user.deletion_pending = False
        job.version += 1
        job.lease_until = None
        # Receipts store only resource IDs, but expired keys still need bounded retention.
        from app.modules.journal.quota import expired_receipts

        await db.execute(
            delete(Idempotency).where(expired_receipts(now()))
        )
