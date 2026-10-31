"""P2-07: receipt-backed DTO line and real SSE v2 progress, deterministic from DB state."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.ai.chat_routes import persistent_events
from tests.collaboration_helpers import (
    HABIT,
    finish,
    primary,
    receipts,
    setup,
    specialist_model,
    start,
)
from tests.test_ai_events_v2 import events
from tests.test_multi_message_persistence import conversation

SUMMARY = "Nhịp đã gợi ý một thói quen nhỏ. Mây đã dựa vào đó để trả lời bạn."


def state(run="completed", collaboration=None, answers=1):
    row = SimpleNamespace(status=run)
    bubbles = [SimpleNamespace(id=uuid4(), text=f"Phần {i}", cards=[]) for i in range(answers)]
    receipt = None if collaboration is None else SimpleNamespace(
        status=collaboration, edge="nhip_habit_for_may", rule_id="R3", specialist_bot="nhip", used_in_reply=collaboration == "completed")
    return row, bubbles if run == "completed" else [], receipt


def kinds(items):
    return [(e.type, e.data.get("activity")) for e in items]


@pytest.mark.parametrize(
    ("run", "collaboration", "expected"),
    [
        ("running", None, [("progress", None)]),
        ("running", "authorized", [("progress", None), ("progress", "consulting")]),
        ("running", "completed", [("progress", None), ("progress", "consulting"), ("progress", "composing")]),
        ("running", "timeout", [("progress", None), ("progress", "consulting"), ("progress", "composing")]),
        ("running", "denied", [("progress", None)]),
        ("completed", None, [("progress", None), ("final", None), ("completed", None)]),
        ("completed", "completed", [("progress", None), ("progress", "consulting"), ("progress", "composing"),
                                    ("final", None), ("completed", None)]),
        ("completed", "failed", [("progress", None), ("progress", "consulting"), ("progress", "composing"),
                                 ("final", None), ("completed", None)]),
        ("cancelled", "cancelled", [("progress", None), ("progress", "consulting"), ("progress", "composing"),
                                    ("cancelled", None)]),
        ("failed", "discarded", [("progress", None), ("progress", "consulting"), ("progress", "composing"),
                                 ("failed", None)]),
    ],
)
def test_v2_event_list_is_a_function_of_db_state(run, collaboration, expected):
    items = persistent_events(*state(run, collaboration), protocol=2, collaboration_enabled=True)
    assert kinds(items) == expected
    assert [e.seq for e in items] == [str(i) for i in range(1, len(items) + 1)]
    consulting = [e for e in items if e.data.get("activity") == "consulting"]
    assert all(e.data == {"activity": "consulting", "companion": "nhip"} for e in consulting)


def test_prefix_never_changes_as_state_advances():
    timeline = [("running", None), ("running", "authorized"), ("running", "completed"), ("completed", "completed")]
    lists = [persistent_events(*state(r, c), protocol=2, collaboration_enabled=True) for r, c in timeline]
    for before, after in zip(lists, lists[1:], strict=False):
        assert [(e.seq, e.type, e.data) for e in after[: len(before)]] == [(e.seq, e.type, e.data) for e in before]


def test_v1_and_flag_off_keep_the_phase_1_shape():
    for protocol, enabled in ((1, True), (2, False), (1, False)):
        items = persistent_events(*state("completed", "completed"), protocol=protocol, collaboration_enabled=enabled)
        assert kinds(items) == [("progress", None), ("final", None), ("completed", None)]
        assert "collaboration" not in items[1].data


def test_final_carries_the_template_only_for_a_completed_used_receipt():
    for status, summary in (("completed", SUMMARY), ("failed", None), ("timeout", None), ("discarded", None)):
        row, bubbles, receipt = state("completed", status)
        final = next(e for e in persistent_events(row, bubbles, receipt, protocol=2, collaboration_enabled=True)
                     if e.type == "final")
        line = final.data["collaboration"]
        assert (line["summary"] if line else None) == summary
    no_receipt = persistent_events(*state("completed", None), protocol=2, collaboration_enabled=True)
    assert next(e for e in no_receipt if e.type == "final").data["collaboration"] is None


@pytest.mark.postgres
async def test_live_stream_and_reconnect_at_every_cursor(clients):
    app, [(client, _), _] = clients
    await setup(app, client)
    app.state.ai.specialist_model_override = specialist_model(HABIT)
    url = await conversation(client, "may")
    run = await finish(await start(app, client, url, "Mình mất ngủ", model=primary("Một.", "Hai.")))
    full = events((await client.get(f"/api/v1/ai/runs/{run.id}/events?protocol=2")).text)
    assert [(e["type"], e["data"].get("activity")) for e in full] == [
        ("progress", None), ("progress", "consulting"), ("progress", "composing"), ("final", None), ("completed", None)]
    assert full[3]["data"]["collaboration"] == {"kind": "nhip_habit_for_may", "companions": ["nhip", "may"],
                                                "summary": SUMMARY}
    assert [m["text"] for m in full[3]["data"]["messages"]] == ["Một.", "Hai."]
    for cursor in range(6):
        resumed = events((await client.get(f"/api/v1/ai/runs/{run.id}/events?protocol=2&afterSeq={cursor}")).text)
        assert resumed == full[cursor:]
    gap = await client.get(f"/api/v1/ai/runs/{run.id}/events?protocol=2&afterSeq=6")
    assert gap.status_code == 409
    v1 = events((await client.get(f"/api/v1/ai/runs/{run.id}/events")).text)
    assert [e["type"] for e in v1] == ["progress", "final", "completed"]
    assert set(v1[1]["data"]) == {"text", "cards"}
    assert (await client.get(f"/api/v1/ai/runs/{run.id}/events?afterSeq=4")).status_code == 409


@pytest.mark.postgres
async def test_dto_line_disappears_when_the_flag_is_turned_off(clients):
    app, [(client, _), _] = clients
    await setup(app, client)
    app.state.ai.specialist_model_override = specialist_model(HABIT)
    url = await conversation(client, "may")
    run = await finish(await start(app, client, url, "Mình mất ngủ", model=primary("Một.", "Hai.")))
    assert [r.status for r in await receipts(app, run.id)] == ["completed"]
    view = (await client.get(url)).json()
    assert [m["collaboration"] is not None for m in view["messages"]] == [False, True, False]
    app.state.settings.ai_collaboration_enabled = False
    view = (await client.get(url)).json()
    assert all(m["collaboration"] is None for m in view["messages"])
