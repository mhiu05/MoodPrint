"""Lease-fenced local deletion worker. Provider/backups remain separate tracked gates."""

from datetime import timedelta
from uuid import uuid4

from sqlalchemy import and_, delete, func, or_, select, update

from app.infrastructure.database.models import (
    AgeDeclaration,
    AiUsage,
    AuthSession,
    Idempotency,
    Memory,
    Mood,
    PrivateItem,
    User,
    now,
)
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
            scopes = {"memories", "moods", "private_items", "identity", "matching"}
        if "memories" in scopes or "private_items" in scopes:
            await db.execute(delete(Memory).where(Memory.user_id == uid))
        if "private_items" in scopes:
            await db.execute(delete(PrivateItem).where(PrivateItem.user_id == uid))
        if "moods" in scopes:
            await db.execute(delete(Mood).where(Mood.user_id == uid))
        if "identity" in scopes:
            await db.execute(
                update(RevealAccess)
                .where(or_(RevealAccess.owner_id == uid, RevealAccess.recipient_id == uid))
                .values(status="revoked", version=RevealAccess.version + 1)
            )
            await db.execute(delete(IdentityField).where(IdentityField.user_id == uid))
        if "matching" in scopes:
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
            if await db.scalar(select(func.to_regclass("moodprint.ai_usage"))):
                await db.execute(delete(AiUsage).where(AiUsage.user_id == uid))
            await db.execute(delete(AgeDeclaration).where(AgeDeclaration.user_id == uid))
            await db.execute(
                update(HumanMessage).where(HumanMessage.sender_id == uid).values(text="[Đã xóa]")
            )
            await db.execute(
                update(AuthSession).where(AuthSession.user_id == uid).values(revoked=True)
            )
            user.status = "deleted"
            job.status = "awaiting_provider"
        else:
            job.status = "completed"
        user.deletion_pending = False
        job.version += 1
        job.lease_until = None
        # Receipts store only resource IDs, but expired keys still need bounded retention.
        await db.execute(
            delete(Idempotency).where(Idempotency.created_at < now() - timedelta(hours=24))
        )
