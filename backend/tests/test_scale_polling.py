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
        app.state.settings.ai_dispatch_gate_enabled = True
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


@pytest.mark.postgres
@pytest.mark.parametrize("reader", ["stream", "monitor"])
@pytest.mark.parametrize(("change", "code"), [
    ("provider_session", "SESSION_EXPIRED"),
    ("application_session", "SESSION_EXPIRED"),
    ("session_expiry", "SESSION_EXPIRED"),
    ("auth_version", "SESSION_EXPIRED"),
    ("age", "ELIGIBILITY_REQUIRED"),
    ("suspended", "ACCOUNT_SUSPENDED"),
    ("deleting", "DELETION_IN_PROGRESS"),
    ("purpose", "CONSENT_REQUIRED"),
    ("data_version", "CONTEXT_CHANGED"),
    ("conversation", "NOT_FOUND"),
])
async def test_running_poll_revalidates_each_authority_on_the_next_snapshot(clients, change, code, reader):
    from datetime import timedelta
    from uuid import uuid4

    from sqlalchemy import select

    from app.ai.models import AiConversation
    from app.core.errors import DomainError
    from app.infrastructure.database.models import AgeDeclaration, AuthSession, Consent, User, now

    app, actors = clients
    client, uid = actors[0]
    await enable(client)
    model = make_test_model("Synthetic reply")
    model.hold = True
    app.state.ai.model_override = model
    created = await client.post("/api/v1/ai/conversations", headers=key(), json={"botId": "may", "persistent": True})
    cid = UUID(created.json()["conversationId"])
    accepted = await client.post(f"/api/v1/ai/conversations/{cid}/messages", headers=key(), json={
        "text": "Synthetic", "clientMessageId": str(uuid4()), "expectedConversationVersion": 1,
    })
    assert accepted.status_code == 202, accepted.text
    run = app.state.ai.runs[UUID(accepted.json()["runId"])]
    await asyncio.wait_for(model.started.wait(), 5)
    request = Request({"type": "http", "app": app, "headers": []})

    async def read():
        app.state.settings.ai_dispatch_gate_enabled = True
        if reader == "monitor":
            await app.state.ai.check(run, completed_ok=True)
        else:
            assert (await durable_run(request, run.actor, run.id, poll=True, recover=False))[0].id == run.id

    try:
        await read()
        async with app.state.database.sessions.begin() as db:
            user = await db.get(User, uid)
            session = await db.scalar(select(AuthSession).where(AuthSession.user_id == uid))
            if change == "provider_session":
                await db.execute(text("delete from auth.sessions where user_id=:uid"), {"uid": uid})
            elif change == "application_session":
                session.revoked = True
            elif change == "session_expiry":
                session.expires_at = now() - timedelta(seconds=1)
            elif change == "auth_version":
                user.auth_version += 1
            elif change == "age":
                await db.delete(await db.get(AgeDeclaration, uid))
            elif change == "suspended":
                user.suspended_until = now() + timedelta(hours=1)
            elif change == "deleting":
                user.deletion_pending = True
            elif change == "purpose":
                await db.delete(await db.get(Consent, (uid, "AI")))
            elif change == "data_version":
                user.data_version += 1
            else:
                (await db.get(AiConversation, cid)).expires_at = now() - timedelta(seconds=1)
        with pytest.raises(DomainError) as denied:
            await read()
        assert denied.value.code == ("CONVERSATION_EXPIRED" if reader == "monitor" and change == "conversation" else code)
    finally:
        model.release.set()
        await run.task


@pytest.mark.postgres
@pytest.mark.parametrize("change", ["turn_worker", "turn_lease", "usage_worker", "usage_lease", "run_status", "run_owner"])
async def test_monitor_does_not_accept_changed_worker_or_run_authority(clients, change):
    from datetime import timedelta
    from uuid import uuid4

    from app.ai.models import AiTurn
    from app.core.errors import DomainError
    from app.infrastructure.database.models import AiRun, AiUsage, now

    app, actors = clients
    client = actors[0][0]
    app.state.settings.ai_dispatch_gate_enabled = True
    app.state.settings.ai_accounting_enabled = True
    model = make_test_model("Synthetic reply")
    model.hold = True
    app.state.ai.model_override = model
    await enable(client)
    created = await client.post("/api/v1/ai/conversations", headers=key(), json={"botId": "may", "persistent": True})
    accepted = await client.post(f"/api/v1/ai/conversations/{created.json()['conversationId']}/messages", headers=key(), json={
        "text": "Synthetic", "clientMessageId": str(uuid4()), "expectedConversationVersion": 1,
    })
    assert accepted.status_code == 202, accepted.text
    run = app.state.ai.runs[UUID(accepted.json()["runId"])]
    await asyncio.wait_for(model.started.wait(), 5)
    try:
        await app.state.ai.check(run, completed_ok=True)
        async with app.state.database.sessions.begin() as db:
            if change.startswith("turn_"):
                row = await db.get(AiTurn, run.id)
            elif change.startswith("usage_"):
                row = await db.get(AiUsage, run.id)
            else:
                row = await db.get(AiRun, run.id)
            if change.endswith("worker"):
                row.worker_id = uuid4()
            elif change.endswith("lease"):
                row.lease_until = now() - timedelta(seconds=1)
            elif change == "run_status":
                row.status = "cancelled"
            else:
                row.user_id = actors[1][1]
        with pytest.raises(DomainError) as denied:
            await app.state.ai.check(run, completed_ok=True)
        assert denied.value.code == (
            "WORKER_FENCED" if change.startswith(("turn_", "usage_"))
            else "RUN_ENDED"
        )
    finally:
        model.release.set()
        await run.task


@pytest.mark.postgres
@pytest.mark.parametrize("cancel", [False, True])
async def test_candidate_terminal_reconnect_replays_without_another_paid_attempt(clients, cancel):
    from uuid import uuid4

    from sqlalchemy import func, select

    from app.infrastructure.database.models import AiRun, AiUsage

    app, actors = clients
    client, uid = actors[0]
    app.state.settings.ai_dispatch_gate_enabled = True
    app.state.settings.ai_accounting_enabled = True
    model = make_test_model("Synthetic persisted answer")
    model.hold = True
    app.state.ai.model_override = model
    await enable(client)
    created = await client.post("/api/v1/ai/conversations", headers=key(), json={"botId": "may", "persistent": True})
    accepted = await client.post(f"/api/v1/ai/conversations/{created.json()['conversationId']}/messages", headers=key(), json={
        "text": "Synthetic", "clientMessageId": str(uuid4()), "expectedConversationVersion": 1,
    })
    assert accepted.status_code == 202, accepted.text
    run = app.state.ai.runs[UUID(accepted.json()["runId"])]
    await asyncio.wait_for(model.started.wait(), 5)
    try:
        if cancel:
            stopped = await client.post(f"/api/v1/ai/runs/{run.id}/cancel", json={"expectedVersion": 1})
            assert stopped.status_code == 200, stopped.text
        else:
            model.release.set()
        await asyncio.wait_for(run.task, 5)
        found = await durable_run(Request({"type": "http", "app": app, "headers": []}), run.actor, run.id, poll=True, recover=False)
        assert found[0].status == ("cancelled" if cancel else "completed")
        assert len(found[2]) == (0 if cancel else 1)
        for _ in range(2):
            replay = await client.get(accepted.json()["eventsUrl"], headers={"Last-Event-ID": "1"})
            assert replay.status_code == 200
            assert ('"cancelled"' if cancel else '"completed"') in replay.text
            assert ("Synthetic persisted answer" in replay.text) is (not cancel)
            assert "UNVALIDATED-RAW-CANARY" not in replay.text
        async with app.state.database.sessions() as db:
            assert await db.scalar(select(func.count()).select_from(AiRun).where(AiRun.user_id == uid)) == 1
            assert (await db.get(AiUsage, run.id)).requests_started == 1
    finally:
        model.release.set()
        await run.task
