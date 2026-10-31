"""P2-05: the coordinator in chat — R1/R3/R4 end to end, fallback, revocation, minimization."""

import asyncio
import logging

import pytest
from sqlalchemy import func, select, update

from tests.collaboration_helpers import (
    ACTIVITY,
    HABIT,
    JOURNAL_CANARY,
    USER_CANARY,
    energy,
    entry,
    finish,
    key,
    primary,
    receipts,
    sent_text,
    setup,
    specialist_model,
    start,
)
from tests.conftest import add_actor
from tests.test_multi_message_persistence import conversation

pytestmark = pytest.mark.postgres
R1_TEXT = "Rủ Rê ơi gợi ý gì nhẹ nhàng hợp với mình hôm nay"
TEMPLATES = {
    "R1": "Nhịp đã gợi ý mức năng lượng phù hợp với bạn. Rủ Rê đã dựa vào đó để chọn hoạt động này.",
    "R3": "Nhịp đã gợi ý một thói quen nhỏ. Mây đã dựa vào đó để trả lời bạn.",
    "R4": "Rủ Rê đã gợi ý một hoạt động. Gương đã dựa vào đó để trả lời bạn.",
}


async def child_runs(app, parent):
    from app.infrastructure.database.models import AiRun, AiUsage

    async with app.state.database.sessions() as db:
        return (await db.execute(
            select(AiRun, AiUsage).outerjoin(AiUsage, AiUsage.run_id == AiRun.id).where(AiRun.parent_run_id == parent)
        )).all()


async def test_r1_rure_gets_only_the_energy_enum_never_the_journal(clients):
    from app.ai.models import AiTurn
    from app.ai.proactive.models import AiMessageSource

    app, [(client, uid), _] = clients
    await setup(app, client)
    entry_id = await entry(app, uid)
    spec = specialist_model(energy([entry_id]))
    app.state.ai.specialist_model_override = spec
    main = primary("Sáng nay thử một thử thách nhỏ: nhắm mắt đếm âm thanh trong 2 phút nhé.", "Kể mình nghe nhé!")
    url = await conversation(client, "rure")
    run = await finish(await start(app, client, url, R1_TEXT, model=main))
    assert run.terminal_status == "completed", run.failure
    # The specialist saw the excerpt; the primary saw only closed values.
    assert JOURNAL_CANARY in sent_text(spec)
    assert JOURNAL_CANARY not in sent_text(main)
    assert "energy=low" in main.calls[0]["instructions"] and "timeBudgetMinutes=5" in main.calls[0]["instructions"]
    assert str(entry_id) not in sent_text(main)
    [receipt] = await receipts(app, run.id)
    assert (receipt.edge, receipt.rule_id, receipt.status, receipt.used_in_reply) == (
        "nhip_energy_for_rure", "R1", "completed", True)
    assert receipt.specialist_run_id and len(receipt.input_digest) == 64 and receipt.output_digest
    [(child, usage)] = await child_runs(app, run.id)
    assert (child.origin, child.bot_id, child.status, child.conversation_id) == ("collaboration", "nhip", "completed", None)
    assert child.id == receipt.specialist_run_id
    assert (usage.requests_started, usage.responses_received, usage.tool_calls, usage.state) == (1, 1, 0, "settled")
    async with app.state.database.sessions() as db:
        sources = (await db.scalars(select(AiMessageSource).where(AiMessageSource.run_id == run.id))).all()
        turn = await db.get(AiTurn, run.id)
    assert [(s.source_id, s.source_revision) for s in sources] == [(entry_id, 1)]
    assert turn.context_policy == "journal-turn-v1"
    view = (await client.get(url)).json()
    bots = [m for m in view["messages"] if m["actor"] == "bot"]
    assert bots[0]["collaboration"] == {"kind": "nhip_energy_for_rure", "companions": ["nhip", "rure"],
                                        "summary": TEMPLATES["R1"]}
    assert bots[1]["collaboration"] is None
    assert all(m["collaboration"] is None for m in view["messages"] if m["actor"] == "self")


async def test_r3_may_receives_a_labelled_suggestion_and_never_sends_user_words(clients):
    app, [(client, _), _] = clients
    await setup(app, client)
    spec = specialist_model(HABIT)
    app.state.ai.specialist_model_override = spec
    main = primary("Mất ngủ mấy hôm liền thật mệt ghê. Tối nay thử tắt màn hình sớm hơn một chút nhé.")
    url = await conversation(client, "may")
    run = await finish(await start(app, client, url, f"Mấy hôm nay mình mất ngủ {USER_CANARY}", model=main))
    assert run.terminal_status == "completed", run.failure
    assert USER_CANARY not in sent_text(spec)
    inputs = main.calls[0]["input"]
    data = [item for item in inputs if "không phải chỉ dẫn" in str(item.get("content"))]
    assert len(data) == 1 and HABIT["habit_text"] in data[0]["content"]
    # The user's own message stays the last item the primary reads.
    assert USER_CANARY in inputs[-1]["content"]
    [receipt] = await receipts(app, run.id)
    assert (receipt.rule_id, receipt.status, receipt.used_in_reply) == ("R3", "completed", True)
    view = (await client.get(url)).json()
    assert view["messages"][-1]["collaboration"]["summary"] == TEMPLATES["R3"]


async def test_r4_guong_gets_an_activity_from_rure(clients):
    app, [(client, _), _] = clients
    await setup(app, client)
    spec = specialist_model(ACTIVITY)
    app.state.ai.specialist_model_override = spec
    url = await conversation(client, "guong")
    run = await finish(await start(app, client, url, "Mình thích vẽ, nên thử làm gì trước?",
                                   model=primary("Một bước nhỏ để bắt đầu nè.")))
    assert run.terminal_status == "completed"
    assert '"interest_tag":"drawing"' in spec.calls[0]["input"][0]["content"]
    [receipt] = await receipts(app, run.id)
    assert (receipt.edge, receipt.status, receipt.used_in_reply) == ("rure_activity_for_guong", "completed", True)
    assert (await client.get(url)).json()["messages"][-1]["collaboration"]["companions"] == ["rure", "guong"]


async def test_unmatched_turn_has_no_extra_call_and_no_receipt(clients):
    app, [(client, _), _] = clients
    await setup(app, client)
    spec = specialist_model(HABIT)
    app.state.ai.specialist_model_override = spec
    main = primary("Chào bạn!")
    url = await conversation(client, "may")
    run = await finish(await start(app, client, url, "Chào Mây", model=main))
    assert run.terminal_status == "completed"
    assert spec.calls == [] and len(main.calls) == 1
    assert await receipts(app) == []
    assert "từ Nhịp" not in main.calls[0]["instructions"]
    assert not any("không phải chỉ dẫn" in str(item.get("content")) for item in main.calls[0]["input"])


async def test_disabled_edge_means_no_call_and_no_receipt(clients):
    app, [(client, _), _] = clients
    await setup(app, client, edges=("rure_activity_for_guong",))
    spec = specialist_model(HABIT)
    app.state.ai.specialist_model_override = spec
    url = await conversation(client, "may")
    run = await finish(await start(app, client, url, "Mình mất ngủ", model=primary("Thương ghê.")))
    assert run.terminal_status == "completed" and spec.calls == [] and await receipts(app) == []


async def test_flag_off_behaves_like_phase_1(clients):
    from tests.test_ai_events_v2 import events

    app, [(client, _), _] = clients
    await setup(app, client)
    app.state.settings.ai_collaboration_enabled = False
    spec = specialist_model(HABIT)
    app.state.ai.specialist_model_override = spec
    main = primary("Thương ghê.")
    url = await conversation(client, "may")
    run = await finish(await start(app, client, url, "Mình mất ngủ", model=main))
    assert run.terminal_status == "completed" and spec.calls == [] and len(main.calls) == 1
    assert await receipts(app) == []
    assert "Nhịp" not in main.calls[0]["instructions"][-300:]
    received = events((await client.get(f"/api/v1/ai/runs/{run.id}/events?protocol=2")).text)
    assert [e["type"] for e in received] == ["progress", "final", "completed"]
    assert "collaboration" not in received[1]["data"]


async def test_specialist_timeout_falls_back_to_a_single_reply(clients):
    app, [(client, _), _] = clients
    await setup(app, client)
    app.state.settings.ai_collaboration_timeout_seconds = 0.3
    spec = specialist_model(HABIT, hold=True)
    app.state.ai.specialist_model_override = spec
    main = primary("Thương ghê, tối nay nghỉ sớm nhé.")
    url = await conversation(client, "may")
    run = await finish(await start(app, client, url, "Mình mất ngủ", model=main))
    assert run.terminal_status == "completed"
    assert "không phải chỉ dẫn" not in str(main.calls[0]["input"])
    [receipt] = await receipts(app, run.id)
    assert (receipt.status, receipt.failure_code, receipt.used_in_reply) == ("timeout", "timeout", False)
    [(child, _usage)] = await child_runs(app, run.id)
    assert child.status == "failed"
    assert all(m["collaboration"] is None for m in (await client.get(url)).json()["messages"])


@pytest.mark.parametrize("payload", [{"habit_text": "Xem https://x.vn nhé, rất hay đó!", "duration_minutes": 5,
                                      "kind": "wind_down"}, {"unexpected": True}])
async def test_invalid_specialist_output_falls_back(clients, payload):
    app, [(client, _), _] = clients
    await setup(app, client)
    app.state.ai.specialist_model_override = specialist_model(payload)
    url = await conversation(client, "may")
    run = await finish(await start(app, client, url, "Mình mất ngủ", model=primary("Thương ghê.")))
    assert run.terminal_status == "completed"
    [receipt] = await receipts(app, run.id)
    assert receipt.status == "failed" and receipt.failure_code.startswith(("invalid", "unsafe"))
    assert all(m["collaboration"] is None for m in (await client.get(url)).json()["messages"])


async def test_r1_without_recent_entries_never_calls_and_records_no_data(clients):
    app, [(client, uid), _] = clients
    await setup(app, client)
    await entry(app, uid, days_ago=3)  # outside the 2-day window
    await entry(app, uid, days_ago=1, status="draft")
    spec = specialist_model(energy([]))
    app.state.ai.specialist_model_override = spec
    url = await conversation(client, "rure")
    run = await finish(await start(app, client, url, R1_TEXT, model=primary("Thử trò đố vui nhé.")))
    assert run.terminal_status == "completed" and spec.calls == []
    [receipt] = await receipts(app, run.id)
    assert (receipt.status, receipt.deny_reason, receipt.specialist_run_id) == ("denied", "no_data", None)


async def test_r1_with_journal_context_off_records_consent_denial(clients):
    from tests.test_proactive_api import settings_body

    app, [(client, uid), _] = clients
    await setup(app, client)
    await entry(app, uid)
    current = (await client.get("/api/v1/ai/proactive")).json()["settings"]["version"]
    await client.put("/api/v1/ai/proactive/settings", headers=key(),
                     json=settings_body(journalContextEnabled=False, expectedVersion=current))
    spec = specialist_model(energy([]))
    app.state.ai.specialist_model_override = spec
    url = await conversation(client, "rure")
    run = await finish(await start(app, client, url, R1_TEXT, model=primary("Thử trò đố vui nhé.")))
    assert run.terminal_status == "completed" and spec.calls == []
    assert [(r.status, r.deny_reason) for r in await receipts(app, run.id)] == [("denied", "journal_consent_off")]


async def test_daily_cap_and_time_budget_deny(clients):
    app, [(client, _), _] = clients
    await setup(app, client)
    app.state.settings.ai_collaboration_daily_cap = 1
    app.state.ai.specialist_model_override = specialist_model(HABIT)
    url = await conversation(client, "may")
    first = await finish(await start(app, client, url, "Mình mất ngủ", model=primary("Một.")))
    second = await finish(await start(app, client, url, "Vẫn mất ngủ", model=primary("Hai.")))
    assert [r.status for r in await receipts(app, first.id)] == ["completed"]
    assert [(r.status, r.deny_reason) for r in await receipts(app, second.id)] == [("denied", "daily_cap")]
    app.state.settings.ai_collaboration_daily_cap = 10
    app.state.settings.ai_timeout_seconds = 20  # 20 - 8 < 15 s left for the primary
    third = await finish(await start(app, client, url, "Mình căng thẳng quá", model=primary("Ba.")))
    assert [(r.status, r.deny_reason) for r in await receipts(app, third.id)] == [("denied", "time_budget")]


async def test_distress_message_never_consults_and_leaves_no_trace(clients):
    app, [(client, _), _] = clients
    await setup(app, client)
    spec = specialist_model(HABIT)
    app.state.ai.specialist_model_override = spec
    url = await conversation(client, "may")
    run = await finish(await start(app, client, url, "Mất ngủ mấy hôm, mình không muốn sống nữa",
                                   model=primary("Mình ở đây với bạn.")))
    assert run.terminal_status == "completed" and spec.calls == [] and await receipts(app) == []


async def test_revoking_the_edge_during_the_specialist_cancels_the_turn(clients):
    from app.ai.models import AiMessageRecord

    app, [(client, _), _] = clients
    await setup(app, client)
    spec = specialist_model(HABIT, hold=True)
    app.state.ai.specialist_model_override = spec
    url = await conversation(client, "may")
    run = await start(app, client, url, "Mình mất ngủ", model=primary("Không được lưu."))
    await asyncio.wait_for(spec.started.wait(), 10)
    view = (await client.get("/api/v1/ai/sharing")).json()
    version = next(e["version"] for e in view["edges"] if e["edge"] == "nhip_habit_for_may")
    off = await client.put("/api/v1/ai/sharing/nhip_habit_for_may", headers=key(),
                           json={"enabled": False, "expectedVersion": version, "policyVersion": "sharing-v1"})
    assert off.status_code == 200
    await finish(run)
    assert run.terminal_status == "cancelled"
    [receipt] = await receipts(app, run.id)
    assert receipt.status == "cancelled" and not receipt.used_in_reply
    [(child, _usage)] = await child_runs(app, run.id)
    assert child.status == "cancelled"
    async with app.state.database.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(AiMessageRecord).where(
            AiMessageRecord.run_id == run.id, AiMessageRecord.actor == "bot")) == 0


async def test_primary_failure_after_consultation_discards_the_receipt(clients):
    from tests.fakes import ScriptedModel, message_output

    app, [(client, _), _] = clients
    await setup(app, client)
    app.state.ai.specialist_model_override = specialist_model(HABIT)
    broken = ScriptedModel([[message_output("not json")]])
    url = await conversation(client, "may")
    run = await finish(await start(app, client, url, "Mình mất ngủ", model=broken))
    assert run.terminal_status == "failed"
    [receipt] = await receipts(app, run.id)
    assert (receipt.status, receipt.used_in_reply) == ("discarded", False)


async def test_journal_edit_during_the_turn_blocks_publication(clients):
    from app.modules.journal.models import JournalEntry

    app, [(client, uid), _] = clients
    await setup(app, client)
    entry_id = await entry(app, uid)
    spec = specialist_model(energy([entry_id]), hold=True)
    app.state.ai.specialist_model_override = spec
    url = await conversation(client, "rure")
    run = await start(app, client, url, R1_TEXT, model=primary("Thử thách nhỏ nè."))
    await asyncio.wait_for(spec.started.wait(), 10)
    async with app.state.database.sessions.begin() as db:
        await db.execute(update(JournalEntry).where(JournalEntry.id == entry_id).values(version=2, text="đã sửa"))
    spec.release.set()
    await finish(run)
    assert run.terminal_status == "failed"
    [receipt] = await receipts(app, run.id)
    assert receipt.status == "discarded" and not receipt.used_in_reply


async def test_under_18_account_never_collaborates_even_with_a_stored_opt_in(clients):
    from app.ai.collaboration.models import AiSharingPermission
    from tests.test_chat_persistence import enable

    app, _ = clients
    teen, teen_id = await add_actor(app, 9, age_band="teen")
    await enable(teen)
    app.state.settings.ai_multi_message_enabled = True
    app.state.settings.ai_collaboration_enabled = True
    async with app.state.database.sessions.begin() as db:
        db.add(AiSharingPermission(user_id=teen_id, edge="nhip_habit_for_may", enabled=True))
    spec = specialist_model(HABIT)
    app.state.ai.specialist_model_override = spec
    app.state.ai.model_override = primary("x")
    url = await conversation(teen, "may")
    run = await finish(await start(app, teen, url, "Mình mất ngủ", model=primary("Thương ghê.")))
    assert run.terminal_status == "completed" and spec.calls == [] and await receipts(app) == []


async def test_temporary_chat_never_collaborates(clients):
    app, [(client, _), _] = clients
    await setup(app, client)
    spec = specialist_model(HABIT)
    app.state.ai.specialist_model_override = spec
    url = await conversation(client, "may", persistent=False)
    run = await finish(await start(app, client, url, "Mình mất ngủ", model=primary("Thương ghê.")))
    assert run.terminal_status == "completed" and spec.calls == []


async def test_logs_are_content_free(clients, caplog):
    app, [(client, uid), _] = clients
    await setup(app, client)
    entry_id = await entry(app, uid)
    app.state.ai.specialist_model_override = specialist_model(energy([entry_id]))
    url = await conversation(client, "rure")
    with caplog.at_level(logging.INFO, logger="moodprint"):
        run = await finish(await start(app, client, url, f"{R1_TEXT} {USER_CANARY}", model=primary("Ok nhé.")))
    assert run.terminal_status == "completed"
    lines = [r.getMessage() for r in caplog.records if "collaboration_state" in r.getMessage()]
    assert lines and all("edge=nhip_energy_for_rure" in line for line in lines)
    joined = "\n".join(r.getMessage() for r in caplog.records)
    for secret in (JOURNAL_CANARY, USER_CANARY, str(entry_id), str(uid)):
        assert secret not in joined


async def test_crash_recovery_closes_the_child_run_and_the_receipt(clients):
    from datetime import timedelta

    from app.ai.models import AiTurn
    from app.ai.persistence import recover_turns
    from app.infrastructure.database.models import AiRun, now

    app, [(client, _), _] = clients
    await setup(app, client)
    spec = specialist_model(HABIT, hold=True)
    app.state.ai.specialist_model_override = spec
    url = await conversation(client, "may")
    run = await start(app, client, url, "Mình mất ngủ", model=primary("x"))
    await asyncio.wait_for(spec.started.wait(), 10)
    # Simulate a worker that died: its lease expired while the specialist was running.
    async with app.state.database.sessions.begin() as db:
        await db.execute(update(AiTurn).where(AiTurn.run_id == run.id).values(lease_until=now() - timedelta(seconds=1)))
        await recover_turns(db)
    async with app.state.database.sessions() as db:
        assert (await db.get(AiRun, run.id)).status == "interrupted"
        [(child, _usage)] = await child_runs(app, run.id)
    assert child.status == "interrupted"
    [receipt] = await receipts(app, run.id)
    assert (receipt.status, receipt.failure_code) == ("cancelled", "interrupted")
    spec.release.set()
    await finish(run)
    [receipt] = await receipts(app, run.id)
    assert receipt.status == "cancelled" and not receipt.used_in_reply


async def test_distressing_journal_excerpt_is_never_forwarded_or_recorded(clients):
    app, [(client, uid), _] = clients
    await setup(app, client)
    await entry(app, uid, text="Mấy hôm nay mình không muốn sống nữa")
    spec = specialist_model(energy([]))
    app.state.ai.specialist_model_override = spec
    url = await conversation(client, "rure")
    run = await finish(await start(app, client, url, R1_TEXT, model=primary("Mình ở đây nè.")))
    assert run.terminal_status == "completed" and spec.calls == []
    assert await receipts(app) == []
