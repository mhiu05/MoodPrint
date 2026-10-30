import json
from datetime import date, timedelta
from uuid import uuid4

import pytest
from agents.tool_context import ToolContext
from pydantic import ValidationError
from sqlalchemy import select

from app.ai.runtime import LiveRun
from app.ai.schemas import MoodReadScope, StartRunInput
from app.core.errors import DomainError
from app.core.security import Actor
from app.infrastructure.database.models import AiRun, AuthSession, Mood, User


def tool_context(run):
    return ToolContext(
        context=run, tool_name="read_mood_summary", tool_call_id="synthetic", tool_arguments="{}"
    )


def test_mood_scope_rejects_inverted_oversized_or_forged_source_selection():
    for scope in (
        {"fromDate": "2026-10-24", "toDate": "2026-10-23"},
        {"fromDate": "2026-01-01", "toDate": "2026-10-24"},
        {"fromDate": "2026-10-23", "toDate": "2026-10-24", "userId": str(uuid4())},
    ):
        with pytest.raises(ValidationError):
            MoodReadScope.model_validate(scope)
    body = StartRunInput.model_validate(
        {
            "text": "Read my selected days",
            "clientMessageId": str(uuid4()),
            "expectedConversationVersion": 1,
            "moodScope": {"fromDate": "2026-10-23", "toDate": "2026-10-24"},
        }
    )
    assert body.mood_scope.from_date == date(2026, 10, 23)


async def prepare(clients, scope):
    app, actors = clients
    client, uid = actors[0]
    response = await client.put(
        "/api/v1/consents/AI",
        json={"enabled": True, "expectedVersion": 1, "policyVersion": "v1"},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert response.status_code == 200
    async with app.state.database.sessions() as db:
        user = await db.get(User, uid)
        session = await db.scalar(select(AuthSession).where(AuthSession.user_id == uid))
        actor = Actor(uid, session.id, user.auth_version)
        version = user.data_version
    c = app.state.ai.store.create(str(uid), str(actor.session_id), "nhip")
    run = LiveRun(actor, c.id, version, uuid4(), mood_scope=scope)
    async with app.state.database.sessions.begin() as db:
        db.add(AiRun(id=run.id, user_id=uid, conversation_id=c.id, bot_id="nhip"))
    return app.state.ai, run


@pytest.mark.postgres
async def test_scoped_tool_uses_only_owner_selected_dates_and_never_includes_notes(clients):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    today = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()
    scope = MoodReadScope(from_date=today - timedelta(days=2), to_date=today)
    runtime, run = await prepare(clients, scope)
    app, actors = clients
    async with app.state.database.sessions.begin() as db:
        for uid, day, value in (
            (actors[0][1], today, 4),
            (actors[0][1], today - timedelta(days=2), 2),
            (actors[0][1], today - timedelta(days=3), 1),
            (actors[1][1], today, 5),
        ):
            db.add(
                Mood(
                    user_id=uid,
                    local_date=day,
                    value=value,
                    note="PRIVATE-NOTE-CANARY",
                    timezone="Asia/Ho_Chi_Minh",
                )
            )
    tool = next(t for t in runtime.tools(run, "nhip") if t.name == "read_mood_summary")
    result = json.loads(await tool.on_invoke_tool(tool_context(run), "{}"))
    assert result["count"] == 2 and result["mean"] == 3
    assert result["buckets"][1]["value"] is None
    assert len(result["buckets"]) == 3 and result["insightAvailable"] is False
    assert "PRIVATE-NOTE-CANARY" not in json.dumps(result)
    assert all("userId" not in bucket and "note" not in bucket for bucket in result["buckets"])
    assert all(t.name != "read_mood_summary" for t in runtime.tools(run, "may"))
    assert all(t.name != "read_mood_summary" for t in runtime.tools(run, "caunoi"))
    run.mood_scope = None
    assert all(t.name != "read_mood_summary" for t in runtime.tools(run, "nhip"))


@pytest.mark.postgres
async def test_tool_rechecks_live_data_version_and_refuses_model_supplied_owner(clients):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    today = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()
    runtime, run = await prepare(clients, MoodReadScope(from_date=today, to_date=today))
    tool = next(t for t in runtime.tools(run, "nhip") if t.name == "read_mood_summary")
    with pytest.raises(DomainError) as rejected:
        await tool.on_invoke_tool(tool_context(run), json.dumps({"userId": str(clients[1][1][1])}))
    assert rejected.value.code == "INVALID_TOOL_ARGUMENTS"
    async with clients[0].state.database.sessions.begin() as db:
        user = await db.get(User, run.actor.user_id)
        user.data_version += 1
    with pytest.raises(DomainError) as error:
        await tool.on_invoke_tool(tool_context(run), "{}")
    assert error.value.code == "CONTEXT_CHANGED"


@pytest.mark.postgres
async def test_tool_rejects_expired_dates_and_third_call(clients):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    today = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()
    runtime, run = await prepare(
        clients,
        MoodReadScope(from_date=today - timedelta(days=90), to_date=today - timedelta(days=90)),
    )
    tool = next(t for t in runtime.tools(run, "nhip") if t.name == "read_mood_summary")
    with pytest.raises(DomainError) as error:
        await tool.on_invoke_tool(tool_context(run), "{}")
    assert error.value.code == "MOOD_SCOPE_EXPIRED"
    run.mood_scope = MoodReadScope(from_date=today, to_date=today)
    run.tool_calls = 2
    with pytest.raises(DomainError) as error:
        await tool.on_invoke_tool(tool_context(run), "{}")
    assert error.value.code == "TOOL_LIMIT"


@pytest.mark.postgres
async def test_sdk_route_reads_explicit_scope_and_idempotency_binds_scope(clients):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from tests.fakes import ScriptedModel, message_output, tool_output

    today = datetime.now(ZoneInfo("Asia/Bangkok")).date()
    app, actors = clients
    client, uid = actors[0]
    await prepare(clients, None)
    model = ScriptedModel(
        [
            [tool_output("read_mood_summary", "read_selected")],
            [message_output('{"focus":"overview","next_step":"none"}')],
        ]
    )
    app.state.ai.model_override = model
    async with app.state.database.sessions.begin() as db:
        db.add(
            Mood(
                user_id=uid,
                local_date=today,
                value=4,
                note="NEVER-SEND-NOTE",
                timezone="Asia/Bangkok",
            )
        )
    headers = {"Idempotency-Key": str(uuid4())}
    c = await client.post("/api/v1/ai/conversations", json={"botId": "nhip"}, headers=headers)
    assert c.status_code == 201
    endpoint = f"/api/v1/ai/conversations/{c.json()['conversationId']}/messages"
    body = {
        "text": "Xem khoảng ngày tôi chọn",
        "clientMessageId": str(uuid4()),
        "expectedConversationVersion": 1,
        "moodScope": {"fromDate": str(today), "toDate": str(today)},
    }
    accepted = await client.post(endpoint, json=body, headers=headers)
    assert accepted.status_code == 202
    stream = await client.get(accepted.json()["eventsUrl"])
    assert "event: completed" in stream.text and "event: final" in stream.text
    assert len(model.calls) == 2 and model.calls[0]["tools"][-1].name == "read_mood_summary"
    model_input = json.dumps(model.calls[1]["input"], ensure_ascii=False)
    assert "sourceVersions" in model_input and "NEVER-SEND-NOTE" not in model_input
    replay = await client.post(endpoint, json=body, headers=headers)
    assert replay.status_code == 202 and replay.json()["runId"] == accepted.json()["runId"]
    body["moodScope"]["fromDate"] = str(today - timedelta(days=1))
    changed = await client.post(endpoint, json=body, headers=headers)
    assert changed.status_code == 409 and changed.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"


@pytest.mark.postgres
async def test_tool_rechecks_consent_and_expired_provider_session_before_read(clients):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from sqlalchemy import text

    from app.infrastructure.database.models import Consent

    today = datetime.now(ZoneInfo("Asia/Bangkok")).date()
    runtime, run = await prepare(clients, MoodReadScope(from_date=today, to_date=today))
    tool = next(t for t in runtime.tools(run, "nhip") if t.name == "read_mood_summary")
    async with clients[0].state.database.sessions.begin() as db:
        consent = await db.get(Consent, (run.actor.user_id, "AI"))
        consent.enabled = False
    await tool.on_invoke_tool(tool_context(run), "{}")
    async with clients[0].state.database.sessions.begin() as db:
        await db.execute(
            text("delete from auth.sessions where user_id=:uid"), {"uid": run.actor.user_id}
        )
    with pytest.raises(DomainError) as expired:
        await tool.on_invoke_tool(tool_context(run), "{}")
    assert expired.value.code == "SESSION_EXPIRED"
