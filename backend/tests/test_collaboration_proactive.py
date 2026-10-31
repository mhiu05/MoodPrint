"""P2-06: R2 — Rủ Rê's morning check-in may consult Nhịp for an energy hint (between E2 and E3)."""

import asyncio
import json

import pytest
from sqlalchemy import select

from app.jobs import proactive as worker
from tests.collaboration_helpers import JOURNAL_CANARY, energy, entry, receipts, specialist_model
from tests.fakes import ScriptedModel, message_output
from tests.test_proactive_executor import due_schedule, only_job, proactive_messages, ready

pytestmark = pytest.mark.postgres
R2 = "Nhịp đã gợi ý một hoạt động nhẹ nhàng. Rủ Rê đã dựa vào đó để chuẩn bị thử thách hôm nay."


def rure_model(**kwargs) -> ScriptedModel:
    payload = {"messages": [{"text": "Chào buổi sáng! Thử nhắm mắt đếm xem nghe được mấy âm thanh trong 2 phút nhé.",
                             "cards": []}], "challenge_kind": "observation"}
    return ScriptedModel([[message_output(json.dumps(payload, ensure_ascii=False))]], **kwargs)


async def opt_in(app, uid, *, edge=True):
    from app.ai.collaboration.models import AiSharingPermission

    settings = app.state.settings
    settings.ai_multi_message_enabled = True
    settings.ai_collaboration_enabled = True
    settings.ai_accounting_enabled = True
    if edge:
        async with app.state.database.sessions.begin() as db:
            db.add(AiSharingPermission(user_id=uid, edge="nhip_energy_for_rure", enabled=True))


async def test_r2_morning_check_in_uses_only_the_energy_hint(clients):
    from app.ai.models import AiTurn
    from app.ai.proactive.models import AiMessageSource

    app, [(client, uid), _] = clients
    entry_id = await entry(app, uid)
    main = rure_model()
    ready(app, main)
    await opt_in(app, uid)
    spec = specialist_model(energy([entry_id]))
    app.state.ai.specialist_model_override = spec
    await due_schedule(app, uid, bot="rure", journal=True)
    await worker.proactive_tick(app.state.ai)
    job = await only_job(app, uid)
    assert job.status == "delivered"
    assert JOURNAL_CANARY in json.dumps(spec.calls[0]["input"], ensure_ascii=False)
    main_sent = main.calls[-1]["instructions"] + json.dumps(main.calls[-1]["input"], ensure_ascii=False)
    assert JOURNAL_CANARY not in main_sent and str(entry_id) not in main_sent
    assert "energy=low" in main.calls[-1]["instructions"]
    [receipt] = await receipts(app, job.run_id)
    assert (receipt.rule_id, receipt.status, receipt.used_in_reply) == ("R2", "completed", True)
    async with app.state.database.sessions() as db:
        sources = (await db.scalars(select(AiMessageSource).where(AiMessageSource.run_id == job.run_id))).all()
        turn = await db.get(AiTurn, job.run_id)
    assert [(s.source_id, s.policy.startswith("proactive-journal-v1@")) for s in sources] == [(entry_id, True)]
    assert turn.context_policy == "proactive-journal-v1"
    view = (await client.get(f"/api/v1/ai/conversations/{job.conversation_id}")).json()
    assert view["messages"][0]["collaboration"]["summary"] == R2


async def test_no_entry_yesterday_means_no_specialist_call(clients):
    app, [(_client, uid), _] = clients
    await entry(app, uid, days_ago=0)  # today is not "yesterday"
    ready(app, rure_model())
    await opt_in(app, uid)
    spec = specialist_model(energy([]))
    app.state.ai.specialist_model_override = spec
    await due_schedule(app, uid, bot="rure", journal=True)
    await worker.proactive_tick(app.state.ai)
    job = await only_job(app, uid)
    assert job.status == "delivered" and spec.calls == []
    assert [(r.status, r.deny_reason) for r in await receipts(app, job.run_id)] == [("denied", "no_data")]


async def test_edge_off_or_evening_or_other_companion_never_consults(clients):
    app, [(_client, uid), (_other, other_uid)] = clients
    await entry(app, uid)
    await entry(app, other_uid)
    ready(app, rure_model())
    await opt_in(app, uid, edge=False)
    spec = specialist_model(energy([]))
    app.state.ai.specialist_model_override = spec
    await due_schedule(app, uid, bot="rure", journal=True)
    await due_schedule(app, other_uid, bot="rure", slot="evening", journal=True)
    await worker.proactive_tick(app.state.ai)
    await worker.proactive_tick(app.state.ai)  # concurrency 1: one job per tick
    assert (await only_job(app, uid)).status == "delivered"
    assert (await only_job(app, other_uid)).status == "delivered"
    assert spec.calls == [] and await receipts(app) == []


async def test_specialist_timeout_delivers_the_plain_check_in_once(clients):
    app, [(client, uid), _] = clients
    await entry(app, uid)
    ready(app, rure_model())
    await opt_in(app, uid)
    app.state.settings.ai_collaboration_timeout_seconds = 0.3
    app.state.ai.specialist_model_override = specialist_model(energy([]), hold=True)
    await due_schedule(app, uid, bot="rure", journal=True)
    await worker.proactive_tick(app.state.ai)
    job = await only_job(app, uid)
    assert job.status == "delivered"
    assert len(await proactive_messages(app, uid)) == 1
    [receipt] = await receipts(app, job.run_id)
    assert receipt.status == "timeout"
    view = (await client.get(f"/api/v1/ai/conversations/{job.conversation_id}")).json()
    assert all(m["collaboration"] is None for m in view["messages"])


async def test_revoking_the_edge_during_the_specialist_cancels_the_job(clients):
    from app.ai.collaboration.models import AiSharingPermission
    from app.infrastructure.database.models import User

    app, [(_client, uid), _] = clients
    entry_id = await entry(app, uid)
    ready(app, rure_model())
    await opt_in(app, uid)
    spec = specialist_model(energy([entry_id]), hold=True)
    app.state.ai.specialist_model_override = spec
    await due_schedule(app, uid, bot="rure", journal=True)
    tick = asyncio.create_task(worker.proactive_tick(app.state.ai))
    await asyncio.wait_for(spec.started.wait(), 10)
    async with app.state.database.sessions.begin() as db:
        row = await db.get(AiSharingPermission, (uid, "nhip_energy_for_rure"))
        row.enabled, row.version = False, row.version + 1
        (await db.get(User, uid)).data_version += 1
    spec.release.set()
    await asyncio.wait_for(tick, 20)
    job = await only_job(app, uid)
    assert job.status == "cancelled"
    assert await proactive_messages(app, uid) == []
    [receipt] = await receipts(app)
    assert not receipt.used_in_reply and receipt.status in ("cancelled", "discarded")


async def test_entry_edited_before_publish_regenerates_from_fresh_data(clients):
    from sqlalchemy import update

    from app.modules.journal.models import JournalEntry

    app, [(_client, uid), _] = clients
    entry_id = await entry(app, uid)
    ready(app, rure_model())
    await opt_in(app, uid)
    spec = specialist_model(energy([entry_id]), hold=True)
    app.state.ai.specialist_model_override = spec
    await due_schedule(app, uid, bot="rure", journal=True)
    tick = asyncio.create_task(worker.proactive_tick(app.state.ai))
    await asyncio.wait_for(spec.started.wait(), 10)
    async with app.state.database.sessions.begin() as db:
        await db.execute(update(JournalEntry).where(JournalEntry.id == entry_id).values(version=2))
    spec.release.set()
    await asyncio.wait_for(tick, 20)
    job = await only_job(app, uid)
    assert job.status == "retry" and job.last_error == "source_changed"
    assert await proactive_messages(app, uid) == []
    assert [r.status for r in await receipts(app)] == ["discarded"]
