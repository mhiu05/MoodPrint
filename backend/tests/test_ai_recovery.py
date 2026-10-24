import asyncio
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.ai.runtime import LiveRun
from app.core.security import Actor
from app.infrastructure.database.models import AiRun, AuthSession, User
from tests.fakes import ScriptedModel, message_output

pytestmark = pytest.mark.postgres


def key():
    return {"Idempotency-Key": str(uuid4())}


async def seed_unstarted_run(clients):
    app, actors = clients
    client, uid = actors[0]
    response = await client.put(
        "/api/v1/consents/AI",
        json={"enabled": True, "expectedVersion": 1, "policyVersion": "v1"},
        headers=key(),
    )
    assert response.status_code == 200
    runtime = app.state.ai
    model = ScriptedModel([[message_output('{"text":"Never emitted","cards":[]}')]], hold=True)
    runtime.model_override = model
    async with app.state.database.sessions.begin() as db:
        user = await db.get(User, uid)
        session = await db.scalar(select(AuthSession).where(AuthSession.user_id == uid))
        c = runtime.store.create(str(uid), str(session.id), "may")
        run = LiveRun(Actor(uid, session.id, user.auth_version), c.id, user.data_version, uuid4())
        db.add(AiRun(id=run.id, user_id=uid, conversation_id=c.id, bot_id="may"))
    runtime.runs[run.id] = run
    c.active_run_id = run.id
    run.task = asyncio.create_task(runtime.drive(run))
    return runtime, run, c, model


async def test_cancel_before_coroutine_entry_releases_conversation_and_persists_once(clients):
    runtime, run, c, model = await seed_unstarted_run(clients)
    # Cancel in the same scheduler turn: drive() cannot execute its finally block.
    run.task.cancel()
    await asyncio.gather(run.task, return_exceptions=True)
    client = clients[1][0][0]
    endpoint = f"/api/v1/ai/runs/{run.id}/cancel"
    response = await client.post(endpoint, json={"expectedVersion": 1})
    assert response.status_code == 200
    assert response.json()["version"] == 2
    assert run.terminal and c.active_run_id is None and model.calls == []
    assert [e.type for e in run.events] == ["cancelled"]
    replay = await client.post(endpoint, json={"expectedVersion": 1})
    assert replay.json() == response.json() and len(run.events) == 1
    async with clients[0].state.database.sessions() as db:
        row = await db.get(AiRun, run.id)
        assert row.status == "cancelled" and row.version == 2
    next_run = await client.post(
        f"/api/v1/ai/conversations/{c.id}/messages",
        json={
            "text": "A fresh synthetic turn",
            "clientMessageId": str(uuid4()),
            "expectedConversationVersion": c.version,
        },
        headers=key(),
    )
    assert next_run.status_code == 202
    await runtime.stop(runtime.runs[UUID(next_run.json()["runId"])])


async def test_end_and_shutdown_finalize_tasks_that_have_not_entered_drive(clients):
    runtime, run, c, model = await seed_unstarted_run(clients)
    run.task.cancel()
    await asyncio.gather(run.task, return_exceptions=True)
    response = await clients[1][0][0].post(f"/api/v1/ai/conversations/{c.id}/end")
    assert response.status_code == 204
    async with clients[0].state.database.sessions() as db:
        assert (await db.get(AiRun, run.id)).status == "cancelled"
    assert model.calls == [] and c.id not in runtime.store.conversations


async def test_revoke_cancels_sdk_without_late_final_or_tool_and_records_terminal_state(clients):
    runtime, run, c, model = await seed_unstarted_run(clients)
    await asyncio.wait_for(model.started.wait(), 3)
    client = clients[1][0][0]
    response = await client.put(
        "/api/v1/consents/AI",
        json={"enabled": False, "expectedVersion": 2, "policyVersion": "v1"},
        headers=key(),
    )
    assert response.status_code == 200
    await asyncio.wait_for(asyncio.gather(run.task, return_exceptions=True), 3)
    assert model.cancelled and len(model.calls) == 1
    assert not any(e.type == "final" for e in run.events)
    await runtime.close()
    assert runtime.runs == {} and run.events == []
    async with clients[0].state.database.sessions() as db:
        assert (await db.get(AiRun, run.id)).status == "cancelled"


async def test_restart_interrupts_orphan_metadata_without_replaying_provider_input(clients):
    from app.core.config import Settings
    from app.main import create_app

    app, actors = clients
    identity = uuid4()
    async with app.state.database.sessions.begin() as db:
        db.add(AiRun(id=identity, user_id=actors[0][1], conversation_id=uuid4(), bot_id="may"))
    restarted = create_app(Settings(_env_file=None))
    restarted.state.database.sessions = app.state.database.sessions
    # create_app's closure keeps the Database instance stored on app.state.
    async with restarted.router.lifespan_context(restarted):
        async with app.state.database.sessions() as db:
            row = await db.get(AiRun, identity)
            assert row.status == "interrupted" and row.version == 2
        assert restarted.state.ai.store.conversations == {} and restarted.state.ai.runs == {}


async def test_terminal_write_failure_is_sanitized_and_retried_without_model_replay(
    clients, monkeypatch, caplog
):
    from app.core.errors import DomainError

    runtime, run, c, model = await seed_unstarted_run(clients)
    original = runtime.database.require

    def unavailable():
        raise RuntimeError("SECRET-DATABASE-ERROR-CANARY")

    monkeypatch.setattr(runtime.database, "require", unavailable)
    with pytest.raises(DomainError) as failed:
        await runtime.stop(run)
    assert failed.value.code == "CANCEL_PENDING" and failed.value.status == 503
    assert not run.terminal_persisted and run.id in runtime.pending_terminal
    assert "SECRET-DATABASE-ERROR-CANARY" not in caplog.text
    monkeypatch.setattr(runtime.database, "require", original)
    runtime.sweep()
    await run.finalization_task
    assert run.terminal_persisted and run.id not in runtime.pending_terminal
    assert model.calls == [] and [e.type for e in run.events] == ["cancelled"]
    async with clients[0].state.database.sessions() as db:
        assert (await db.get(AiRun, run.id)).status == "cancelled"


async def test_other_user_and_stale_version_cannot_cancel_an_active_sdk_run(clients):
    runtime, run, c, model = await seed_unstarted_run(clients)
    await asyncio.wait_for(model.started.wait(), 3)
    endpoint = f"/api/v1/ai/runs/{run.id}/cancel"
    other = await clients[1][1][0].post(endpoint, json={"expectedVersion": 1})
    assert other.status_code == 404 and not model.cancelled
    stale = await clients[1][0][0].post(endpoint, json={"expectedVersion": 0})
    assert stale.status_code == 409 and not model.cancelled
    await runtime.stop(run)
    assert model.cancelled and run.terminal_persisted
