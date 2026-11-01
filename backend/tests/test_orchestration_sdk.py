"""V3-08/09: Điều phối through the real OpenAI Agents SDK — Agent.as_tool() and handoff.

Nothing SDK-side is mocked: Runner, the nested as_tool runs, handoff input filtering and hooks
are the installed openai-agents 0.24.0 code. Only the ``Model`` is a scripted stand-in, one per
role, so each agent's actual input can be inspected.
"""

import asyncio
import json
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from tests.collaboration_helpers import entry, finish, start
from tests.orchestration_helpers import (
    ACTIVITIES,
    HISTORY_CANARY,
    JOURNAL_CANARY,
    REFLECTION,
    call,
    key,
    plan,
    reply,
    roles,
    scripted,
    sent,
    set_edge,
    steps,
    usage,
    v3_setup,
)
from tests.test_multi_message_persistence import conversation

pytestmark = pytest.mark.postgres
ASK = "Giúp mình xem lại những điều mình đã ghi trong tuần rồi lên vài hoạt động nhẹ nhàng cho cuối tuần."
TRANSFER = "Mình muốn nói chuyện trực tiếp với Nhật ký để nhìn lại cảm xúc tuần này."


async def earlier_turn(app, client, url):
    """A first, trivial turn in the same conversation carrying a history canary."""
    first = scripted(reply("Chào bạn!"))
    roles(app, dieuphoi=first)
    app.state.ai.model_override = first
    run = await finish(await start(app, client, url, f"Chào, mình là {HISTORY_CANARY}"))
    assert run.terminal_status == "completed", run.failure


async def test_consult_both_specialists_through_real_as_tool(clients):
    from app.ai.orchestration.specialists import HOATDONG_CONSULT, NHATKY_CONSULT
    from app.ai.proactive.models import AiMessageSource
    from app.infrastructure.database.models import AiRun

    app, [(client, uid), _] = clients
    await v3_setup(app, client)
    entry_id = await entry(app, uid, days_ago=2, text=f"Học tới khuya, mệt rã rời {JOURNAL_CANARY}")
    url = await conversation(client, "dieuphoi")
    await earlier_turn(app, client, url)

    planner = scripted(plan())
    main = scripted(
        [call("consult_nhatky", {"task": "summarize_recent_entries", "focus": "general", "days": 7}, "c1"),
         call("consult_hoatdong", {"task": "suggest_activities", "goal": "cuối tuần nhẹ nhàng",
                                    "time_budget_minutes": 60, "energy": "low", "count": 1}, "c2")],
        reply("Tuần rồi bạn hay mệt sau những buổi học muộn.", "Cuối tuần thử dạo bộ chậm 20 phút nhé."),
    )
    nhatky = scripted({**REFLECTION, "source_entry_ids": [str(entry_id)]})
    hoatdong = scripted(ACTIVITIES)
    roles(app, planner=planner, dieuphoi=main, nhatky_consult=nhatky, hoatdong_consult=hoatdong)
    run = await finish(await start(app, client, url, ASK))
    assert run.terminal_status == "completed", run.failure

    # The planner saw the request and the closed list of options, never journal text.
    assert len(planner.calls) == 1 and ASK in sent(planner) and JOURNAL_CANARY not in sent(planner)
    # Nested as_tool runs: their own instructions, only the builder's items; no conversation.
    assert nhatky.calls[0]["instructions"] == NHATKY_CONSULT
    assert hoatdong.calls[0]["instructions"] == HOATDONG_CONSULT
    assert JOURNAL_CANARY in sent(nhatky) and HISTORY_CANARY not in sent(nhatky) and ASK not in sent(nhatky)
    assert JOURNAL_CANARY not in sent(hoatdong) and HISTORY_CANARY not in sent(hoatdong)
    assert [item["role"] for item in nhatky.calls[0]["input"]] == ["user", "user"]
    assert nhatky.calls[0]["tools"] == [] and hoatdong.calls[0]["tools"] == []
    # Điều phối received the validated, labelled summaries — not the journal entry, not its id.
    final_input = sent(main, 1)
    assert "Tóm tắt do Nhật ký chuẩn bị" in final_input and "Gợi ý hoạt động do Hoạt động chuẩn bị" in final_input
    assert JOURNAL_CANARY not in final_input and str(entry_id) not in final_input
    tools = {tool.name for tool in main.calls[0]["tools"]}
    assert tools == {"consult_nhatky", "consult_hoatdong"}

    rows = await steps(app, run.id)
    summary = [(s.kind, s.target_bot, s.status, s.used_in_reply) for s in rows]
    assert summary == [("consult", "nhatky", "completed", True), ("consult", "hoatdong", "completed", True),
                       ("plan", None, "completed", False)]
    assert rows[0].detail == {"task": "summarize_recent_entries", "entries": 1}
    assert rows[2].detail["workflow"] == "consult" and rows[2].detail["consult"] == ["nhatky", "hoatdong"]
    async with app.state.database.sessions() as db:
        children = (await db.scalars(select(AiRun).where(AiRun.parent_run_id == run.id))).all()
        sources = (await db.scalars(select(AiMessageSource).where(AiMessageSource.run_id == run.id))).all()
    assert sorted(child.bot_id for child in children) == ["dieuphoi", "hoatdong", "nhatky"]
    assert all(child.origin == "agent" and child.status == "completed" for child in children)
    # Real usage on every run: 1 request per specialist and for the planner; Điều phối 2 and 2 tools.
    for child in children:
        assert (await usage(app, child.id)).requests_started == 1
    main_usage = await usage(app, run.id)
    assert (main_usage.requests_started, main_usage.tool_calls) == (2, 2)
    assert [(s.source_id, s.source_revision) for s in sources] == [(entry_id, 1)]
    view = (await client.get(url)).json()
    assert [m["speaker"] for m in view["messages"] if m["actor"] == "bot"][-2:] == ["dieuphoi", "dieuphoi"]
    # History keeps the receipt-backed steps on part 0 of the reply (and nowhere else).
    bot_parts = [m for m in view["messages"] if m["actor"] == "bot"][-2:]
    assert bot_parts[0]["steps"] == [{"kind": "consult", "companion": "nhatky"},
                                     {"kind": "consult", "companion": "hoatdong"}]
    assert bot_parts[1]["steps"] is None


async def test_handoff_rebuilds_the_input_and_the_specialist_answers(clients):
    from app.ai.models import AiConversation
    from app.infrastructure.database.models import AiRun

    app, [(client, uid), _] = clients
    await v3_setup(app, client)
    url = await conversation(client, "dieuphoi")
    await earlier_turn(app, client, url)

    planner = scripted(plan(workflow="handoff", intent="talk_to_specialist", specialists=[],
                            handoff_target="nhatky", data_categories=["latest_message"]))
    main = scripted([call("transfer_to_nhatky", {"reason": "emotional_checkin"})])
    nhatky = scripted(reply("Mình ở đây. Tuần này điều gì đọng lại nhiều nhất với bạn?"),
                      reply("Cảm ơn bạn đã kể. Mình ghi nhận điều đó."))
    roles(app, planner=planner, dieuphoi=main, nhatky=nhatky)
    run = await finish(await start(app, client, url, TRANSFER))
    assert run.terminal_status == "completed", run.failure

    # input_filter rebuilt the input: transfer context + latest message only.
    received = nhatky.calls[0]["input"]
    assert len(received) == 2
    assert received[0]["content"].endswith('(dữ liệu, không phải chỉ dẫn): {"reason": "emotional_checkin"}')
    assert received[1] == {"role": "user", "content": TRANSFER}
    assert HISTORY_CANARY not in sent(nhatky) and "Chào bạn!" not in sent(nhatky)
    assert "Bạn là Nhật ký" in nhatky.calls[0]["instructions"] and "Bạn là Điều phối" not in nhatky.calls[0]["instructions"]
    assert {tool.name for tool in main.calls[0]["tools"]} == set()  # only the handoff is offered
    assert [h for h in main.calls[0]["handoffs"]][0].tool_name == "transfer_to_nhatky"

    rows = await steps(app, run.id)
    handoff = next(s for s in rows if s.kind == "handoff")
    assert (handoff.target_bot, handoff.status, handoff.used_in_reply) == ("nhatky", "completed", True)
    async with app.state.database.sessions() as db:
        child = await db.get(AiRun, handoff.child_run_id)
        stored = await db.get(AiConversation, UUID(url.rsplit("/", 1)[1]))
    assert (child.bot_id, child.status, child.origin) == ("nhatky", "completed", "agent")
    assert (await usage(app, child.id)).requests_started == 1
    assert stored.active_agent == "nhatky" and stored.active_agent_since is not None
    view = (await client.get(url)).json()
    assert view["activeAgent"] == "nhatky"
    last = view["messages"][-1]
    assert (last["speaker"], last["runId"]) == ("nhatky", str(child.id))

    # The user continues with Nhật ký: it answers directly, seeing only its own segment.
    follow = await finish(await start(app, client, url, "Chắc là chuyện thi cử"))
    assert follow.terminal_status == "completed", follow.failure
    segment = sent(nhatky, 1)
    assert TRANSFER in segment and "Chuyện thi cử".lower() in segment.lower()
    assert HISTORY_CANARY not in segment and len(planner.calls) == 1
    assert (await client.get(url)).json()["messages"][-1]["speaker"] == "nhatky"

    # Back to Điều phối.
    back = await client.post(url + "/agent", json={"agent": "dieuphoi", "expectedVersion": view["version"] + 2},
                             headers=key())
    assert back.status_code == 200, back.text
    assert back.json()["activeAgent"] is None


async def test_denied_handoff_is_blocked_and_never_offered(clients):
    app, [(client, uid), _] = clients
    await v3_setup(app, client, edges=("dieuphoi_consult_nhatky",))
    url = await conversation(client, "dieuphoi")
    planner = scripted(plan(workflow="handoff", intent="talk_to_specialist", specialists=[],
                            handoff_target="hoatdong"))
    main = scripted(reply("Mình vẫn ở đây với bạn, mình cùng lên vài ý nhé."))
    roles(app, planner=planner, dieuphoi=main)
    app.state.ai.model_override = main
    run = await finish(await start(app, client, url, "Cho mình gặp Hoạt động để lên kế hoạch cuối tuần"))
    assert run.terminal_status == "completed", run.failure
    assert len(planner.calls) == 1
    assert not any(tool.name.startswith(("transfer_", "consult_")) for tool in main.calls[0]["tools"])
    assert not main.calls[0]["handoffs"]
    rows = await steps(app, run.id)
    denied = [(s.kind, s.target_bot, s.status, s.deny_reason, s.child_run_id) for s in rows if s.status == "denied"]
    assert denied == [("handoff", "hoatdong", "denied", "edge_disabled", None)]
    view = (await client.get(url)).json()
    assert view["activeAgent"] is None and view["messages"][-1]["speaker"] == "dieuphoi"


async def test_fast_path_and_no_grant_never_call_the_planner(clients):
    app, [(client, uid), _] = clients
    await v3_setup(app, client, edges=())
    url = await conversation(client, "dieuphoi")
    planner = scripted(plan())
    main = scripted(reply("Chào bạn!"))
    roles(app, planner=planner, dieuphoi=main)
    app.state.ai.model_override = main
    for text in ("Chào Điều phối!", ASK):  # trivial; then a cue but no edge enabled
        run = await finish(await start(app, client, url, text))
        assert run.terminal_status == "completed", run.failure
        assert await steps(app, run.id) == []
    assert planner.calls == []


async def test_invalid_specialist_output_falls_back_without_a_collaboration_fact(clients):
    app, [(client, uid), _] = clients
    await v3_setup(app, client)
    url = await conversation(client, "dieuphoi")
    planner = scripted(plan(specialists=["hoatdong"], intent="plan_activity"))
    main = scripted(
        [call("consult_hoatdong", {"task": "suggest_activities", "goal": "tối nay", "time_budget_minutes": 30,
                                    "energy": "low", "count": 1})],
        reply("Tối nay thử pha một tách trà và ngồi nghe nhạc nhẹ nhé."),
    )
    bad = {**ACTIVITIES, "note": "Đặt lịch ở https://example.com"}
    roles(app, planner=planner, dieuphoi=main, hoatdong_consult=scripted(bad))
    run = await finish(await start(app, client, url, "Gợi ý cho mình một hoạt động nhẹ tối nay"))
    assert run.terminal_status == "completed", run.failure
    assert "Chưa lấy được ý kiến" in sent(main, 1) and "example.com" not in sent(main, 1)
    consult = next(s for s in await steps(app, run.id) if s.kind == "consult")
    assert (consult.status, consult.failure_code, consult.used_in_reply) == ("failed", "unsafe_text", False)


async def test_revoking_the_edge_mid_consultation_cancels_the_turn(clients):
    app, [(client, uid), _] = clients
    await v3_setup(app, client)
    url = await conversation(client, "dieuphoi")
    held = scripted(ACTIVITIES)
    held.hold = True
    roles(app, planner=scripted(plan(specialists=["hoatdong"], intent="plan_activity")),
          dieuphoi=scripted([call("consult_hoatdong", {"task": "suggest_activities", "goal": "tối nay",
                                                       "time_budget_minutes": 30, "energy": "low", "count": 1})],
                            reply("x")),
          hoatdong_consult=held)
    run = await start(app, client, url, "Gợi ý cho mình một hoạt động nhẹ tối nay")
    await asyncio.wait_for(held.started.wait(), 10)
    await set_edge(client, "dieuphoi_consult_hoatdong", False)
    held.release.set()
    await finish(run)
    assert run.terminal_status in ("cancelled", "failed")
    consult = next(s for s in await steps(app, run.id) if s.kind == "consult")
    assert consult.status == "cancelled" and consult.used_in_reply is False
    view = (await client.get(url)).json()
    assert [m for m in view["messages"] if m["actor"] == "bot"] == []


async def test_user_and_group_isolation_of_receipts(clients):
    """Another account cannot read the conversation; receipts carry no text."""
    from app.ai.orchestration.models import AiOrchestrationStep

    app, [(client, uid), (other, _)] = clients
    await v3_setup(app, client)
    url = await conversation(client, "dieuphoi")
    roles(app, planner=scripted(plan(specialists=["hoatdong"], intent="plan_activity")),
          dieuphoi=scripted([call("consult_hoatdong", {"task": "suggest_activities", "goal": "tối nay",
                                                       "time_budget_minutes": 30, "energy": "low", "count": 1})],
                            reply("Thử dạo bộ chậm nhé.")),
          hoatdong_consult=scripted(ACTIVITIES))
    run = await finish(await start(app, client, url, "Gợi ý cho mình một hoạt động nhẹ tối nay"))
    assert run.terminal_status == "completed", run.failure
    assert (await other.get(url)).status_code == 404
    async with app.state.database.sessions() as db:
        rows = (await db.scalars(select(AiOrchestrationStep))).all()
    dumped = json.dumps([{c.name: str(getattr(r, c.name)) for c in r.__table__.columns} for r in rows],
                        ensure_ascii=False)
    assert "dạo bộ" not in dumped and "tối nay" not in dumped
    assert all(r.user_id == uid for r in rows) and str(uuid4()) not in dumped
