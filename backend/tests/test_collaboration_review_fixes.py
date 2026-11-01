"""Regressions for the independent adversarial review of Phase 2 (findings 1, 2, 3, 6, open-failure)."""

import asyncio

import pytest
from sqlalchemy import update

from app.jobs import proactive as worker
from tests.collaboration_helpers import (
    HABIT,
    energy,
    entry,
    finish,
    primary,
    receipts,
    setup,
    specialist_model,
    start,
)
from tests.test_collaboration_proactive import opt_in, rure_model
from tests.test_multi_message_persistence import conversation
from tests.test_proactive_executor import due_schedule, only_job, ready

pytestmark = pytest.mark.postgres


async def test_r1_respects_a_refusal_to_read_the_journal_in_the_same_message(clients):
    """Finding 1 (High): an in-turn journal refusal must also stop the energy edge."""
    app, [(client, uid), _] = clients
    await setup(app, client)
    await entry(app, uid)
    spec = specialist_model(energy([]))
    app.state.ai.specialist_model_override = spec
    url = await conversation(client, "rure")
    text = "Gợi ý gì nhẹ nhàng hợp với mình nhưng đừng đọc nhật ký của mình nhé"
    run = await finish(await start(app, client, url, text, model=primary("Thử trò quan sát nhé.")))
    assert run.terminal_status == "completed"
    assert spec.calls == [] and await receipts(app) == []


async def test_r2_survives_an_unrelated_data_change_during_the_consultation(clients):
    """Finding 2 (Medium): logging a mood (data_version += 1) must not cancel the check-in."""
    from app.infrastructure.database.models import User

    app, [(client, uid), _] = clients
    entry_id = await entry(app, uid)
    ready(app, rure_model())
    await opt_in(app, uid)
    spec = specialist_model(energy([entry_id]), hold=True)
    app.state.ai.specialist_model_override = spec
    await due_schedule(app, uid, bot="rure", journal=True)
    tick = asyncio.create_task(worker.proactive_tick(app.state.ai))
    await asyncio.wait_for(spec.started.wait(), 10)
    async with app.state.database.sessions.begin() as db:
        await db.execute(update(User).where(User.id == uid).values(data_version=User.data_version + 1))
    spec.release.set()
    await asyncio.wait_for(tick, 20)
    job = await only_job(app, uid)
    assert job.status == "delivered"
    [receipt] = await receipts(app, job.run_id)
    assert receipt.status == "completed" and receipt.used_in_reply


async def test_retention_closes_consultations_orphaned_by_a_finished_primary(clients):
    """Finding 3 (Low-Medium): a receipt never stays 'authorized' after its primary ended."""
    from datetime import timedelta
    from uuid import uuid4

    from app.ai.collaboration.models import AiCollaboration
    from app.infrastructure.database.models import AiRun, now
    from app.jobs.retention import purge_expired

    app, [(_client, uid), _] = clients
    async with app.state.database.sessions.begin() as db:
        primary_run = AiRun(user_id=uid, conversation_id=uuid4(), bot_id="may", status="interrupted")
        db.add(primary_run)
        await db.flush()
        child = AiRun(user_id=uid, conversation_id=None, bot_id="nhip", status="running", origin="collaboration",
                      parent_run_id=primary_run.id)
        db.add(child)
        await db.flush()
        receipt = AiCollaboration(
            user_id=uid, primary_run_id=primary_run.id, specialist_run_id=child.id, edge="nhip_habit_for_may",
            rule_id="R3", requester_bot="may", specialist_bot="nhip", status="authorized", permission_version=1,
            data_version=1, input_schema="tiny-habit-in-v1", input_digest="a" * 64,
            started_at=now() - timedelta(minutes=10),
        )
        db.add(receipt)
    await purge_expired(app)
    async with app.state.database.sessions() as db:
        row = await db.get(AiCollaboration, receipt.id)
        assert (row.status, row.failure_code) == ("cancelled", "interrupted")
        assert (await db.get(AiRun, child.id)).status == "interrupted"


async def test_an_unexpected_error_while_opening_falls_back_to_a_single_reply(clients, monkeypatch):
    app, [(client, _), _] = clients
    await setup(app, client)
    spec = specialist_model(HABIT)
    app.state.ai.specialist_model_override = spec

    async def broken(*args, **kwargs):
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(app.state.ai.coordinator, "open", broken)
    url = await conversation(client, "may")
    run = await finish(await start(app, client, url, "Mình mất ngủ", model=primary("Thương ghê.")))
    assert run.terminal_status == "completed" and spec.calls == []


async def test_turns_without_an_enabled_edge_never_take_the_global_lock(clients, monkeypatch):
    """Finding 6 (Low): a rule match for a user who never opted in stays cheap."""
    from sqlalchemy.ext.asyncio import AsyncSession

    app, [(client, _), _] = clients
    await setup(app, client, edges=())
    seen: list[str] = []
    original = AsyncSession.execute

    async def spy(self, statement, *args, **kwargs):
        seen.append(str(statement))
        return await original(self, statement, *args, **kwargs)

    url = await conversation(client, "may")
    monkeypatch.setattr(AsyncSession, "execute", spy)
    run = await finish(await start(app, client, url, "Mình mất ngủ", model=primary("Thương ghê.")))
    monkeypatch.undo()
    assert run.terminal_status == "completed"
    # admission() takes the lock once at send; the coordinator must not take it again.
    assert sum("pg_advisory_xact_lock(664201" in s for s in seen) <= 1


def test_r2_line_does_not_claim_a_gentle_activity_for_every_energy_level():
    """Finding 4 (Low): the R2 template is true for low, medium and high energy."""
    from app.ai.collaboration.policy import summary_for

    assert "nhẹ nhàng" not in summary_for("nhip_energy_for_rure", "R2")
