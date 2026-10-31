"""Synthetic proactive rows (no real schedules or content) shared by lifecycle tests."""

from datetime import date, datetime, time, timedelta
from uuid import UUID, uuid4


async def seed_proactive(db, uid: UUID, *, conversation_id: UUID, run_id: UUID, finished_days_ago: int | None = None):
    """One row in each of the five proactive stores; returns the job id."""
    from app.ai.proactive.models import (
        AiConversationRead,
        AiMessageSource,
        AiProactiveJob,
        AiProactiveSchedule,
        AiProactiveSettings,
    )
    from app.infrastructure.database.models import now

    db.add(AiProactiveSettings(user_id=uid, timezone="Asia/Ho_Chi_Minh"))
    schedule = AiProactiveSchedule(
        user_id=uid, bot_id="nhip", slot="morning", enabled=True, local_time=time(7, 30),
        next_due_at=now() + timedelta(hours=1),
    )
    db.add(schedule)
    await db.flush()
    due = now() - timedelta(days=finished_days_ago or 0)
    job = AiProactiveJob(
        user_id=uid, schedule_id=schedule.id, bot_id="nhip", slot="morning",
        local_date=date.today() - timedelta(days=finished_days_ago or 0),
        due_at=due, expires_at=due + timedelta(minutes=90), available_at=due,
        status="delivered" if finished_days_ago is not None else "pending",
        run_id=run_id if finished_days_ago is not None else None,
        finished_at=due if finished_days_ago is not None else None,
        schedule_version=1, settings_version=1,
    )
    db.add(job)
    db.add(AiConversationRead(conversation_id=conversation_id, user_id=uid, last_read_sequence=1))
    db.add(
        AiMessageSource(
            run_id=run_id, user_id=uid, source_kind="journal_entry", source_id=uuid4(),
            source_revision=1, source_local_date=date.today(), policy="proactive-journal-v1@1",
        )
    )
    await db.flush()
    return job.id


def utc(year, month, day, hour=0, minute=0):
    from datetime import UTC

    return datetime(year, month, day, hour, minute, tzinfo=UTC)
