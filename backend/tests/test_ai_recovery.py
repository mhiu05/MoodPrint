import asyncio
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, update

from app.ai.runtime import LiveRun
from app.core.security import Actor
from app.infrastructure.database.models import AiRun, AuthSession, Consent, User
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
        # Mirror POST /ai/conversations, which records the AI consent version.
        c.ai_consent_version = (await db.get(Consent, (uid, "AI"))).version
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


async def test_repeated_cancellation_cannot_skip_terminal_finalization(clients, monkeypatch):
    runtime, run, conversation, model = await seed_unstarted_run(clients)
    await asyncio.wait_for(model.started.wait(), 3)
    entered, release = asyncio.Event(), asyncio.Event()
    original = runtime.settle_guest

    async def held_settlement(*args):
        entered.set()
        await release.wait()
        return await original(*args)

    monkeypatch.setattr(runtime, "settle_guest", held_settlement)
    runtime.request_cancel(run)
    await asyncio.wait_for(entered.wait(), 3)
    run.task.cancel()  # policy/expiry/heartbeat can arrive while terminal IO is in flight
    release.set()
    await asyncio.wait_for(asyncio.gather(run.task, return_exceptions=True), 3)
    assert run.terminal and conversation.active_run_id is None
    assert not any(event.type == "final" for event in run.events)
    async with clients[0].state.database.sessions() as db:
        assert (await db.get(AiRun, run.id)).status == "cancelled"
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


@pytest.mark.parametrize("stored_status", ["interrupted", "cancelled", "failed", None])
async def test_durable_terminal_or_deleted_run_never_publishes_a_late_final(clients, stored_status):
    from sqlalchemy import delete

    runtime, run, c, model = await seed_unstarted_run(clients)
    await asyncio.wait_for(model.started.wait(), 3)
    async with runtime.database.sessions.begin() as db:
        if stored_status is None:
            await db.execute(delete(AiRun).where(AiRun.id == run.id))
        else:
            await db.execute(
                update(AiRun).where(AiRun.id == run.id).values(status=stored_status, version=2)
            )
    model.release.set()
    await asyncio.wait_for(run.task, 3)
    assert not any(event.type == "final" for event in run.events)
    assert c.messages == [] and run.terminal_persisted
    assert run.id not in runtime.pending_terminal
    async with runtime.database.sessions() as db:
        row = await db.get(AiRun, run.id)
        assert row is None if stored_status is None else row.status == stored_status


async def test_interrupted_run_cannot_create_a_new_tool_proposal(clients):
    from agents.tool_context import ToolContext

    from app.core.errors import DomainError

    runtime, run, _, model = await seed_unstarted_run(clients)
    await asyncio.wait_for(model.started.wait(), 3)
    async with runtime.database.sessions.begin() as db:
        await db.execute(
            update(AiRun).where(AiRun.id == run.id).values(status="interrupted", version=2)
        )
    tool = next(t for t in runtime.tools(run, "guong") if t.name == "propose_memory")
    arguments = '{"text":"A stale synthetic proposal"}'
    with pytest.raises(DomainError) as stopped:
        await tool.on_invoke_tool(
            ToolContext(context=run, tool_name=tool.name, tool_call_id="stale", tool_arguments=arguments),
            arguments,
        )
    assert stopped.value.code == "RUN_ENDED" and runtime.proposals == {}
    await runtime.stop(run)


async def test_late_cancel_does_not_overwrite_an_already_completed_database_run(clients):
    runtime, run, _, model = await seed_unstarted_run(clients)
    run.task.cancel()
    await asyncio.gather(run.task, return_exceptions=True)
    async with runtime.database.sessions.begin() as db:
        await db.execute(
            update(AiRun).where(AiRun.id == run.id).values(status="completed", version=2)
        )
    await runtime.stop(run)
    async with runtime.database.sessions() as db:
        assert (await db.get(AiRun, run.id)).status == "completed"
    assert run.terminal_persisted and model.calls == []


async def test_competing_terminal_writers_adopt_the_first_committed_outcome(clients):
    runtime, run, _, model = await seed_unstarted_run(clients)
    run.task.cancel()
    await asyncio.gather(run.task, return_exceptions=True)
    peer = LiveRun(run.actor, run.conversation_id, run.data_version, run.id)
    results = await asyncio.gather(runtime.finalize(run, "cancelled"), runtime.finalize(peer, "failed"))
    assert results == [True, True]
    async with runtime.database.sessions() as db:
        status = (await db.get(AiRun, run.id)).status
    assert status in ("cancelled", "failed")
    assert run.terminal_status == peer.terminal_status == status
    assert run.id not in runtime.pending_terminal and model.calls == []


async def test_completion_compare_and_set_loses_without_emitting_output(clients, monkeypatch):
    runtime, run, c, model = await seed_unstarted_run(clients)
    await asyncio.wait_for(model.started.wait(), 3)
    original_check = runtime.check
    interrupted = False

    async def interrupt_after_last_policy_check(current):
        nonlocal interrupted
        await original_check(current)
        if model.stream_finished and not interrupted:
            interrupted = True
            async with runtime.database.sessions.begin() as db:
                await db.execute(
                    update(AiRun).where(AiRun.id == run.id).values(status="interrupted", version=2)
                )

    monkeypatch.setattr(runtime, "check", interrupt_after_last_policy_check)
    model.release.set()
    await asyncio.wait_for(run.task, 3)
    assert interrupted and c.messages == []
    assert not any(event.type == "final" for event in run.events)
    assert run.terminal_persisted and run.terminal_status == "interrupted"


async def test_output_capacity_is_reserved_while_the_completion_write_waits(clients, monkeypatch):
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.sql.dml import Update

    from app.ai.schemas import AIMessage
    from app.core.errors import DomainError

    runtime, run, c, model = await seed_unstarted_run(clients)
    await asyncio.wait_for(model.started.wait(), 3)
    # 1,900,000 bytes already resident; another197,000 alone fits below2MiB.
    c.messages = [AIMessage(id=uuid4(), actor="self", text="x" * 1000) for _ in range(1900)]
    waiting, release = asyncio.Event(), asyncio.Event()
    original_scalar = AsyncSession.scalar

    async def delayed_completion(session, statement, *args, **kwargs):
        if isinstance(statement, Update) and statement.table.name == "ai_runs":
            waiting.set()
            await release.wait()
        return await original_scalar(session, statement, *args, **kwargs)

    monkeypatch.setattr(AsyncSession, "scalar", delayed_completion)
    model.release.set()
    try:
        await asyncio.wait_for(waiting.wait(), 3)
        with pytest.raises(DomainError) as full:
            runtime.check_capacity(c.id, 197000)
        assert full.value.code == "CONTEXT_LIMIT"
    finally:
        release.set()
        await asyncio.wait_for(run.task, 3)
    assert any(event.type == "final" for event in run.events)
    # The reservation is released after the output itself becomes resident.
    runtime.check_capacity(c.id, 196400)


async def test_pending_input_commit_and_output_commit_share_the_global_capacity(clients, monkeypatch):
    import json

    from sqlalchemy.ext.asyncio import AsyncSession, AsyncSessionTransaction
    from sqlalchemy.sql.dml import Update

    from app.ai.schemas import AIMessage

    runtime, run, c, model = await seed_unstarted_run(clients)
    await asyncio.wait_for(model.started.wait(), 3)
    model.responses = [[message_output(json.dumps({"text": "🙂" * 500, "cards": []}))]]
    other, uid = clients[1][1]
    enabled = await other.put(
        "/api/v1/consents/AI",
        json={"enabled": True, "expectedVersion": 1, "policyVersion": "v1"},
        headers=key(),
    )
    assert enabled.status_code == 200
    conversation = await other.post("/api/v1/ai/conversations", json={"botId": "may"}, headers=key())
    assert conversation.status_code == 201
    cid = UUID(conversation.json()["conversationId"])
    # Fill serialized history to64MiB-5,500. Each individual admission fits;
    # 2KB user text plus4KB output copies cannot both fit. No provider I/O.
    full = AIMessage(id=uuid4(), actor="self", text="x" * 2_000_000)
    for _ in range(33):
        runtime.store.create(str(uuid4()), str(uuid4()), "may").messages = [full]
    runtime.store.create(str(uuid4()), str(uuid4()), "may").messages = [
        AIMessage(id=uuid4(), actor="self", text="x" * 1_103_364)
    ]
    input_waiting, input_release = asyncio.Event(), asyncio.Event()
    output_waiting, output_release = asyncio.Event(), asyncio.Event()
    original_flush, original_exit, original_scalar = (
        AsyncSession.flush, AsyncSessionTransaction.__aexit__, AsyncSession.scalar
    )

    async def mark_input(session, *args, **kwargs):
        if any(isinstance(item, AiRun) and item.user_id == uid for item in session.new):
            session.info["hold_input_commit"] = True
        return await original_flush(session, *args, **kwargs)

    async def wait_input_commit(transaction, *args):
        if transaction.session.info.pop("hold_input_commit", False):
            input_waiting.set()
            await input_release.wait()
        return await original_exit(transaction, *args)

    async def wait_output_commit(session, statement, *args, **kwargs):
        if isinstance(statement, Update) and statement.table.name == "ai_runs" and (
            statement.compile().params.get("status") == "completed"
        ):
            output_waiting.set()
            await output_release.wait()
        return await original_scalar(session, statement, *args, **kwargs)

    monkeypatch.setattr(AsyncSession, "flush", mark_input)
    monkeypatch.setattr(AsyncSessionTransaction, "__aexit__", wait_input_commit)
    monkeypatch.setattr(AsyncSession, "scalar", wait_output_commit)
    pending = asyncio.create_task(other.post(
        f"/api/v1/ai/conversations/{cid}/messages",
        json={"text": "🙂" * 500, "clientMessageId": str(uuid4()), "expectedConversationVersion": 1},
        headers=key(),
    ))
    watch_output = asyncio.create_task(output_waiting.wait())
    try:
        await asyncio.wait_for(input_waiting.wait(), 3)
        model.release.set()
        done, _ = await asyncio.wait((run.task, watch_output), timeout=3, return_when=asyncio.FIRST_COMPLETED)
        assert done
        input_release.set()
        assert (await asyncio.wait_for(pending, 3)).status_code == 202
    finally:
        input_release.set()
        output_release.set()
        watch_output.cancel()
        await asyncio.gather(watch_output, return_exceptions=True)
        await asyncio.wait_for(asyncio.gather(pending, run.task), 3)
    assert not any(event.type == "final" for event in run.events)
    assert c.messages == []
    runtime.check_capacity(c.id, 0)
