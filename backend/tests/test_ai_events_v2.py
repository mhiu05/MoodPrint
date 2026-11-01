"""P1-06: ai-events-v1 stays the default (joined bubbles); ai-events-v2 via ?protocol=2."""

import json

import pytest
from sqlalchemy import select

from tests.fakes import make_test_model
from tests.test_chat_persistence import enable
from tests.test_context_privacy import turn
from tests.test_multi_message_persistence import bubbles, conversation


def events(body: str) -> list[dict]:
    return [
        json.loads(line.removeprefix("data: "))
        for line in body.splitlines()
        if line.startswith("data: ")
    ]


async def stream(client, run_id, query=""):
    response = await client.get(f"/api/v1/ai/runs/{run_id}/events{query}")
    return response


@pytest.fixture
async def chat(clients):
    app, actors = clients
    client, _ = actors[0]
    await enable(client)
    app.state.ai.model_override = make_test_model("ready")
    return app, client


async def bot_ids(app, run_id):
    from app.ai.models import AiMessageRecord

    async with app.state.database.sessions() as db:
        return [
            str(identity)
            for identity in (
                await db.scalars(
                    select(AiMessageRecord.id)
                    .where(AiMessageRecord.run_id == run_id, AiMessageRecord.actor == "bot")
                    .order_by(AiMessageRecord.part_index)
                )
            ).all()
        ]


@pytest.mark.postgres
@pytest.mark.parametrize("persistent", [True, False])
async def test_v1_single_bubble_final_is_byte_for_byte_unchanged(chat, persistent):
    app, client = chat
    url = await conversation(client, persistent=persistent)
    run = await turn(app, client, url, "Chào", make_test_model("Một tin duy nhất"))
    body = (await stream(client, run.id)).text
    # Persistent replay is fixed at seq 1-3; a temporary run replays its live events.
    seq = next(event["seq"] for event in events(body) if event["type"] == "final")
    assert seq == "2" or not persistent
    expected_final = (
        f'id: {seq}\nevent: final\ndata: {{"version":"ai-events-v1","seq":"{seq}","type":"final",'
        '"data":{"text":"Một tin duy nhất","cards":[]}}\n\n'
    )
    assert expected_final in body
    done = int(seq) + 1
    assert (
        f'id: {done}\nevent: completed\ndata: {{"version":"ai-events-v1","seq":"{done}",'
        '"type":"completed","data":{}}'
    ) in body


@pytest.mark.postgres
@pytest.mark.parametrize("persistent", [True, False])
async def test_v1_joins_bubbles_for_old_clients(chat, persistent):
    app, client = chat
    app.state.settings.ai_multi_message_enabled = True
    url = await conversation(client, persistent=persistent)
    run = await turn(app, client, url, "Chào", bubbles("Một", "Hai", "Ba"))
    final = [event for event in events((await stream(client, run.id)).text) if event["type"] == "final"]
    assert [(event["version"], event["data"]) for event in final] == [
        ("ai-events-v1", {"text": "Một\n\nHai\n\nBa", "cards": []})
    ]


@pytest.mark.postgres
async def test_v2_persistent_final_carries_ordered_bubbles_with_saved_ids(chat):
    app, client = chat
    app.state.settings.ai_multi_message_enabled = True
    url = await conversation(client)
    run = await turn(app, client, url, "Chào", bubbles("Một", "Hai"))
    received = events((await stream(client, run.id, "?protocol=2")).text)
    assert {event["version"] for event in received} == {"ai-events-v2"}
    assert [event["type"] for event in received] == ["progress", "final", "completed"]
    final = received[1]["data"]
    assert final["partCount"] == 2
    assert [(m["partIndex"], m["text"], m["cards"]) for m in final["messages"]] == [(0, "Một", []), (1, "Hai", [])]
    assert [m["messageId"] for m in final["messages"]] == await bot_ids(app, run.id)
    assert set(final["messages"][0]) == {"messageId", "partIndex", "text", "cards"}


@pytest.mark.postgres
async def test_v2_temporary_final_uses_published_ids(chat):
    app, client = chat
    app.state.settings.ai_multi_message_enabled = True
    url = await conversation(client, persistent=False)
    run = await turn(app, client, url, "Chào", bubbles("Một", "Hai"))
    final = [e for e in events((await stream(client, run.id, "?protocol=2")).text) if e["type"] == "final"][0]
    view = (await client.get(url)).json()
    assert [m["messageId"] for m in final["data"]["messages"]] == [m["id"] for m in view["messages"][1:]]


@pytest.mark.postgres
async def test_v2_single_bubble_is_one_message(chat):
    app, client = chat
    url = await conversation(client)
    run = await turn(app, client, url, "Chào", make_test_model("Một"))
    final = [e for e in events((await stream(client, run.id, "?protocol=2")).text) if e["type"] == "final"][0]
    assert final["data"]["partCount"] == 1
    assert [m["text"] for m in final["data"]["messages"]] == ["Một"]


@pytest.mark.postgres
@pytest.mark.parametrize(("after", "types"), [(0, ["progress", "final", "completed"]), (1, ["final", "completed"]),
                                              (2, ["completed"]), (3, [])])
async def test_v2_replay_respects_after_seq(chat, after, types):
    app, client = chat
    url = await conversation(client)
    run = await turn(app, client, url, "Chào", make_test_model("Một"))
    received = events((await stream(client, run.id, f"?protocol=2&afterSeq={after}")).text)
    assert [event["type"] for event in received] == types


@pytest.mark.postgres
async def test_v2_reconnect_with_last_event_id_and_cursor_gap(chat):
    app, client = chat
    url = await conversation(client)
    run = await turn(app, client, url, "Chào", make_test_model("Một"))
    resumed = await client.get(f"/api/v1/ai/runs/{run.id}/events?protocol=2", headers={"Last-Event-ID": "2"})
    assert [event["type"] for event in events(resumed.text)] == ["completed"]
    gap = await stream(client, run.id, "?protocol=2&afterSeq=4")
    assert gap.status_code == 409 and gap.json()["error"]["code"] == "CURSOR_GAP"


@pytest.mark.postgres
async def test_unknown_protocol_is_rejected(chat):
    app, client = chat
    url = await conversation(client)
    run = await turn(app, client, url, "Chào", make_test_model("Một"))
    assert (await stream(client, run.id, "?protocol=3")).status_code == 422


def test_openapi_documents_both_final_shapes():
    from app.core.config import Settings
    from app.main import create_app

    schemas = create_app(Settings(_env_file=None)).openapi()["components"]["schemas"]
    assert schemas["AIEvent"]["properties"]["version"]["enum"] == ["ai-events-v1", "ai-events-v2"]
    final = schemas["AIFinalV2"]
    assert set(final["properties"]) == {"partCount", "messages"}
    assert set(schemas["AIReplyBubble"]["properties"]) == {"messageId", "partIndex", "text", "cards"}
