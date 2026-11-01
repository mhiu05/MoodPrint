"""Proactive stores follow account deletion, private-data deletion and retention (P1-02)."""

from datetime import timedelta

import pytest
from sqlalchemy import func, select, text

from tests.proactive_helpers import seed_proactive

PROACTIVE_TABLES = (
    "ai_proactive_settings",
    "ai_proactive_schedules",
    "ai_proactive_jobs",
    "ai_conversation_reads",
    "ai_message_sources",
)


async def _seed_run(app, uid, **kwargs):
    from app.ai.models import AiConversation
    from app.infrastructure.database.models import AiRun, now

    async with app.state.database.sessions.begin() as db:
        conversation = AiConversation(user_id=uid, bot_id="nhip", expires_at=now() + timedelta(days=5))
        db.add(conversation)
        await db.flush()
        run = AiRun(
            user_id=uid, conversation_id=conversation.id, bot_id="nhip", status="completed",
            origin="proactive", proactive_slot="morning",
        )
        db.add(run)
        await db.flush()
        return await seed_proactive(db, uid, conversation_id=conversation.id, run_id=run.id, **kwargs)


async def _counts(app, uid):
    async with app.state.database.sessions() as db:
        return {
            table: await db.scalar(
                text(f"select count(*) from moodprint.{table} where user_id = :u"), {"u": uid}
            )
            for table in PROACTIVE_TABLES
        }


async def _delete(app, uid, scope):
    from app.modules.users.lifecycle import process_deletions
    from app.modules.users.models import DataJob

    async with app.state.database.sessions.begin() as db:
        db.add(DataJob(user_id=uid, kind="deletion", scope=scope, status="queued"))
    await process_deletions(app)


@pytest.mark.postgres
@pytest.mark.parametrize("scope", ["account", "all_private"])
async def test_deletion_removes_every_proactive_store_of_only_that_user(clients, scope):
    app, actors = clients
    (_, owner), (_, other) = actors
    await _seed_run(app, owner)
    await _seed_run(app, other)
    assert set((await _counts(app, owner)).values()) == {1}

    await _delete(app, owner, scope)

    # The users row is a tombstone, so FK cascades never ran: rows must go explicitly.
    assert await _counts(app, owner) == dict.fromkeys(PROACTIVE_TABLES, 0)
    assert set((await _counts(app, other)).values()) == {1}


@pytest.mark.postgres
async def test_retention_drops_only_jobs_finished_more_than_30_days_ago(clients):
    from app.ai.proactive.models import AiProactiveJob
    from app.jobs.retention import purge_expired

    app, actors = clients
    (_, first), (_, second) = actors
    old = await _seed_run(app, first, finished_days_ago=31)
    recent = await _seed_run(app, second, finished_days_ago=29)

    await purge_expired(app)

    async with app.state.database.sessions() as db:
        remaining = set((await db.scalars(select(AiProactiveJob.id))).all())
        assert remaining == {recent}
        assert old not in remaining
        assert await db.scalar(select(func.count()).select_from(AiProactiveJob)) == 1


@pytest.mark.postgres
async def test_retention_never_drops_an_unfinished_job(clients):
    from app.ai.proactive.models import AiProactiveJob
    from app.jobs.retention import purge_expired

    app, actors = clients
    _, uid = actors[0]
    job = await _seed_run(app, uid)  # pending, never finished
    async with app.state.database.sessions.begin() as db:
        row = await db.get(AiProactiveJob, job)
        row.created_at = row.created_at - timedelta(days=60)
    await purge_expired(app)
    async with app.state.database.sessions() as db:
        assert await db.get(AiProactiveJob, job) is not None
