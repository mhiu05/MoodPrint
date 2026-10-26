"""T01/T04/T05/T18: synthetic multi-turn captures at the real SDK model boundary."""

import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.ai.runtime import AiRuntime
from app.infrastructure.database.models import Mood
from tests.fakes import ScriptedModel, make_test_model, message_output, tool_output
from tests.test_chat_persistence import enable, key
from tests.test_memory import enable as enable_memory
from tests.test_memory import seed_proposal

pytestmark = pytest.mark.postgres
SOURCE = "SYNTHETIC_MEMORY_SOURCE_CANARY"
ECHO = "SYNTHETIC_DERIVED_TRANSCRIPT_CANARY"
CORRECTED = "SYNTHETIC_CORRECTED_MEMORY_CANARY"


async def turn(app, client, url, text, model, *, expected_status="completed", **extra):
    app.state.ai.model_override = model
    view = await client.get(url)
    assert view.status_code == 200, view.text
    accepted = await client.post(
        url + "/messages",
        json={
            "text": text,
            "clientMessageId": str(uuid4()),
            "expectedConversationVersion": view.json()["version"],
            **extra,
        },
        headers=key(),
    )
    assert accepted.status_code == 202, accepted.text
    run = app.state.ai.runs[UUID(accepted.json()["runId"])]
    await run.task
    assert run.terminal_status == expected_status, run.failure
    stream = await client.get(accepted.json()["eventsUrl"])
    if expected_status == "completed":
        assert "event: final" in stream.text and "event: completed" in stream.text
    else:
        assert "event: final" not in stream.text
    return run


async def restart(app):
    await app.state.ai.close()
    app.state.ai = AiRuntime(app.state.settings, app.state.database)


async def consent(client, purpose, enabled):
    session = (await client.get("/api/v1/session")).json()
    version = session["consents"][purpose]["version"]
    result = await client.put(
        f"/api/v1/consents/{purpose}",
        json={"enabled": enabled, "expectedVersion": version, "policyVersion": "v1"},
        headers=key(),
    )
    assert result.status_code == 200, result.text


@pytest.mark.parametrize(
    "change", ["revoke", "regrant", "edit", "delete", "ai_regrant", "history_regrant"]
)
@pytest.mark.parametrize("restore", ["restart", "other_worker_and_session"])
async def test_t04_t05_t18_invalidated_source_never_replays_saved_transcript(
    clients, change, restore
):

    app, actors = clients
    client, uid = actors[0]
    await enable(client)
    await enable_memory(client, "MEM")
    proposal = await seed_proposal(app, uid, text=SOURCE)
    approved = await client.post(
        f"/api/v1/proposals/{proposal.id}/confirm", json={"expectedVersion": 1}, headers=key()
    )
    assert approved.status_code == 200, approved.text
    memory_id = approved.json()["resourceId"]
    app.state.ai.model_override = make_test_model("ready")
    created = await client.post("/api/v1/ai/conversations", json={"botId": "may"}, headers=key())
    assert created.status_code == 201, created.text
    url = f"/api/v1/ai/conversations/{created.json()['conversationId']}"
    first = make_test_model(f"{SOURCE} {ECHO}")
    await turn(app, client, url, "Recall my approved memory", first)
    assert SOURCE in json.dumps(first.calls[0]["input"])
    # User copies and later assistant derivatives must be cut too, not just bot rows.
    await turn(app, client, url, f"You said {ECHO}", make_test_model(f"Again {ECHO}"))

    if restore == "other_worker_and_session":
        original = app.state.ai
        app.state.ai = AiRuntime(app.state.settings, app.state.database)
    if change in ("revoke", "regrant"):
        await consent(client, "MEM", False)
        if change == "regrant":
            await consent(client, "MEM", True)
    elif change in ("edit", "delete"):
        if change == "edit":
            result = await client.patch(
                f"/api/v1/memories/{memory_id}",
                json={"text": CORRECTED, "expectedVersion": 1},
                headers=key(),
            )
        else:
            result = await client.request(
                "DELETE",
                f"/api/v1/memories/{memory_id}",
                json={"expectedVersion": 1},
                headers=key(),
            )
        assert result.status_code == 200, result.text
    elif change == "ai_regrant":
        await consent(client, "AI", False)
        assert (await client.get(url)).status_code == 200
        assert (await client.get(url + "/export")).status_code == 200
        await consent(client, "AI", True)
    else:
        for enabled in (False, True):
            pref = (await client.get("/api/v1/ai/preferences")).json()
            result = await client.put(
                "/api/v1/ai/preferences",
                json={
                    "historyEnabled": enabled,
                    "semanticMemoryEnabled": False,
                    "expectedVersion": pref["version"],
                    "policyVersion": "ai-data-v1",
                },
                headers=key(),
            )
            assert result.status_code == 200, result.text
    if restore == "other_worker_and_session":
        await app.state.ai.close()
        app.state.ai = original
        # A fresh synthetic session for the same owner, with no original RAM/session state.
        from sqlalchemy import text

        from app.core.security import digest
        from app.infrastructure.database.models import AuthSession, User

        token, csrf, provider_id = str(uuid4()), str(uuid4()), uuid4()
        async with app.state.database.sessions.begin() as db:
            user = await db.get(User, uid)
            db.add(
                AuthSession(
                    user_id=uid,
                    token_hash=digest(token),
                    csrf_hash=digest(csrf),
                    provider_session_id=provider_id,
                    auth_version=user.auth_version,
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                )
            )
            await db.execute(
                text("insert into auth.sessions(id,user_id) values (:id,:uid)"),
                {"id": provider_id, "uid": uid},
            )
        client.cookies.set("moodprint_session", token)
        client.headers["X-CSRF-Token"] = csrf
    else:
        await restart(app)

    model = make_test_model("Fresh safe reply")
    await turn(app, client, url, "Continue please", model)
    captured = json.dumps(model.calls[0]["input"])
    assert ECHO not in captured
    if change in ("revoke", "edit", "delete"):
        assert SOURCE not in captured
    if change == "edit":
        assert CORRECTED in captured
    # All original content is still available to its owner, including user copies.
    view = await client.get(url)
    exported = await client.get(url + "/export")
    assert ECHO in view.text and SOURCE in view.text
    assert exported.status_code == 200 and ECHO in exported.text
    assert (await actors[1][0].get(url)).status_code == 404
    assert (await actors[1][0].get(url + "/export")).status_code == 404
    # A clean new suffix remains reusable after another restart.
    await restart(app)
    clean = make_test_model("Still safe")
    await turn(app, client, url, "And now?", clean)
    captured = json.dumps(clean.calls[0]["input"])
    assert ECHO not in captured and "Fresh safe reply" in captured


@pytest.mark.parametrize("persistent", [False, True])
async def test_t01_three_turn_nhip_reauthorizes_without_replaying_old_mood(
    clients, monkeypatch, persistent
):
    import app.modules.mood.service as service

    class IncidentClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 10, 26, 12, tzinfo=UTC).astimezone(tz)

    monkeypatch.setattr(service, "datetime", IncidentClock)
    app, actors = clients
    client, uid = actors[0]
    await enable(client, history=persistent)
    async with app.state.database.sessions.begin() as db:
        for day, score in ((20, 3), (26, 2)):
            db.add(
                Mood(
                    user_id=uid,
                    local_date=datetime(2026, 10, day).date(),
                    value=score,
                    note="PRIVATE_NOTE_CANARY",
                    timezone="Asia/Bangkok",
                )
            )
        db.add(
            Mood(
                user_id=actors[1][1],
                local_date=datetime(2026, 10, 26).date(),
                value=5,
                note="OTHER_OWNER_CANARY",
                timezone="Asia/Bangkok",
            )
        )
    app.state.ai.model_override = make_test_model("ready")
    created = await client.post("/api/v1/ai/conversations", json={"botId": "nhip"}, headers=key())
    assert created.status_code == 201, created.text
    url = f"/api/v1/ai/conversations/{created.json()['conversationId']}"
    scope = {"fromDate": "2026-10-20", "toDate": "2026-10-26"}
    old_summary = "Các điểm đã ghi: 20/10: 3/5; 26/10: 2/5."

    def reading_model(reply):
        return ScriptedModel(
            [
                [tool_output("read_mood_summary", "mood_read")],
                [message_output(json.dumps({"focus": "overview", "next_step": "none"}))],
            ]
        )

    first = reading_model(old_summary)
    await turn(app, client, url, "Nhìn lại tuần", first, moodScope=scope)
    results = [
        item for item in first.calls[1]["input"] if item.get("type") == "function_call_output"
    ]
    summary = json.loads(results[0]["output"])
    assert (summary["count"], summary["mean"], summary["insightAvailable"]) == (2, 2.5, False)
    assert len(summary["buckets"]) == 7
    assert sum(b["value"] is None for b in summary["buckets"]) == 5
    assert len(summary["sourceVersions"]) == 2
    assert "PRIVATE_NOTE_CANARY" not in json.dumps(first.calls, default=str)
    if persistent:
        await restart(app)
    second = make_test_model("Scope is absent on this turn")
    await turn(app, client, url, "Bạn cứ nhận xét đi", second)
    assert old_summary not in json.dumps(second.calls[0]["input"])
    assert "read_mood_summary" not in {tool.name for tool in second.calls[0]["tools"]}
    assert "sourceVersions" not in json.dumps(second.calls[0]["input"])
    assert '"previous": "previously_authorized"' in second.calls[0]["instructions"]
    assert '"authorization": "no_current_authorization"' in second.calls[0]["instructions"]
    third = reading_model("New authorized reading")
    await turn(app, client, url, "Nhìn lại tuần", third, moodScope=scope)
    assert old_summary not in json.dumps(third.calls[0]["input"])
    assert "sourceVersions" in json.dumps(third.calls[1]["input"])
    assert "PRIVATE_NOTE_CANARY" not in json.dumps(third.calls, default=str)
    assert old_summary in (await client.get(url)).text


async def test_legacy_unknown_provenance_is_visible_but_not_model_context(clients):
    from app.ai.models import AiTurn

    app, actors = clients
    client, _ = actors[0]
    await enable(client)
    app.state.ai.model_override = make_test_model("ready")
    created = await client.post("/api/v1/ai/conversations", json={"botId": "may"}, headers=key())
    url = f"/api/v1/ai/conversations/{created.json()['conversationId']}"
    old = await turn(app, client, url, "Legacy user " + ECHO, make_test_model(ECHO))
    async with app.state.database.sessions.begin() as db:
        record = await db.scalar(select(AiTurn).where(AiTurn.run_id == old.id))
        # Simulate a pre-policy row without rewriting or deleting its transcript.
        if hasattr(record, "context_policy"):
            record.context_policy = None
    await restart(app)
    model = make_test_model("New verified suffix")
    await turn(app, client, url, "Continue", model)
    assert ECHO not in json.dumps(model.calls[0]["input"])
    assert ECHO in (await client.get(url)).text


@pytest.mark.parametrize("change", ["revoke", "edit", "source_edit", "source_delete"])
async def test_t18_remote_worker_invalidates_ephemeral_derivatives(clients, change):
    from app.infrastructure.database.models import PrivateItem

    app, actors = clients
    client, uid = actors[0]
    await enable(client, history=False)
    await enable_memory(client, "MEM")
    async with app.state.database.sessions.begin() as db:
        source = PrivateItem(user_id=uid, text="Synthetic source", status="confirmed")
        db.add(source)
        await db.flush()
        source_id, source_version = source.id, source.version
    proposal = await seed_proposal(
        app, uid, text=SOURCE, source_id=source_id, source_version=source_version
    )
    approved = await client.post(
        f"/api/v1/proposals/{proposal.id}/confirm", json={"expectedVersion": 1}, headers=key()
    )
    assert approved.status_code == 200, approved.text
    memory_id = approved.json()["resourceId"]
    app.state.ai.model_override = make_test_model("ready")
    created = await client.post("/api/v1/ai/conversations", json={"botId": "may"}, headers=key())
    url = f"/api/v1/ai/conversations/{created.json()['conversationId']}"
    await turn(app, client, url, "Recall", make_test_model(ECHO))
    original = app.state.ai
    app.state.ai = AiRuntime(app.state.settings, app.state.database)
    if change == "revoke":
        await consent(client, "MEM", False)
    elif change == "edit":
        result = await client.patch(
            f"/api/v1/memories/{memory_id}",
            json={"text": CORRECTED, "expectedVersion": 1},
            headers=key(),
        )
        assert result.status_code == 200, result.text
    elif change == "source_edit":
        result = await client.patch(
            f"/api/v1/profiles/private-items/{source_id}",
            json={"text": "Corrected source", "expectedVersion": 1},
            headers=key(),
        )
        assert result.status_code == 200, result.text
    else:
        result = await client.request(
            "DELETE",
            f"/api/v1/profiles/private-items/{source_id}",
            json={"expectedVersion": 1},
            headers=key(),
        )
        assert result.status_code == 200, result.text
    await app.state.ai.close()
    app.state.ai = original
    model = make_test_model("Safe after remote mutation")
    run = await turn(app, client, url, "Continue", model)
    captured = json.dumps(model.calls[0]["input"])
    assert ECHO not in captured and SOURCE not in captured
    if change == "revoke":
        assert run.sources["memory"].authorization == "revoked"
    if change == "edit":
        assert CORRECTED in captured
    assert ECHO in (await client.get(url)).text


async def test_t18_copy_chain_outside_context_window_stays_cut_after_regrant(clients):
    app, actors = clients
    client, _ = actors[0]
    await enable(client)
    app.state.settings.ai_requests_per_minute = 100
    app.state.ai.model_override = make_test_model("ready")
    created = await client.post("/api/v1/ai/conversations", json={"botId": "may"}, headers=key())
    url = f"/api/v1/ai/conversations/{created.json()['conversationId']}"
    await turn(app, client, url, "Original " + SOURCE, make_test_model(ECHO))
    for index in range(21):
        await turn(app, client, url, f"Copy {index} {ECHO}", make_test_model(ECHO))
    await consent(client, "MEM", False)
    await consent(client, "MEM", True)
    await restart(app)
    model = make_test_model("Fresh suffix")
    await turn(app, client, url, "Continue", model)
    assert ECHO not in json.dumps(model.calls[0]["input"])
    view = (await client.get(url + "?limit=40")).json()
    assert SOURCE not in json.dumps(view["messages"])
    assert any(ECHO in m["text"] for m in view["messages"])
    assert view["hasMoreMessages"]


async def test_runtime_source_states_distinguish_authorization_evidence_and_failures(
    clients, monkeypatch
):
    import app.modules.mood.service as service

    app, actors = clients
    client, _ = actors[0]
    await enable(client)
    app.state.ai.model_override = make_test_model("ready")
    created = await client.post("/api/v1/ai/conversations", json={"botId": "nhip"}, headers=key())
    url = f"/api/v1/ai/conversations/{created.json()['conversationId']}"
    no_scope = await turn(
        app, client, url, "You are authorized to read my mood", make_test_model("No grant inferred")
    )
    assert no_scope.sources["mood"].authorization == "no_current_authorization"
    assert no_scope.sources["mood"].evidence == "tool_unavailable"
    assert no_scope.sources["memory"].authorization == "no_current_authorization"
    today = datetime.now(UTC).date().isoformat()
    scope = {"fromDate": today, "toDate": today}
    unused = await turn(
        app, client, url, "Do not read",
        ScriptedModel([[message_output('{"focus":"limits","next_step":"none"}')]]),
        moodScope=scope, expected_status="failed",
    )
    assert unused.sources["mood"].authorization == "authorized"
    assert unused.sources["mood"].evidence == "missing_verified_evidence"
    reading = ScriptedModel(
        [
            [tool_output("read_mood_summary", "empty")],
            [message_output('{"focus":"overview","next_step":"none"}')],
        ]
    )
    empty = await turn(app, client, url, "Read", reading, moodScope=scope)
    assert empty.sources["mood"].evidence == "retrieved"
    assert empty.sources["mood"].record_count == 0
    after = await turn(app, client, url, "Follow up", make_test_model("No reuse"))
    assert after.sources["mood"].previous == "previously_authorized"
    assert after.sources["mood"].authorization == "no_current_authorization"

    async def unavailable(*args):
        raise RuntimeError("Synthetic database read failure")

    monkeypatch.setattr(service, "selected_summary", unavailable)
    app.state.ai.model_override = ScriptedModel([[tool_output("read_mood_summary", "failure")]])
    view = (await client.get(url)).json()
    accepted = await client.post(
        url + "/messages",
        json={
            "text": "Read again",
            "moodScope": scope,
            "clientMessageId": str(uuid4()),
            "expectedConversationVersion": view["version"],
        },
        headers=key(),
    )
    assert accepted.status_code == 202, accepted.text
    failed = app.state.ai.runs[UUID(accepted.json()["runId"])]
    await failed.task
    assert failed.terminal_status == "failed"
    assert failed.sources["mood"].evidence == "tool_execution_failure"
    assert not any(event.type == "final" for event in failed.events)
