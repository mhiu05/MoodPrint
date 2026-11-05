"""Queued provider work must never hold the application's startup health gate."""

import asyncio

from sqlalchemy import text


async def test_due_journal_provider_work_starts_after_health_is_available(clients, monkeypatch):
    from app.core.revisions import READY_REVISIONS

    app, actors = clients
    started, release = asyncio.Event(), asyncio.Event()

    async def held_provider_batch(*args, **kwargs):
        started.set()
        await release.wait()
        return 0

    monkeypatch.setattr("app.modules.journal.indexing.process_journal_jobs", held_provider_batch)
    async with app.state.database.sessions.begin() as db:
        await db.execute(text("create table if not exists moodprint.alembic_version (version_num varchar(32) primary key)"))
        await db.execute(text("delete from moodprint.alembic_version"))
        await db.execute(text("insert into moodprint.alembic_version values (:v)"), {"v": READY_REVISIONS[0]})
    lifecycle = app.router.lifespan_context(app)
    entered = False
    try:
        await asyncio.wait_for(lifecycle.__aenter__(), 2)
        entered = True
        client = actors[0][0]
        assert not release.is_set()
        assert (await client.get("/api/v1/health/live")).status_code == 200
        assert (await client.get("/api/v1/health/ready")).status_code == 200
        await asyncio.wait_for(started.wait(), 5)
        assert not release.is_set()
        assert (await client.get("/api/v1/health/ready")).status_code == 200
    finally:
        release.set()
        if entered:
            await lifecycle.__aexit__(None, None, None)
