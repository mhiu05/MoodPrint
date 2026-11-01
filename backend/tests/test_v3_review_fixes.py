"""Regression tests for the independent adversarial review of V3 (H1, M1–M4, L2, L5, L6)."""

import asyncio
import json
from datetime import timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from tests.collaboration_helpers import entry, finish, start
from tests.group_helpers import create_group, groups_setup, say
from tests.orchestration_helpers import (
    ACTIVITIES,
    JOURNAL_CANARY,
    REFLECTION,
    call,
    key,
    plan,
    reply,
    roles,
    scripted,
    sent,
    steps,
    v3_setup,
)
from tests.test_multi_message_persistence import conversation

pytestmark = pytest.mark.postgres
ASK = "Giúp mình xem lại những điều mình đã ghi trong tuần rồi lên vài hoạt động nhẹ nhàng cho cuối tuần."


def test_h1_specialist_parameters_are_closed_values():
    from app.ai.orchestration.specialists import ConsultNhatKyInput, HandoffInput

    with pytest.raises(ValidationError):
        ConsultNhatKyInput.model_validate({"task": "find_patterns", "focus": "bạn khóc mỗi đêm vì X", "days": 7})
    ConsultNhatKyInput.model_validate({"task": "find_patterns", "focus": "sleep", "days": 7})
    with pytest.raises(ValidationError):
        HandoffInput.model_validate({"reason": "journal_reflection", "topic": "chuyện riêng"})


async def test_h1_hoatdong_is_never_asked_after_nhatky_returned(clients):
    """Sequential calls could carry journal-derived text into Hoạt động's free-text goal."""
    app, [(client, uid), _] = clients
    await v3_setup(app, client)
    await entry(app, uid, days_ago=1, text=f"Học khuya mệt {JOURNAL_CANARY}")
    url = await conversation(client, "dieuphoi")
    entries = await steps_entries(app, uid)
    main = scripted(
        [call("consult_nhatky", {"task": "summarize_recent_entries", "focus": "general", "days": 7}, "n1")],
        reply("Tuần rồi bạn hay mệt vì học khuya."),
    )
    hoatdong = scripted(ACTIVITIES)
    roles(app, planner=scripted(plan()), dieuphoi=main,
          nhatky_consult=scripted({**REFLECTION, "source_entry_ids": entries}), hoatdong_consult=hoatdong)
    run = await finish(await start(app, client, url, ASK))
    assert run.terminal_status == "completed", run.failure
    assert "consult_hoatdong" not in {tool.name for tool in main.calls[1]["tools"]}
    assert hoatdong.calls == []


async def steps_entries(app, uid):
    from app.modules.journal.models import JournalEntry

    async with app.state.database.sessions() as db:
        return [str(i) for i in (await db.scalars(select(JournalEntry.id).where(JournalEntry.user_id == uid))).all()]


async def test_h1_handoff_carries_no_free_text_and_journal_tool_needs_the_plan(clients):
    app, [(client, uid), _] = clients
    await v3_setup(app, client)
    url = await conversation(client, "dieuphoi")
    nhatky = scripted(reply("Mình ở đây."))
    roles(app, planner=scripted(plan(workflow="handoff", intent="talk_to_specialist", specialists=[],
                                     handoff_target="nhatky", data_categories=["latest_message"])),
          dieuphoi=scripted([call("transfer_to_nhatky", {"reason": "emotional_checkin"})]), nhatky=nhatky)
    run = await finish(await start(app, client, url, "Cho mình nói chuyện trực tiếp với Nhật ký"))
    assert run.terminal_status == "completed", run.failure
    transfer = nhatky.calls[0]["input"][0]["content"]
    assert json.loads(transfer.split(": ", 1)[1]) == {"reason": "emotional_checkin"}
    # The plan did not ask for journal entries: no journal tool on this handoff.
    assert nhatky.calls[0]["tools"] == []


async def test_m1_recovery_closes_v3_steps_and_child_runs(clients):
    from app.ai.models import AiTurn
    from app.ai.orchestration.models import AiOrchestrationStep
    from app.ai.persistence import recover_turns
    from app.infrastructure.database.models import AiRun, now

    app, [(client, uid), _] = clients
    async with app.state.database.sessions.begin() as db:
        primary = AiRun(user_id=uid, conversation_id=uuid4(), bot_id="dieuphoi", status="running")
        db.add(primary)
        await db.flush()
        child = AiRun(user_id=uid, conversation_id=None, bot_id="nhatky", status="running", origin="agent",
                      parent_run_id=primary.id)
        db.add(child)
        await db.flush()
        db.add(AiTurn(run_id=primary.id, user_id=uid, scope_id=uuid4(), session_id=uuid4(),
                      client_message_id=uuid4(), input_digest="a" * 64, data_version=1, worker_id=uuid4(),
                      lease_until=now() - timedelta(seconds=5)))
        db.add(AiOrchestrationStep(user_id=uid, workflow_run_id=primary.id, child_run_id=child.id, kind="handoff",
                                   requester_bot="dieuphoi", target_bot="nhatky", ordinal=0, status="authorized",
                                   data_version=1))
    async with app.state.database.sessions.begin() as db:
        await recover_turns(db)
    async with app.state.database.sessions() as db:
        step = (await db.scalars(select(AiOrchestrationStep).where(AiOrchestrationStep.workflow_run_id == primary.id))).one()
        assert (step.status, step.failure_code) == ("cancelled", "interrupted")
        assert (await db.get(AiRun, child.id)).status == "interrupted"


async def test_m2_group_selector_reads_only_the_latest_message(clients):
    app, [(client, _uid), _] = clients
    await groups_setup(app, client)
    group = await create_group(client)
    roles(app, dieuphoi=scripted(reply("Chào!"), reply("Ok nhé.")),
          selector=scripted({"speakers": [{"agent": "dieuphoi", "reason": "general"}], "summarize": False}))
    await say(app, client, group["groupId"], "@Điều phối bí mật CANARY-SEL-11")
    selector = app.state.ai.agent_model_overrides["selector"]
    await say(app, client, group["groupId"], "Tối nay mình nên làm gì?")
    assert len(selector.calls) == 1 and "CANARY-SEL-11" not in sent(selector)


async def test_m3_group_journal_tool_respects_an_in_message_refusal(clients):
    app, [(client, _uid), _] = clients
    await groups_setup(app, client)
    group = await create_group(client, ("dieuphoi", "nhatky"))
    await client.put(f"/api/v1/ai/groups/{group['groupId']}/members/nhatky/journal-access",
                     json={"enabled": True, "expectedVersion": 1}, headers=key())
    nhatky = scripted(reply("Mình chỉ nghe thôi."))
    roles(app, nhatky=nhatky)
    run, _ = await say(app, client, group["groupId"], "@Nhật ký đừng đọc nhật ký của mình, chỉ nghe thôi")
    assert run.terminal_status == "completed", run.failure
    assert nhatky.calls[0]["tools"] == []


async def test_m4_a_group_speaker_without_evidence_cannot_publish_journal_links(clients):
    app, [(client, _uid), _] = clients
    await groups_setup(app, client)
    group = await create_group(client, ("dieuphoi", "hoatdong"))
    roles(app, dieuphoi=scripted(reply(f"Xem lại [ở đây](/self/entry/{uuid4()}) nhé.")),
          hoatdong=scripted(reply("Thử dạo bộ nhé.")))
    run, _ = await say(app, client, group["groupId"], "@mọi người ơi")
    view = (await client.get(f"/api/v1/ai/groups/{group['groupId']}")).json()
    assert [(m["speaker"]) for m in view["messages"] if m["actor"] == "bot"] == ["hoatdong"]
    assert all("/self/entry/" not in m["text"] for m in view["messages"])


async def test_l2_stopping_a_turn_closes_open_receipts_at_once(clients):
    from app.ai.orchestration.models import AiOrchestrationStep

    app, [(client, _uid), _] = clients
    await groups_setup(app, client)
    group = await create_group(client)
    held = scripted(reply("…"))
    held.hold = True
    roles(app, nhatky=held, hoatdong=scripted(reply("x")), dieuphoi=scripted(reply("y")))
    run, accepted = await say(app, client, group["groupId"], "@mọi người ơi", wait=False)
    await asyncio.wait_for(held.started.wait(), 10)
    stopped = await client.post(f"/api/v1/ai/groups/{group['groupId']}/turns/{accepted['turnId']}/cancel", headers=key())
    assert stopped.status_code == 204
    async with app.state.database.sessions() as db:
        open_ = (await db.scalars(select(AiOrchestrationStep).where(
            AiOrchestrationStep.workflow_run_id == run.id, AiOrchestrationStep.status == "authorized"))).all()
    assert open_ == []
    held.release.set()
    await asyncio.wait_for(asyncio.gather(run.task, return_exceptions=True), 20)


async def test_l5_migration_keeps_an_auto_paused_schedule_paused(clients):
    from app.ai.proactive.models import AiProactiveSchedule
    from app.infrastructure.database.models import now
    from tests.test_proactive_api import BASE, enable, put_schedule

    app, [(client, uid), _] = clients
    enable(app)
    await put_schedule(client, "nhip", "morning", localTime="07:30")
    async with app.state.database.sessions.begin() as db:
        row = (await db.scalars(select(AiProactiveSchedule).where(AiProactiveSchedule.user_id == uid))).one()
        row.auto_paused_at = now()
    app.state.settings.ai_three_agent_experience_enabled = True
    moved = await client.post(f"{BASE}/schedules/nhip/morning/migrate", json={"expectedVersion": 1}, headers=key())
    assert moved.status_code == 200, moved.text
    assert moved.json()["autoPaused"] is True and moved.json()["nextDeliveryAt"] is None


async def test_l6_group_count_is_bounded_like_the_list(clients):
    from app.ai.groups.service import MAX_GROUPS
    from app.ai.models import AiConversation
    from app.ai.orchestration.models import AiGroupMember
    from app.infrastructure.database.models import now

    app, [(client, uid), _] = clients
    await groups_setup(app, client)
    async with app.state.database.sessions.begin() as db:
        for index in range(MAX_GROUPS):
            group = AiConversation(user_id=uid, bot_id="group", kind="group", title=f"G{index}",
                                   expires_at=now() + timedelta(days=5))
            db.add(group)
            await db.flush()
            db.add(AiGroupMember(conversation_id=group.id, bot_id="dieuphoi", user_id=uid))
    refused = await client.post("/api/v1/ai/groups", json={"name": "Thêm", "members": ["dieuphoi", "nhatky"]},
                                headers=key())
    assert refused.status_code == 429 and refused.json()["error"]["code"] == "GROUP_LIMIT"
