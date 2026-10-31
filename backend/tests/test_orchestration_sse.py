"""V3-10: SSE v2 for orchestrated turns — real steps and the real speaker, forward-only, replayable."""

import pytest

from tests.collaboration_helpers import entry, finish, start
from tests.orchestration_helpers import (
    ACTIVITIES,
    REFLECTION,
    call,
    plan,
    reply,
    roles,
    scripted,
    v3_setup,
)
from tests.test_collaboration_dto import events
from tests.test_multi_message_persistence import conversation

pytestmark = pytest.mark.postgres


async def stream(client, run_id, query=""):
    response = await client.get(f"/api/v1/ai/runs/{run_id}/events{query}")
    assert response.status_code == 200, response.text
    return events(response.text)


async def test_consult_turn_streams_each_real_step_then_the_final_with_steps(clients):
    app, [(client, uid), _] = clients
    await v3_setup(app, client)
    entry_id = await entry(app, uid, days_ago=1)
    url = await conversation(client, "dieuphoi")
    roles(app, planner=scripted(plan()),
          dieuphoi=scripted([call("consult_nhatky", {"task": "find_patterns", "focus": "tuần rồi", "days": 7}, "a"),
                             call("consult_hoatdong", {"task": "suggest_activities", "goal": "cuối tuần",
                                                        "time_budget_minutes": 60, "energy": "low", "count": 1}, "b")],
                            reply("Gộp lại: nghỉ ngơi sáng thứ bảy, dạo bộ chiều chủ nhật.")),
          nhatky_consult=scripted({**REFLECTION, "source_entry_ids": [str(entry_id)]}),
          hoatdong_consult=scripted(ACTIVITIES))
    run = await finish(await start(app, client, url, "Nhìn lại tuần rồi và lên kế hoạch cuối tuần giúp mình"))
    assert run.terminal_status == "completed", run.failure

    full = await stream(client, run.id, "?protocol=2")
    kinds = [(e["type"], e["data"].get("activity"), e["data"].get("companion")) for e in full]
    assert kinds[0] == ("progress", None, None)
    assert sorted(kinds[1:3]) == [("progress", "consulting", "hoatdong"), ("progress", "consulting", "nhatky")]
    assert [k[0] for k in kinds[3:]] == ["final", "completed"]
    final = full[3]["data"]
    assert final["speaker"] == "dieuphoi"
    assert sorted(step["companion"] for step in final["steps"]) == ["hoatdong", "nhatky"]
    assert {step["kind"] for step in final["steps"]} == {"consult"}
    # Replay from every cursor reproduces the same suffix with the same ids (no duplicates).
    for cursor in range(len(full)):
        resumed = await stream(client, run.id, f"?protocol=2&afterSeq={cursor}")
        assert resumed == full[cursor:]
    assert (await client.get(f"/api/v1/ai/runs/{run.id}/events?protocol=2&afterSeq=7")).status_code == 409
    # v1 keeps the Phase 1 shape: progress, final {text, cards}, completed — no new keys.
    v1 = await stream(client, run.id)
    assert [e["type"] for e in v1] == ["progress", "final", "completed"]
    assert set(v1[1]["data"]) == {"text", "cards"}


async def test_handoff_turn_streams_the_transfer_and_the_specialist_as_speaker(clients):
    app, [(client, uid), _] = clients
    await v3_setup(app, client)
    url = await conversation(client, "dieuphoi")
    roles(app, planner=scripted(plan(workflow="handoff", intent="talk_to_specialist", specialists=[],
                                     handoff_target="nhatky")),
          dieuphoi=scripted([call("transfer_to_nhatky", {"reason": "journal_reflection", "topic": "tuần này"})]),
          nhatky=scripted(reply("Chào bạn, mình là Nhật ký. Tuần này có điều gì bạn muốn nhìn lại không?")))
    run = await finish(await start(app, client, url, "Cho mình nói chuyện với Nhật ký nhé"))
    assert run.terminal_status == "completed", run.failure
    full = await stream(client, run.id, "?protocol=2")
    assert [(e["type"], e["data"].get("activity"), e["data"].get("companion")) for e in full] == [
        ("progress", None, None), ("progress", "transferring", "nhatky"), ("final", None, None), ("completed", None, None)]
    assert full[2]["data"]["speaker"] == "nhatky"
    assert full[2]["data"]["steps"] == [{"kind": "handoff", "companion": "nhatky"}]
    assert full[2]["data"]["messages"][0]["text"].startswith("Chào bạn, mình là Nhật ký")


async def test_flag_off_keeps_the_phase1_v2_shape(clients):
    app, [(client, uid), _] = clients
    await v3_setup(app, client)
    app.state.settings.ai_smart_orchestration_enabled = False
    url = await conversation(client, "dieuphoi")
    model = scripted(reply("Chào bạn!"))
    roles(app, dieuphoi=model)
    app.state.ai.model_override = model
    run = await finish(await start(app, client, url, "Nhìn lại tuần rồi giúp mình"))
    assert run.terminal_status == "completed", run.failure
    full = await stream(client, run.id, "?protocol=2")
    assert [e["type"] for e in full] == ["progress", "final", "completed"]
    assert "speaker" not in full[1]["data"] and "steps" not in full[1]["data"]
