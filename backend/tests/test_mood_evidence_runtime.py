"""Real routes + PostgreSQL + SDK; synthetic model scripts only control model I/O."""

import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from app.infrastructure.database.models import Mood
from tests.fakes import ScriptedModel, make_test_model, message_output, tool_output
from tests.test_chat_persistence import enable, key
from tests.test_context_privacy import consent, restart, turn

pytestmark = pytest.mark.postgres


def reader(plan=None):
    return ScriptedModel([
        [tool_output("read_mood_summary", "evidence_read")],
        [message_output(json.dumps(plan or {"focus": "overview", "next_step": "none"}))],
    ])


async def setup(clients, count):
    app, actors = clients
    client, uid = actors[0]
    await enable(client)
    today = datetime.now(UTC).date()
    async with app.state.database.sessions.begin() as db:
        for i, value in enumerate((3, 2, 4)[:count]):
            db.add(Mood(user_id=uid, local_date=today - timedelta(days=6 - i * 3), value=value,
                        note="EVIDENCE_PRIVATE_NOTE", timezone="Asia/Bangkok"))
        db.add(Mood(user_id=actors[1][1], local_date=today, value=5, note="PEER_NOTE", timezone="Asia/Bangkok"))
    app.state.ai.model_override = make_test_model("ready")
    created = await client.post("/api/v1/ai/conversations", json={"botId": "nhip"}, headers=key())
    assert created.status_code == 201
    url = f"/api/v1/ai/conversations/{created.json()['conversationId']}"
    scope = {"fromDate": str(today - timedelta(days=6)), "toDate": str(today)}
    return app, client, url, scope


@pytest.mark.parametrize("count", [0, 1, 2, 3])
async def test_actual_sdk_receives_typed_evidence_and_only_backend_claims_reach_sse(clients, count):
    app, client, url, scope = await setup(clients, count)
    model = reader()
    run = await turn(app, client, url, "Nhìn lại tuần, không cần lời khuyên", model, moodScope=scope)
    raw = next(item["output"] for item in model.calls[1]["input"] if item.get("type") == "function_call_output")
    evidence = json.loads(raw)["evidence"]
    assert evidence["statistics"]["recordedDays"] == count
    assert evidence["statistics"]["missingDays"] == 7 - count
    assert evidence["capabilities"]["inference"] is False
    assert "EVIDENCE_PRIVATE_NOTE" not in str(model.calls) and "PEER_NOTE" not in str(model.calls)
    final = next(event.data for event in run.events if event.type == "final")
    assert f"{count}/7" in final["text"]
    assert set(final) == {"text", "cards"}
    assert run.mood_evidence is None


@pytest.mark.parametrize("forgery", [
    {"text": "7 ngày đã ghi, trung bình 5 điểm"},
    {"mean": 5}, {"trend": "increasing"}, {"recorded_days": 7},
])
async def test_forged_scoped_claims_never_emit_final(clients, forgery):
    app, client, url, scope = await setup(clients, 2)
    run = await turn(app, client, url, "Nhận xét", reader({"focus": "overview", "next_step": "none", **forgery}), moodScope=scope, expected_status="failed")
    assert not any(event.type == "final" for event in run.events)
    assert run.mood_evidence is None


@pytest.mark.parametrize("change", ["edit", "delete", "revoke_regrant"])
async def test_saved_three_turn_followup_reloads_current_sources_after_restart(clients, change):
    app, client, url, scope = await setup(clients, 2)
    old = await turn(app, client, url, "Nhìn lại tuần", reader(), moodScope=scope)
    old_text = next(e.data["text"] for e in old.events if e.type == "final")
    await restart(app)
    followup = make_test_model("Lượt chia sẻ trước chỉ có hiệu lực cho lượt đã gửi. Bạn có thể chia sẻ lại khoảng ngày để mình kiểm tra và nhận xét tiếp.")
    await turn(app, client, url, "Bạn cứ nhận xét đi", followup)
    captured = str(followup.calls[0]["input"])
    assert old_text not in captured and "sourceRevisions" not in captured
    assert all(tool.name != "read_mood_summary" for tool in followup.calls[0]["tools"])
    assert '"previous": "previously_authorized"' in followup.calls[0]["instructions"]
    if change == "edit":
        result = await client.put(f"/api/v1/moods/{scope['fromDate']}", json={"value": 5, "note": "NEW_PRIVATE_NOTE", "timezone": "Asia/Bangkok", "expectedVersion": 1}, headers=key())
        assert result.status_code == 200, result.text
    elif change == "delete":
        result = await client.request("DELETE", f"/api/v1/moods/{scope['fromDate']}", json={"expectedVersion": 1}, headers=key())
        assert result.status_code == 200, result.text
    else:
        await consent(client, "AI", False)
        await consent(client, "AI", True)
    await restart(app)
    current = reader()
    new = await turn(app, client, url, "Bạn cứ nhận xét đi", current, moodScope=scope)
    summary = json.loads(next(item["output"] for item in current.calls[1]["input"] if item.get("type") == "function_call_output"))
    if change == "edit":
        assert summary["mean"] == 3.5 and summary["sourceVersions"][0]["version"] == 2
    elif change == "delete":
        assert summary["count"] == 1 and summary["mean"] == 2
    assert old_text not in str(current.calls[0]["input"])
    assert new.mood_evidence is None
    assert (await client.get(url + "/export")).status_code == 200
    assert (await clients[1][1][0].get(url)).status_code == 404


async def test_source_edit_while_model_is_running_cancels_without_final(clients):
    import asyncio

    app, client, url, scope = await setup(clients, 2)
    class HoldAfterRead(ScriptedModel):
        def __init__(self):
            super().__init__(reader().responses)
            self.after_read = asyncio.Event()

        async def stream_response(self, *args, **kwargs):
            if len(self.calls) == 1:
                self.hold = True
                self.after_read.set()
            async for event in super().stream_response(*args, **kwargs):
                yield event

    model = HoldAfterRead()
    app.state.ai.model_override = model
    version = (await client.get(url)).json()["version"]
    from uuid import uuid4
    accepted = await client.post(url + "/messages", json={"text": "Nhận xét", "moodScope": scope, "clientMessageId": str(uuid4()), "expectedConversationVersion": version}, headers=key())
    assert accepted.status_code == 202
    run = app.state.ai.runs[UUID(accepted.json()["runId"])]
    await asyncio.wait_for(model.after_read.wait(), timeout=5)
    assert run.mood_evidence is not None
    result = await client.put(f"/api/v1/moods/{scope['fromDate']}", json={"value": 5, "note": "", "timezone": "Asia/Bangkok", "expectedVersion": 1}, headers=key())
    assert result.status_code == 200, result.text
    await run.task
    assert run.terminal_status == "cancelled"
    assert not any(e.type == "final" for e in run.events)
    assert run.mood_evidence is None
