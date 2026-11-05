import asyncio
from uuid import UUID

import pytest
from sqlalchemy import event, text
from starlette.requests import Request

from app.ai.chat_routes import durable_run
from tests.fakes import make_test_model
from tests.test_chat_persistence import enable, key


@pytest.mark.postgres
async def test_joined_actor_rechecks_provider_session_after_each_transaction(clients):
    from sqlalchemy import select

    from app.core.errors import DomainError
    from app.core.security import Actor, lock_actor
    from app.infrastructure.database.models import AuthSession

    app, actors = clients
    uid = actors[0][1]
    async with app.state.database.sessions() as db:
        session = await db.scalar(select(AuthSession).where(AuthSession.user_id == uid))
        actor = Actor(uid, session.id, session.auth_version)
    for lock in (False, True):
        async with app.state.database.sessions.begin() as db:
            await lock_actor(db, actor, lock=lock)
    async with app.state.database.sessions.begin() as db:
        await db.execute(text("delete from auth.sessions where user_id=:uid"), {"uid": uid})
    for lock in (False, True):
        async with app.state.database.sessions.begin() as db:
            with pytest.raises(DomainError) as denied:
                await lock_actor(db, actor, lock=lock)
            assert denied.value.code == "SESSION_EXPIRED"


@pytest.mark.postgres
async def test_writer_rechecks_provider_revocation_after_waiting_for_account_lock(clients):
    from sqlalchemy import select

    from app.core.errors import DomainError
    from app.core.security import Actor, lock_actor
    from app.infrastructure.database.models import AuthSession, User

    app, actors = clients
    uid = actors[0][1]
    async with app.state.database.sessions() as db:
        session = await db.scalar(select(AuthSession).where(AuthSession.user_id == uid))
        actor = Actor(uid, session.id, session.auth_version)
    pid_ready = asyncio.get_running_loop().create_future()

    async def waiting_writer():
        async with app.state.database.sessions.begin() as db:
            pid_ready.set_result(await db.scalar(text("select pg_backend_pid()")))
            return await lock_actor(db, actor)

    async with app.state.database.sessions.begin() as blocker:
        await blocker.scalar(select(User).where(User.id == uid).with_for_update())
        task = asyncio.create_task(waiting_writer())
        try:
            pid = await asyncio.wait_for(pid_ready, 5)
            async with asyncio.timeout(5):
                while True:
                    async with app.state.database.sessions() as observer:
                        waiting = await observer.scalar(text(
                            "select wait_event_type = 'Lock' from pg_stat_activity where pid=:pid"
                        ), {"pid": pid})
                    if waiting:
                        break
                    await asyncio.sleep(0.01)
            async with app.state.database.sessions.begin() as revoker:
                await revoker.execute(text("delete from auth.sessions where user_id=:uid"), {"uid": uid})
        except BaseException:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            raise
    with pytest.raises(DomainError) as denied:
        await asyncio.wait_for(task, 5)
    assert denied.value.code == "SESSION_EXPIRED"


@pytest.mark.postgres
async def test_running_saved_poll_keeps_authorization_and_has_a_bounded_query_budget(clients):
    app, actors = clients
    client = actors[0][0]
    model = make_test_model("Synthetic reply")
    model.hold = True
    app.state.ai.model_override = model
    await enable(client)
    created = await client.post("/api/v1/ai/conversations", json={"botId": "may", "persistent": True}, headers=key())
    cid = created.json()["conversationId"]
    accepted = await client.post(f"/api/v1/ai/conversations/{cid}/messages", headers=key(),
                                 json={"text": "Synthetic", "clientMessageId": str(__import__('uuid').uuid4()), "expectedConversationVersion": 1})
    run_id = UUID(accepted.json()["runId"])
    run = app.state.ai.runs[run_id]
    await asyncio.wait_for(model.started.wait(), timeout=5)
    query_count = 0

    def count(*args):
        nonlocal query_count
        query_count += 1

    engine = app.state.database.engine.sync_engine
    event.listen(engine, "before_cursor_execute", count)
    try:
        found = await durable_run(Request({"type": "http", "app": app, "headers": []}),
                                  run.actor, run_id, poll=True, recover=False)
        assert found[0].status == "running" and found[2] == []
        assert query_count <= 3
        query_count = 0
        await app.state.ai.check(run)
        assert query_count <= 5
    finally:
        event.remove(engine, "before_cursor_execute", count)
        model.release.set()
        await run.task
