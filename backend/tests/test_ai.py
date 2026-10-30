import json
from uuid import uuid4

import pytest


def test_ephemeral_store_checks_owner_session_bot_and_idle_expiry_on_every_read():
    from app.ai.store import ConversationStore
    from app.core.errors import DomainError

    clock = [10.0]
    store = ConversationStore(clock=lambda: clock[0], ttl_seconds=5)
    c = store.create("owner", "session", "may")
    assert store.get(c.id, "owner", "session").bot_id == "may"
    with pytest.raises(DomainError) as denied:
        store.get(c.id, "other", "session")
    assert denied.value.status == 404
    clock[0] = 16.0
    with pytest.raises(DomainError) as expired:
        store.get(c.id, "owner", "session")
    assert expired.value.status == 410


def test_ai_output_rejects_forged_action_receipts_and_unknown_cards():
    from pydantic import ValidationError

    from app.ai.schemas import AiOutput

    with pytest.raises(ValidationError):
        AiOutput.model_validate({"text": "Saved", "cards": [], "receipt": {"status": "succeeded"}})
    with pytest.raises(ValidationError):
        AiOutput.model_validate(
            {"text": "hi", "cards": [{"kind": "execute_sql", "sql": "select *"}]}
        )


@pytest.mark.postgres
async def test_ai_disabled_is_explicit_and_never_falls_back_to_scripted_reply(clients):
    _, actors = clients
    a, _ = actors[0]
    await a.put(
        "/api/v1/consents/AI",
        json={"enabled": True, "expectedVersion": 1, "policyVersion": "v1"},
        headers={"Idempotency-Key": str(uuid4())},
    )
    response = await a.post(
        "/api/v1/ai/conversations", json={"botId": "may"}, headers={"Idempotency-Key": str(uuid4())}
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "AI_UNAVAILABLE"


@pytest.mark.postgres
async def test_sdk_fake_model_full_route_stream_isolation_and_no_transcript_in_database(clients):
    from sqlalchemy import text

    from tests.fakes import make_test_model

    app, actors = clients
    app.state.ai.model_override = make_test_model("Một phản hồi tổng hợp từ SDK.")
    a, _ = actors[0]
    c = await a.post(
        "/api/v1/ai/conversations", json={"botId": "may"}, headers={"Idempotency-Key": str(uuid4())}
    )
    assert c.status_code == 201, c.text
    conversation = c.json()
    assert conversation["persistent"] is True
    canary = "PRIVATE-CANARY-DO-NOT-PERSIST"
    accepted = await a.post(
        f"/api/v1/ai/conversations/{conversation['conversationId']}/messages",
        json={"text": canary, "clientMessageId": str(uuid4()), "expectedConversationVersion": 1},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert accepted.status_code == 202, accepted.text
    stream = await a.get(accepted.json()["eventsUrl"])
    assert stream.status_code == 200
    events = [
        json.loads(line[6:]) for line in stream.text.splitlines() if line.startswith("data: ")
    ]
    assert any(
        e["type"] == "final" and e["data"]["text"] == "Một phản hồi tổng hợp từ SDK."
        for e in events
    )
    assert events[-1]["type"] == "completed"
    view = (await a.get(f"/api/v1/ai/conversations/{conversation['conversationId']}")).json()
    assert [m["actor"] for m in view["messages"]] == ["self", "bot"]
    assert (
        await actors[1][0].get(f"/api/v1/ai/conversations/{conversation['conversationId']}")
    ).status_code == 404
    async with app.state.database.sessions() as db:
        rows = await db.execute(text("select row_to_json(r)::text from moodprint.ai_runs r"))
        assert canary not in "".join(rows.scalars())
    # Saved history is the default, so clearing worker memory does not drop the transcript.
    app.state.ai.store.clear()
    restored = await a.get(f"/api/v1/ai/conversations/{conversation['conversationId']}")
    assert restored.status_code == 200, restored.text
    assert canary in restored.text


@pytest.mark.postgres
async def test_capacity_failure_before_emission_is_not_recorded_as_completed(clients):
    from app.core.errors import DomainError
    from app.infrastructure.database.models import AiRun
    from tests.fakes import make_test_model

    app, actors = clients
    runtime = app.state.ai
    runtime.model_override = make_test_model("Synthetic bounded reply.")
    calls = 0

    def capacity(conversation_id, extra_bytes):
        nonlocal calls
        calls += 1
        if calls == 3:
            raise DomainError(429, "CONTEXT_LIMIT", "Synthetic concurrent capacity change")

    runtime.check_capacity = capacity
    client = actors[0][0]
    await client.put(
        "/api/v1/consents/AI",
        json={"enabled": True, "expectedVersion": 1, "policyVersion": "v1"},
        headers={"Idempotency-Key": str(uuid4())},
    )
    conversation = (
        await client.post(
            "/api/v1/ai/conversations",
            json={"botId": "may"},
            headers={"Idempotency-Key": str(uuid4())},
        )
    ).json()
    accepted = await client.post(
        f"/api/v1/ai/conversations/{conversation['conversationId']}/messages",
        json={
            "text": "Synthetic input",
            "clientMessageId": str(uuid4()),
            "expectedConversationVersion": 1,
        },
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert accepted.status_code == 202
    stream = await client.get(accepted.json()["eventsUrl"])
    events = [
        json.loads(line[6:]) for line in stream.text.splitlines() if line.startswith("data: ")
    ]
    assert events[-1]["type"] == "failed" and not any(event["type"] == "final" for event in events)
    await runtime.runs[next(iter(runtime.runs))].task
    from uuid import UUID

    async with app.state.database.sessions() as db:
        row = await db.get(AiRun, UUID(accepted.json()["runId"]))
        assert row.status == "failed"
