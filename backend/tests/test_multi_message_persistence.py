"""P1-05: N validated bubbles persist atomically, keep version == max(sequence), page as groups."""

import asyncio
import json
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.ai.context import build_history
from app.ai.schemas import AIMessage
from tests.fakes import ScriptedModel, make_test_model, message_output
from tests.test_chat_persistence import enable, key
from tests.test_context_privacy import turn


def bubbles(*texts) -> ScriptedModel:
    payload = {"messages": [{"text": text, "cards": []} for text in texts]}
    return ScriptedModel([[message_output(json.dumps(payload, ensure_ascii=False))]])


async def conversation(client, bot="may", persistent=None):
    body = {"botId": bot} if persistent is None else {"botId": bot, "persistent": persistent}
    created = await client.post("/api/v1/ai/conversations", json=body, headers=key())
    assert created.status_code == 201, created.text
    return f"/api/v1/ai/conversations/{created.json()['conversationId']}"


async def db_rows(app, conversation_id):
    from app.ai.models import AiMessageRecord

    async with app.state.database.sessions() as db:
        return (
            await db.scalars(
                select(AiMessageRecord)
                .where(AiMessageRecord.conversation_id == conversation_id)
                .order_by(AiMessageRecord.sequence)
            )
        ).all()


@pytest.fixture
async def multi(clients):
    app, actors = clients
    app.state.settings.ai_multi_message_enabled = True
    client, _ = actors[0]
    await enable(client)
    app.state.ai.model_override = make_test_model("ready")
    return app, client


@pytest.mark.postgres
async def test_three_bubbles_share_run_and_take_consecutive_sequences(multi):
    app, client = multi
    url = await conversation(client)
    run = await turn(app, client, url, "Hôm nay mình hơi uể oải", bubbles("Một", "Hai", "Ba"))
    rows = await db_rows(app, UUID(url.rsplit("/", 1)[1]))
    bot = [row for row in rows if row.actor == "bot"]
    assert [(row.sequence, row.part_index, row.part_count, row.run_id) for row in bot] == [
        (3, 0, 3, run.id), (4, 1, 3, run.id), (5, 2, 3, run.id)
    ]
    view = (await client.get(url)).json()
    assert view["version"] == 5 == max(row.sequence for row in rows)
    assert [(m["actor"], m["text"], m["partIndex"], m["partCount"], m["origin"], m["proactiveSlot"])
            for m in view["messages"]] == [
        ("self", "Hôm nay mình hơi uể oải", 0, 1, "user", None),
        ("bot", "Một", 0, 3, "user", None),
        ("bot", "Hai", 1, 3, "user", None),
        ("bot", "Ba", 2, 3, "user", None),
    ]
    # The in-memory publication uses the persisted identities.
    assert {m["id"] for m in view["messages"][1:]} == {str(row.id) for row in bot}


@pytest.mark.postgres
async def test_temporary_chat_appends_all_bubbles_in_order(multi):
    app, client = multi
    url = await conversation(client, persistent=False)
    await turn(app, client, url, "Chào", bubbles("Xin chào", "Mình đây"))
    view = (await client.get(url)).json()
    assert view["version"] == 4
    assert [(m["text"], m["partIndex"], m["partCount"]) for m in view["messages"]] == [
        ("Chào", 0, 1), ("Xin chào", 0, 2), ("Mình đây", 1, 2)
    ]


@pytest.mark.postgres
async def test_flag_off_persists_exactly_one_part(clients):
    app, actors = clients
    client, _ = actors[0]
    await enable(client)
    app.state.ai.model_override = make_test_model("ready")
    url = await conversation(client)
    await turn(app, client, url, "Chào", make_test_model("Một tin duy nhất"))
    rows = await db_rows(app, UUID(url.rsplit("/", 1)[1]))
    assert [(row.actor, row.part_index, row.part_count) for row in rows] == [("self", 0, 1), ("bot", 0, 1)]


@pytest.mark.postgres
async def test_cancel_before_commit_leaves_no_bubbles(multi):
    app, client = multi
    url = await conversation(client)
    model = ScriptedModel(
        [[message_output(json.dumps({"messages": [{"text": "Không bao giờ hiện", "cards": []}]}))]], hold=True
    )
    app.state.ai.model_override = model
    accepted = await client.post(
        url + "/messages",
        json={"text": "Giữ lại", "clientMessageId": str(uuid4()), "expectedConversationVersion": 1},
        headers=key(),
    )
    assert accepted.status_code == 202, accepted.text
    await asyncio.wait_for(model.started.wait(), 3)
    cancelled = await client.post(f"/api/v1/ai/runs/{accepted.json()['runId']}/cancel", json={"expectedVersion": 1})
    assert cancelled.status_code == 200, cancelled.text
    model.release.set()
    rows = await db_rows(app, UUID(url.rsplit("/", 1)[1]))
    assert [row.actor for row in rows] == ["self"]
    assert (await client.get(url)).json()["version"] == 2


@pytest.mark.postgres
async def test_page_boundary_never_splits_a_bubble_group(multi):
    app, client = multi
    url = await conversation(client)
    await turn(app, client, url, "Một", bubbles("Đáp một"))  # seq 2-3
    await turn(app, client, url, "Hai", bubbles("A", "B", "C"))  # seq 4-7
    page = (await client.get(url + "?limit=2")).json()
    # The two newest rows are parts 1 and 2; part 0 is pulled in so the group is whole.
    assert [m["text"] for m in page["messages"]] == ["A", "B", "C"]
    assert page["hasMoreMessages"] is True
    older = (await client.get(url + f"?limit=2&before={page['messages'][0]['id']}")).json()
    assert [m["text"] for m in older["messages"]] == ["Đáp một", "Hai"]
    assert older["hasMoreMessages"] is True
    oldest = (await client.get(url + f"?limit=2&before={older['messages'][0]['id']}")).json()
    assert [m["text"] for m in oldest["messages"]] == ["Một"]
    assert oldest["hasMoreMessages"] is False


@pytest.mark.postgres
async def test_version_equals_max_sequence_and_sequences_are_contiguous(multi):
    app, client = multi
    url = await conversation(client)
    for texts in (("1",), ("2a", "2b"), ("3a", "3b", "3c", "3d"), ("4",), ("5a", "5b")):
        await turn(app, client, url, "Tiếp " + texts[0], bubbles(*texts))
        rows = await db_rows(app, UUID(url.rsplit("/", 1)[1]))
        sequences = [row.sequence for row in rows]
        # A new conversation starts at version 1 with no message, so sequences start at 2.
        assert sequences == list(range(2, len(rows) + 2))
        assert (await client.get(url)).json()["version"] == max(sequences)


@pytest.mark.postgres
async def test_export_carries_part_and_origin_fields(multi):
    app, client = multi
    url = await conversation(client)
    await turn(app, client, url, "Xuất", bubbles("X", "Y"))
    exported = (await client.get(url + "/export")).json()
    assert [(m["text"], m["partIndex"], m["partCount"], m["origin"]) for m in exported["messages"]] == [
        ("Xuất", 0, 1, "user"), ("X", 0, 2, "user"), ("Y", 1, 2, "user")
    ]


def _message(actor, text, run):
    return AIMessage(id=uuid4(), actor=actor, text=text, run_id=run)


def test_history_merges_adjacent_bubbles_of_one_run_before_bounding():
    first, second = uuid4(), uuid4()
    messages = [
        _message("self", "Chào", first),
        _message("bot", "Một", first),
        _message("bot", "Hai", first),
        _message("self", "Rồi sao", second),
        _message("bot", "Ba", second),
    ]
    assert build_history(messages) == [
        {"role": "user", "content": "Chào"},
        {"role": "assistant", "content": "Một\n\nHai"},
        {"role": "user", "content": "Rồi sao"},
        {"role": "assistant", "content": "Ba"},
    ]


def test_history_bound_counts_turns_not_bubbles():
    messages = []
    for index in range(12):
        run = uuid4()
        messages += [_message("self", f"Hỏi {index}", run)] + [
            _message("bot", f"Đáp {index}.{part}", run) for part in range(4)
        ]
    history = build_history(messages)
    # 12 turns x (1 user + 1 merged assistant) = 24 entries: no bubble consumed the window.
    assert len(history) == 24
    assert history[0] == {"role": "user", "content": "Hỏi 0"}
