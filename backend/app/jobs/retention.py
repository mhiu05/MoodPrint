"""Bounded cleanup for the local active database; no provider/backup erasure claim."""

from datetime import timedelta

from sqlalchemy import Date, cast, delete, func, select

from app.infrastructure.database.models import (
    AiRun,
    AiUsage,
    Idempotency,
    Mood,
    Outbox,
    User,
    now,
)
from app.modules.social.models import CandidateReference, HumanMessage


async def purge_expired(app):
    async with app.state.database.require()() as db, db.begin():
        from app.ai.memory import expire_proposals, purge_proposals
        from app.ai.persistence import purge_chat, recover_turns

        await recover_turns(db)
        await purge_chat(db)
        await expire_proposals(db)
        await purge_proposals(db)
        # Retention continues after the accounting kill switch is turned off;
        # old hosted schemas can still run before the expand migration is approved.
        if await db.scalar(select(func.to_regclass("moodprint.ai_usage"))):
            ids = (
                await db.scalars(
                    select(AiUsage.run_id)
                    .where(
                        AiUsage.created_at <= now() - timedelta(days=90),
                        AiUsage.state != "open",
                    )
                    .limit(1000)
                    .with_for_update(skip_locked=True)
                )
            ).all()
            if ids:
                await db.execute(delete(AiUsage).where(AiUsage.run_id.in_(ids)))
        # Content-free run metadata; saved threads expire within 90 days, so older runs
        # no longer anchor any message. Usage rows for these runs cascade.
        from app.ai.models import AiMessageRecord

        run_ids = (
            await db.scalars(
                select(AiRun.id)
                .where(
                    AiRun.created_at <= now() - timedelta(days=90),
                    AiRun.status != "running",
                    ~select(AiMessageRecord.id).where(AiMessageRecord.run_id == AiRun.id).exists(),
                )
                .order_by(AiRun.id)
                .limit(1000)
                .with_for_update(skip_locked=True)
            )
        ).all()
        if run_ids:
            await db.execute(delete(AiRun).where(AiRun.id.in_(run_ids)))
        # Date buckets use the owner's timezone, consistently with the mood API.
        mood_ids = (
            await db.scalars(
                select(Mood.id)
                .join(User, User.id == Mood.user_id)
                .where(Mood.local_date < cast(func.timezone(User.timezone, now()), Date) - 89)
                .order_by(Mood.id)
                .limit(1000)
                .with_for_update(of=Mood, skip_locked=True)
            )
        ).all()
        if mood_ids:
            await db.execute(delete(Mood).where(Mood.id.in_(mood_ids)))
        message_ids = (
            await db.scalars(
                select(HumanMessage.id)
                .where(HumanMessage.created_at <= now() - timedelta(days=90))
                .order_by(HumanMessage.id)
                .limit(1000)
                .with_for_update(skip_locked=True)
            )
        ).all()
        if message_ids:
            await db.execute(delete(HumanMessage).where(HumanMessage.id.in_(message_ids)))
        # Candidate/safety references live 15 minutes; a day later no replay can use them.
        refs = (
            await db.scalars(
                select(CandidateReference.id)
                .where(CandidateReference.expires_at <= now() - timedelta(hours=24))
                .order_by(CandidateReference.id)
                .limit(1000)
                .with_for_update(skip_locked=True)
            )
        ).all()
        if refs:
            await db.execute(delete(CandidateReference).where(CandidateReference.id.in_(refs)))
        keys = (
            await db.scalars(
                select(Idempotency.id)
                .where(Idempotency.created_at <= now() - timedelta(hours=24))
                .order_by(Idempotency.id)
                .limit(1000)
                .with_for_update(skip_locked=True)
            )
        ).all()
        if keys:
            await db.execute(delete(Idempotency).where(Idempotency.id.in_(keys)))
        # Activity answers live 90 days like messages; finished sessions 90 days after ending.
        from app.modules.activities.models import ActivityResponse, ActivitySession

        answers = (
            await db.execute(
                select(
                    ActivityResponse.session_id, ActivityResponse.user_id, ActivityResponse.round
                )
                .where(ActivityResponse.submitted_at <= now() - timedelta(days=90))
                .limit(1000)
            )
        ).all()
        for session_id, user_id, round_number in answers:
            await db.execute(
                delete(ActivityResponse).where(
                    ActivityResponse.session_id == session_id,
                    ActivityResponse.user_id == user_id,
                    ActivityResponse.round == round_number,
                )
            )
        finished = (
            await db.scalars(
                select(ActivitySession.id)
                .where(
                    ActivitySession.state.in_(
                        ("completed", "ended", "declined", "cancelled", "expired", "aborted")
                    ),
                    ActivitySession.ended_at <= now() - timedelta(days=90),
                )
                .limit(1000)
                .with_for_update(skip_locked=True)
            )
        ).all()
        if finished:
            await db.execute(delete(ActivitySession).where(ActivitySession.id.in_(finished)))
        # Reports and moderation decisions are kept one year (safety record), then purged.
        from app.modules.moderation.models import ModerationAction, Report

        year = now() - timedelta(days=365)
        old_actions = (
            await db.scalars(
                select(ModerationAction.id).where(ModerationAction.created_at <= year).limit(1000)
            )
        ).all()
        if old_actions:
            await db.execute(delete(ModerationAction).where(ModerationAction.id.in_(old_actions)))
        old_reports = (
            await db.scalars(
                select(Report.id)
                .where(
                    Report.created_at <= year,
                    ~select(ModerationAction.id)
                    .where(ModerationAction.report_id == Report.id)
                    .exists(),
                )
                .limit(1000)
            )
        ).all()
        if old_reports:
            await db.execute(delete(Report).where(Report.id.in_(old_reports)))
        # Read markers outlive their room by 90 days; open rooms keep them however old.
        from app.modules.social.models import Connection, ConnectionRead, MatchingStatsDaily

        stale_reads = (
            await db.execute(
                select(ConnectionRead.connection_id, ConnectionRead.user_id)
                .join(Connection, Connection.id == ConnectionRead.connection_id)
                .where(
                    Connection.status != "open",
                    ConnectionRead.updated_at <= now() - timedelta(days=90),
                )
                .limit(1000)
            )
        ).all()
        for connection_id, user_id in stale_reads:
            await db.execute(
                delete(ConnectionRead).where(
                    ConnectionRead.connection_id == connection_id,
                    ConnectionRead.user_id == user_id,
                )
            )
        # Identifier-free matching counters are kept one year (C-08).
        await db.execute(
            delete(MatchingStatsDaily).where(MatchingStatsDaily.day < cast(year, Date))
        )
        # Retired outbox (no consumer): drain the backlog oldest first until the table is dropped.
        outbox = (
            await db.scalars(
                select(Outbox.id)
                .order_by(Outbox.created_at, Outbox.id)
                .limit(1000)
                .with_for_update(skip_locked=True)
            )
        ).all()
        if outbox:
            await db.execute(delete(Outbox).where(Outbox.id.in_(outbox)))
