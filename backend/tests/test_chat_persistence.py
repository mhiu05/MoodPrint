import asyncio
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import SecretStr

from tests.fakes import make_test_model

pytestmark = pytest.mark.postgres


def key():
    return {"Idempotency-Key": str(uuid4())}


async def enable(client, history=True):
    await client.put(
        "/api/v1/consents/AI",
        json={"enabled": True, "expectedVersion": 1, "policyVersion": "v1"},
        headers=key(),
    )
    response = await client.put(
        "/api/v1/ai/preferences",
        json={
            "historyEnabled": history,
            "semanticMemoryEnabled": False,
            "expectedVersion": 1,
            "policyVersion": "ai-data-v1",
        },
        headers=key(),
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_history_is_available_by_default_without_a_personal_optin(clients):
    app, actors = clients
    app.state.ai.model_override = make_test_model("Synthetic reply")
    client = actors[0][0]
    initial = await client.get("/api/v1/ai/preferences")
    assert initial.status_code == 200
    assert initial.json()["historyEnabled"] is True
    created = await client.post(
        "/api/v1/ai/conversations", json={"botId": "may", "persistent": True}, headers=key()
    )
    assert created.status_code == 201, created.text
    assert created.json()["persistent"] is True


async def test_new_saved_history_never_exceeds_thirty_days(clients):
    app, actors = clients
    app.state.ai.model_override = make_test_model("Synthetic reply")
    client = actors[0][0]
    app.state.settings.chat_retention_days = 90  # Legacy deployment setting.
    await enable(client)
    preference = (await client.get("/api/v1/ai/preferences")).json()
    assert preference["retentionDays"] == 30
    created = await client.post(
        "/api/v1/ai/conversations", json={"botId": "may"}, headers=key(),
    )
    assert created.status_code == 201, created.text
    expiry = datetime.fromisoformat(created.json()["expiresAt"])
    remaining = expiry - datetime.now(UTC)
    assert timedelta(days=29) < remaining <= timedelta(days=30)


async def test_memory_reapproval_does_not_resume_withdrawn_voyage_processing(clients):
    from tests.test_memory import seed_proposal

    app, actors = clients
    client, uid = actors[0]
    app.state.settings.semantic_memory_enabled = True
    app.state.settings.voyage_api_key = SecretStr("synthetic-test-only")
    for purpose in ("AI", "MEM"):
        response = await client.put(
            f"/api/v1/consents/{purpose}",
            json={"enabled": True, "expectedVersion": 1, "policyVersion": "v1"},
            headers=key(),
        )
        assert response.status_code == 200, response.text
    enabled = await client.put(
        "/api/v1/ai/preferences",
        json={"historyEnabled": False, "semanticMemoryEnabled": True,
              "expectedVersion": 1, "policyVersion": "ai-data-v1"}, headers=key(),
    )
    assert enabled.status_code == 200, enabled.text
    withdrawn = await client.put(
        "/api/v1/consents/MEM",
        json={"enabled": False, "expectedVersion": 2, "policyVersion": "v1"},
        headers=key(),
    )
    assert withdrawn.status_code == 200, withdrawn.text
    proposal = await seed_proposal(app, uid)
    approved = await client.post(
        f"/api/v1/proposals/{proposal.id}/confirm",
        json={"expectedVersion": 1}, headers=key(),
    )
    assert approved.status_code == 200, approved.text
    assert (await client.get("/api/v1/ai/preferences")).json()["semanticMemoryEnabled"] is True


@pytest.mark.parametrize("bot_id", ["may", "guong", "nhip", "rure", "caunoi"])
async def test_every_assistant_rebuilds_context_from_postgres_after_runtime_restart(clients, bot_id):
    from app.ai.evidence import source_instructions
    from app.ai.journal import journal_instructions
    from app.ai.prompts import conversation_instructions, instructions
    from app.ai.runtime import AiRuntime
    from tests.test_memory import enable as enable_memory
    from tests.test_memory import seed_proposal

    app, actors = clients
    client, uid = actors[0]
    await enable(client)
    await enable_memory(client, "MEM")
    if bot_id in ("may", "guong", "nhip"):
        proposal = await seed_proposal(app, uid, bot_id=bot_id, text="Approved synthetic watercolor memory")
        approved = await client.post(f"/api/v1/proposals/{proposal.id}/confirm",
                                     json={"expectedVersion": 1}, headers=key())
        assert approved.status_code == 200
    app.state.ai.model_override = make_test_model("First synthetic reply")
    c = (await client.post("/api/v1/ai/conversations", json={"botId": bot_id}, headers=key())).json()
    url = f"/api/v1/ai/conversations/{c['conversationId']}"
    first = await client.post(url + "/messages", json={"text": "First synthetic watercolor input",
        "clientMessageId": str(uuid4()), "expectedConversationVersion": 1}, headers=key())
    assert first.status_code == 202
    await app.state.ai.runs[__import__("uuid").UUID(first.json()["runId"])].task
    await app.state.ai.close()
    app.state.ai = AiRuntime(app.state.settings, app.state.database)
    model = make_test_model("Second synthetic reply")
    app.state.ai.model_override = model
    restored = (await client.get(url)).json()
    second = await client.post(url + "/messages", json={"text": "Continue with my approved watercolor memory",
        "clientMessageId": str(uuid4()), "expectedConversationVersion": restored["version"]}, headers=key())
    assert second.status_code == 202
    restored_run = app.state.ai.runs[__import__("uuid").UUID(second.json()["runId"])]
    await restored_run.task
    assert restored_run.terminal_status == "completed"
    expected_intent = {'may':'conversation','guong':'reflection','nhip':'conversation','rure':'activity','caunoi':'connection'}[bot_id]
    assert model.calls[0]["instructions"] == (
        instructions(bot_id) + source_instructions(restored_run, bot_id, mood_analysis=False)
        + (journal_instructions(restored_run) if bot_id == "nhip" else "")
        + conversation_instructions(bot_id, expected_intent)
    )
    history = json.dumps(model.calls[0]["input"])
    assert "First synthetic watercolor input" in history
    assert "First synthetic reply" in history
    assert "Continue with my approved watercolor memory" in history
    if bot_id in ("may", "guong", "nhip"):
        assert "Approved synthetic watercolor memory" in history
    else:
        assert "Approved synthetic watercolor memory" not in history
    tools = {tool.name for tool in model.calls[0]["tools"]}
    assert tools == ({"propose_memory"} if bot_id == "guong" else
                     {"propose_memory", "search_journal_entries"} if bot_id == "nhip" else
                     {"propose_memory"} if bot_id == "may" else set())
    assert (await actors[1][0].get(url)).status_code == 404


async def test_durable_history_survives_runtime_replacement_and_retry_is_unique(clients):
    from app.ai.runtime import AiRuntime

    app, actors = clients
    client = actors[0][0]
    app.state.ai.model_override = make_test_model("A persisted synthetic reply")
    await enable(client)
    c = (await client.post("/api/v1/ai/conversations", json={"botId": "may"}, headers=key())).json()
    assert c["persistent"] is True
    url = f"/api/v1/ai/conversations/{c['conversationId']}"
    body = {
        "text": "Synthetic persisted input",
        "clientMessageId": str(uuid4()),
        "expectedConversationVersion": 1,
    }
    responses = await asyncio.gather(
        *(client.post(url + "/messages", json=body, headers=key()) for _ in range(2))
    )
    assert [r.status_code for r in responses] == [202, 202]
    assert responses[0].json()["runId"] == responses[1].json()["runId"]
    run = app.state.ai.runs[__import__("uuid").UUID(responses[0].json()["runId"])]
    await run.task
    await app.state.ai.close()
    app.state.ai = AiRuntime(app.state.settings, app.state.database)
    view = await client.get(url)
    assert view.status_code == 200, view.text
    assert [m["text"] for m in view.json()["messages"]] == [
        body["text"],
        "A persisted synthetic reply",
    ]
    assert (await actors[1][0].get(url)).status_code == 404
    assert (await actors[1][0].get(url + "/export")).status_code == 404
    replay = await client.post(url + "/messages", json=body, headers=key())
    # Idempotency receipts can be recovered without calling the provider again.
    assert replay.status_code == 202, replay.text
    stream = await client.get(replay.json()["eventsUrl"])
    assert "completed" in stream.text and "A persisted synthetic reply" in stream.text


async def test_history_is_manageable_with_ai_off_and_disable_does_not_erase(clients):
    app, actors = clients
    client = actors[0][0]
    app.state.ai.model_override = make_test_model("Synthetic")
    await enable(client)
    c = (await client.post("/api/v1/ai/conversations", json={"botId": "may"}, headers=key())).json()
    url = f"/api/v1/ai/conversations/{c['conversationId']}"
    pref = await client.put(
        "/api/v1/ai/preferences",
        json={
            "historyEnabled": False,
            "semanticMemoryEnabled": False,
            "expectedVersion": 2,
            "policyVersion": "ai-data-v1",
        },
        headers=key(),
    )
    assert pref.status_code == 200
    await client.put(
        "/api/v1/consents/AI",
        json={"enabled": False, "expectedVersion": 2, "policyVersion": "v1"},
        headers=key(),
    )
    assert (await client.get(url)).status_code == 200
    assert (await client.get(url + "/export")).status_code == 200
    assert len((await client.get("/api/v1/ai/conversations")).json()) == 1
    assert (await client.delete(url)).status_code == 204
    assert (await client.get(url)).status_code in (404, 410)


async def test_two_workers_share_admission_and_remote_cancellation(clients):
    import httpx

    from app.core.config import Settings
    from app.main import create_app
    from tests.fakes import ScriptedModel, message_output

    app, actors = clients
    client, _ = actors[0]
    app.state.settings.ai_global_concurrency = 1
    model = ScriptedModel([[message_output('{"text":"Must never publish","cards":[]}')]], hold=True)
    app.state.ai.model_override = model
    await enable(client)
    first = (await client.post("/api/v1/ai/conversations", json={"botId":"may"}, headers=key())).json()
    second = (await client.post("/api/v1/ai/conversations", json={"botId":"guong"}, headers=key())).json()
    accepted = await client.post(f"/api/v1/ai/conversations/{first['conversationId']}/messages", json={"text":"Hold synthetic","clientMessageId":str(uuid4()),"expectedConversationVersion":1}, headers=key())
    assert accepted.status_code == 202
    await asyncio.wait_for(model.started.wait(), 3)
    worker = create_app(Settings(_env_file=None, app_env="test", ai_global_concurrency=1))
    worker.state.database.sessions = app.state.database.sessions
    worker.state.ai.model_override = make_test_model("Second worker")
    async with worker.router.lifespan_context(worker), httpx.AsyncClient(transport=httpx.ASGITransport(app=worker), base_url="http://test", cookies=client.cookies, headers=dict(client.headers)) as remote:
        busy = await remote.post(f"/api/v1/ai/conversations/{second['conversationId']}/messages", json={"text":"Should hit shared cap","clientMessageId":str(uuid4()),"expectedConversationVersion":1}, headers=key())
        assert busy.status_code == 429, busy.text
        cancellation = await remote.post(f"/api/v1/ai/runs/{accepted.json()['runId']}/cancel", json={"expectedVersion":1})
        assert cancellation.status_code == 200, cancellation.text
        await asyncio.wait_for(app.state.ai.runs[__import__("uuid").UUID(accepted.json()["runId"])].task, 3)
        assert model.cancelled
        stream = await remote.get(accepted.json()["eventsUrl"])
        assert "cancelled" in stream.text and "Must never publish" not in stream.text


async def test_message_cursor_is_ordered_scoped_and_history_expiry_is_immediate(clients):
    from datetime import timedelta

    from app.ai.models import AiConversation
    from app.infrastructure.database.models import now

    app, actors = clients
    app.state.ai.model_override = make_test_model("Synthetic ordered reply")
    client = actors[0][0]
    await enable(client)
    c = (await client.post("/api/v1/ai/conversations", json={"botId":"may"}, headers=key())).json()
    url = f"/api/v1/ai/conversations/{c['conversationId']}"
    for n in range(3):
        snapshot = (await client.get(url)).json()
        sent = await client.post(url + "/messages", json={"text":f"Synthetic page {n}","clientMessageId":str(uuid4()),"expectedConversationVersion":snapshot["version"]}, headers=key())
        assert sent.status_code == 202, sent.text
        await app.state.ai.runs[__import__("uuid").UUID(sent.json()["runId"])].task
    page = (await client.get(url + "?limit=2")).json()
    assert page["hasMoreMessages"] and len(page["messages"]) == 2
    previous = (await client.get(url + f"?limit=2&before={page['messages'][0]['id']}")).json()
    assert previous["messages"][0]["text"] == "Synthetic page 1"
    assert (await client.get(url + f"?before={uuid4()}")).status_code == 422
    async with app.state.database.sessions.begin() as db:
        row = await db.get(AiConversation, __import__("uuid").UUID(c["conversationId"]))
        row.expires_at = now() - timedelta(seconds=1)
    assert (await client.get(url)).status_code in (404, 410)
    assert (await client.get("/api/v1/ai/conversations")).json() == []


async def test_rename_is_owner_only_keeps_send_version_and_works_with_ai_off(clients):
    app, actors = clients
    client = actors[0][0]
    app.state.ai.model_override = make_test_model("Synthetic")
    await enable(client)
    c = (await client.post("/api/v1/ai/conversations", json={"botId": "may"}, headers=key())).json()
    url = f"/api/v1/ai/conversations/{c['conversationId']}"
    assert (await actors[1][0].patch(url, json={"title": "Foreign"}, headers=key())).status_code == 404
    assert (await client.patch(url, json={"title": "   "}, headers=key())).status_code == 422
    renamed = await client.patch(url, json={"title": "  Kế hoạch   tuần  "}, headers=key())
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["title"] == "Kế hoạch tuần"
    assert renamed.json()["version"] == c["version"]
    sent = await client.post(
        url + "/messages",
        json={"text": "First synthetic message", "clientMessageId": str(uuid4()), "expectedConversationVersion": 1},
        headers=key(),
    )
    assert sent.status_code == 202, sent.text
    await app.state.ai.runs[__import__("uuid").UUID(sent.json()["runId"])].task
    # A user-chosen title is not replaced by the first-message auto title.
    assert (await client.get(url)).json()["title"] == "Kế hoạch tuần"
    await client.put(
        "/api/v1/consents/AI",
        json={"enabled": False, "expectedVersion": 2, "policyVersion": "v1"},
        headers=key(),
    )
    again = await client.patch(url, json={"title": "Đã tắt AI"}, headers=key())
    assert again.status_code == 200 and again.json()["title"] == "Đã tắt AI"


async def test_legacy_end_keeps_saved_history_and_writes_require_csrf(clients):
    app, actors = clients
    client = actors[0][0]
    app.state.ai.model_override = make_test_model("Synthetic")
    await enable(client)
    c = (await client.post("/api/v1/ai/conversations", json={"botId": "may"}, headers=key())).json()
    url = f"/api/v1/ai/conversations/{c['conversationId']}"
    assert (await client.post(url + "/end")).status_code == 204
    assert (await client.get(url)).status_code == 200
    csrf = client.headers.pop("X-CSRF-Token")
    try:
        assert (await client.delete(url)).status_code == 403
        assert (await client.patch(url, json={"title": "x"}, headers=key())).status_code == 403
    finally:
        client.headers["X-CSRF-Token"] = csrf
    assert (await actors[1][0].delete(url)).status_code in (404, 410)
    assert (await client.get(url)).status_code == 200
    assert (await client.delete(url)).status_code == 204
    assert (await client.get(url)).status_code in (404, 410)


async def test_temporary_turn_digest_is_not_a_plain_text_hash_and_deletion_removes_turns(clients):
    from sqlalchemy import func, select

    from app.ai.models import AiTurn
    from app.core.security import digest
    from app.modules.users.lifecycle import process_deletions

    app, actors = clients
    client, uid = actors[0]
    app.state.ai.model_override = make_test_model("Synthetic")
    c = (
        await client.post(
            "/api/v1/ai/conversations",
            json={"botId": "may", "persistent": False},
            headers=key(),
        )
    ).json()
    body = {"text": "tôi buồn", "clientMessageId": str(uuid4()), "expectedConversationVersion": 1}
    sent = await client.post(
        f"/api/v1/ai/conversations/{c['conversationId']}/messages", json=body, headers=key()
    )
    await app.state.ai.runs[__import__("uuid").UUID(sent.json()["runId"])].task
    plain = digest(json.dumps({"text": "tôi buồn", "moodScope": None}, separators=(",", ":"), ensure_ascii=False))
    async with app.state.database.sessions() as db:
        stored = await db.scalar(select(AiTurn.input_digest).where(AiTurn.user_id == uid))
        version = (await client.get("/api/v1/session")).json().get("dataVersion")
    assert stored and stored != plain and stored != digest('{"text":"tôi buồn","mood_scope":null}')
    async with app.state.database.sessions() as db:
        from app.infrastructure.database.models import User

        version = (await db.get(User, uid)).data_version
    deleted = await client.post(
        "/api/v1/data-deletions", json={"scope": "all_private", "expectedVersion": version}, headers=key()
    )
    assert deleted.status_code == 202, deleted.text
    await process_deletions(app)
    async with app.state.database.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(AiTurn).where(AiTurn.user_id == uid)) == 0


async def test_saved_thread_copies_do_not_accumulate_in_worker_memory(clients):
    app, actors = clients
    client = actors[0][0]
    app.state.ai.model_override = make_test_model("Synthetic")
    await enable(client)
    for _ in range(4):
        c = (await client.post("/api/v1/ai/conversations", json={"botId": "may"}, headers=key())).json()
        sent = await client.post(
            f"/api/v1/ai/conversations/{c['conversationId']}/messages",
            json={"text": "Saved", "clientMessageId": str(uuid4()), "expectedConversationVersion": 1},
            headers=key(),
        )
        await app.state.ai.runs[__import__("uuid").UUID(sent.json()["runId"])].task
    assert not [c for c in app.state.ai.store.conversations.values() if c.persistent]


async def test_event_streams_per_user_are_capped_on_a_worker(clients):
    app, actors = clients
    client = actors[0][0]
    app.state.ai.model_override = make_test_model("Synthetic")
    await enable(client)
    c = (await client.post("/api/v1/ai/conversations", json={"botId": "may"}, headers=key())).json()
    sent = await client.post(
        f"/api/v1/ai/conversations/{c['conversationId']}/messages",
        json={"text": "Saved", "clientMessageId": str(uuid4()), "expectedConversationVersion": 1},
        headers=key(),
    )
    await app.state.ai.runs[__import__("uuid").UUID(sent.json()["runId"])].task
    from app.ai import chat_routes

    app.state.ai.streams.active[actors[0][1]] = chat_routes.MAX_STREAMS_PER_USER
    capped = await client.get(sent.json()["eventsUrl"])
    assert capped.status_code == 429
    app.state.ai.streams.active[actors[0][1]] = 0
    assert "completed" in (await client.get(sent.json()["eventsUrl"])).text
    assert app.state.ai.streams.active.get(actors[0][1], 0) == 0
    # Reservation happens before any await, so a concurrent burst cannot overshoot.
    burst = await asyncio.gather(
        *(client.get(sent.json()["eventsUrl"]) for _ in range(chat_routes.MAX_STREAMS_PER_USER + 4))
    )
    assert all(r.status_code in (200, 429) for r in burst)
    assert app.state.ai.streams.active.get(actors[0][1], 0) == 0
