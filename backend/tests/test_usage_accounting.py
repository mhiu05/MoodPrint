from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.ai.usage import UsageEvent
from app.infrastructure.database.models import AiRun, now

pytestmark = pytest.mark.postgres


async def test_accounting_snapshots_are_idempotent_and_fenced_by_worker(clients):
    from app.ai.accounting import UsageSnapshot, persist_snapshot, reserve_accounting
    from app.infrastructure.database.models import AiUsage

    app, actors = clients
    uid, run_id, worker = actors[0][1], uuid4(), uuid4()
    async with app.state.database.sessions.begin() as db:
        db.add(AiRun(id=run_id, user_id=uid, conversation_id=uuid4(), bot_id="may"))
        await db.flush()
        await reserve_accounting(db, run_id, uid, worker, "gpt-6-luna", "legacy-v1")
    snapshot = UsageSnapshot()
    snapshot.observe(UsageEvent(kind="request_started"))
    snapshot.observe(UsageEvent(kind="response_received", input_tokens=100, cached_input_tokens=40, output_tokens=20))
    for _ in range(2):
        async with app.state.database.sessions.begin() as db:
            assert await persist_snapshot(db, run_id, worker, snapshot, terminal=True)
    async with app.state.database.sessions.begin() as db:
        assert not await persist_snapshot(db, run_id, uuid4(), snapshot, terminal=True)
        row = await db.get(AiUsage, run_id)
        assert (row.requests_started, row.responses_received, row.input_tokens, row.cached_input_tokens, row.output_tokens) == (1, 1, 100, 40, 20)
        assert row.estimated_nano_usd == 16_400
        assert row.state == "settled"


async def test_cancelled_request_retains_unknown_usage_and_expired_worker_cannot_settle(clients):
    from app.ai.accounting import UsageSnapshot, persist_snapshot, reserve_accounting
    from app.infrastructure.database.models import AiUsage

    app, actors = clients
    uid, run_id, worker = actors[0][1], uuid4(), uuid4()
    async with app.state.database.sessions.begin() as db:
        db.add(AiRun(id=run_id, user_id=uid, conversation_id=uuid4(), bot_id="may"))
        await db.flush()
        await reserve_accounting(db, run_id, uid, worker, "gpt-6-luna", "legacy-v1")
    snapshot = UsageSnapshot()
    snapshot.observe(UsageEvent(kind="request_started"))
    async with app.state.database.sessions.begin() as db:
        assert await persist_snapshot(db, run_id, worker, snapshot, terminal=True)
    async with app.state.database.sessions.begin() as db:
        row = await db.get(AiUsage, run_id)
        assert row.state == "uncertain" and row.requests_started == 1
        row.lease_until = now() - timedelta(seconds=1)
    snapshot.observe(UsageEvent(kind="response_received", input_tokens=10, output_tokens=5))
    async with app.state.database.sessions.begin() as db:
        assert not await persist_snapshot(db, run_id, worker, snapshot, terminal=True)
        assert (await db.scalar(select(AiUsage.state).where(AiUsage.run_id == run_id))) == "uncertain"


async def test_recovery_preserves_live_worker_and_marks_only_expired_usage_unknown(clients):
    from app.ai.accounting import (
        UsageSnapshot,
        persist_snapshot,
        recover_expired,
        reserve_accounting,
    )
    from app.infrastructure.database.models import AiUsage

    app, actors = clients
    uid, worker = actors[0][1], uuid4()
    active, expired = uuid4(), uuid4()
    async with app.state.database.sessions.begin() as db:
        for run_id in (active, expired):
            db.add(AiRun(id=run_id, user_id=uid, conversation_id=uuid4(), bot_id="may"))
        await db.flush()
        for run_id in (active, expired):
            await reserve_accounting(db, run_id, uid, worker, "gpt-6-luna", "legacy-v1")
            snapshot = UsageSnapshot()
            snapshot.observe(UsageEvent(kind="request_started"))
            await persist_snapshot(db, run_id, worker, snapshot)
        (await db.get(AiUsage, expired)).lease_until = now() - timedelta(seconds=1)
    async with app.state.database.sessions.begin() as db:
        await recover_expired(db)
    async with app.state.database.sessions() as db:
        assert (await db.get(AiRun, active)).status == "running"
        assert (await db.get(AiRun, expired)).status == "interrupted"
        assert (await db.get(AiUsage, expired)).state == "uncertain"


async def test_runtime_records_request_before_model_and_cancellation_has_no_zero_cost_refund(clients):
    import asyncio
    from uuid import UUID

    from app.infrastructure.database.models import AiUsage
    from tests.fakes import ScriptedModel, message_output

    app, actors = clients
    client = actors[0][0]
    app.state.settings.ai_accounting_enabled = True
    model = ScriptedModel([[message_output('{"text":"late","cards":[]}')]], hold=True)
    app.state.ai.model_override = model
    await client.put("/api/v1/consents/AI", json={"enabled": True, "expectedVersion": 1, "policyVersion": "v1"}, headers={"Idempotency-Key": str(uuid4())})
    conversation = (await client.post("/api/v1/ai/conversations", json={"botId": "may"}, headers={"Idempotency-Key": str(uuid4())})).json()
    response = await client.post(f"/api/v1/ai/conversations/{conversation['conversationId']}/messages", json={"text": "Synthetic", "clientMessageId": str(uuid4()), "expectedConversationVersion": 1}, headers={"Idempotency-Key": str(uuid4())})
    assert response.status_code == 202
    run_id = UUID(response.json()["runId"])
    await asyncio.wait_for(model.started.wait(), 3)
    async with app.state.database.sessions() as db:
        assert (await db.get(AiUsage, run_id)).requests_started == 1
    await app.state.ai.stop(app.state.ai.runs[run_id])
    async with app.state.database.sessions() as db:
        row = await db.get(AiUsage, run_id)
        assert row.state == "uncertain" and row.responses_received == 0
        assert (await db.get(AiRun, run_id)).status == "cancelled"


async def test_usage_retention_continues_when_capture_is_disabled(clients):
    from app.ai.accounting import reserve_accounting
    from app.infrastructure.database.models import AiUsage
    from app.jobs.retention import purge_expired

    app, actors = clients
    assert not app.state.settings.ai_accounting_enabled
    run_id = uuid4()
    async with app.state.database.sessions.begin() as db:
        db.add(AiRun(id=run_id, user_id=actors[0][1], conversation_id=uuid4(), bot_id="may"))
        await db.flush()
        await reserve_accounting(db, run_id, actors[0][1], uuid4(), "gpt-6-luna", "legacy-v1")
        row = await db.get(AiUsage, run_id)
        row.created_at = now() - timedelta(days=91)
        row.state = "uncertain"
    await purge_expired(app)
    async with app.state.database.sessions() as db:
        assert await db.get(AiUsage, run_id) is None
