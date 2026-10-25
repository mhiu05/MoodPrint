"""T-ICE-01, T-ACT-06: independent answers, reciprocal reveal, mutual next, feedback."""

import pytest

from tests.activity_helpers import command, current, enable, ready, respond, started
from tests.social_helpers import key, open_room

pytestmark = pytest.mark.postgres


async def setup(clients):
    app, actors, _, room = await open_room(clients)
    enable(app)
    (a, _), (b, _) = actors
    view = await started(a, b, room)
    return a, b, room, view["id"]


async def test_peer_answer_is_hidden_until_both_have_answered(clients):
    a, b, room, sid = await setup(clients)
    view = await current(a, room)
    assert view["current"]["item"]["prompt"] and view["progress"] == {
        "round": 1,
        "totalRounds": 3,
        "phase": "answering",
    }
    sent = await respond(a, sid, 1, text="BÍ-MẬT-CỦA-A", choice=0)
    assert sent.status_code == 200, sent.text
    assert sent.json()["current"]["selfResponse"]["text"] == "BÍ-MẬT-CỦA-A"
    raw = (await b.get(f"/api/v1/activities/{sid}")).text
    assert "BÍ-MẬT-CỦA-A" not in raw
    assert (await current(b, room))["current"]["peerSubmitted"] is True
    revealed = await respond(b, sid, 1, choice=1)
    reveal = revealed.json()["current"]["reveal"]
    assert reveal["peer"]["text"] == "BÍ-MẬT-CỦA-A" and reveal["self"]["choice"] == 1
    assert (await current(a, room))["current"]["reveal"]["peer"]["choice"] == 1


async def test_reciprocal_reveal_hides_the_peer_answer_from_a_skipper(clients):
    a, b, room, sid = await setup(clients)
    await respond(a, sid, 1, text="CÂU-TRẢ-LỜI-A")
    await respond(b, sid, 1, skipped=True)
    skipper = await current(b, room)
    assert skipper["current"]["reveal"]["peer"] == "hidden"
    assert "CÂU-TRẢ-LỜI-A" not in str(skipper)
    answerer = await current(a, room)
    assert answerer["current"]["reveal"]["peer"] == "skipped"


async def test_retries_are_idempotent_conflicts_and_wrong_rounds_are_refused(clients):
    a, b, room, sid = await setup(clients)
    first = await respond(a, sid, 1, choice=2)
    again = await respond(a, sid, 1, choice=2)  # a new key, same payload: same view
    assert again.status_code == 200
    assert again.json()["version"] == first.json()["version"]
    conflict = await respond(a, sid, 1, choice=1)
    assert conflict.status_code == 409 and conflict.json()["error"]["code"] == "RESPONSE_CONFLICT"
    wrong = await respond(b, sid, 2, choice=0)
    assert wrong.status_code == 409 and wrong.json()["error"]["code"] == "ROUND_CHANGED"
    headers = key()
    one = await respond(b, sid, 1, headers=headers, choice=0)
    two = await respond(b, sid, 1, headers=headers, choice=0)
    assert one.status_code == two.status_code == 200
    invalid = await respond(a, sid, 1)
    assert invalid.status_code in (409, 422)


async def test_rounds_advance_only_when_both_are_ready_then_complete_with_feedback(clients):
    a, b, room, sid = await setup(clients)
    for round_number in (1, 2, 3):
        await respond(a, sid, round_number, choice=0)
        await respond(b, sid, round_number, choice=1)
        first = await ready(a, sid, round_number)
        assert first.json()["progress"]["round"] == round_number  # waits for the peer
        assert first.json()["peer"]["readyRound"] == round_number - 1
        repeat = await ready(a, sid, round_number)
        assert repeat.status_code == 200
        second = await ready(b, sid, round_number)
        assert second.status_code == 200, second.text
    done = await current(a, room)
    assert done["state"] == "completed" and done["summary"]["answeredTogether"] == 3
    assert len(done["history"]) == 3 and done["history"][0]["reveal"]["peer"]["choice"] == 1
    rated = await a.post(
        f"/api/v1/activities/{sid}/feedback", json={"rating": "liked"}, headers=key()
    )
    assert rated.status_code == 200, rated.text
    mine, theirs = await current(a, room), await current(b, room)
    assert mine["self"]["feedbackGiven"] is True
    assert theirs["self"]["feedbackGiven"] is False
    assert "liked" not in str(theirs) and "feedback" not in theirs["peer"]


async def test_feedback_before_completion_is_refused(clients):
    a, b, room, sid = await setup(clients)
    early = await a.post(
        f"/api/v1/activities/{sid}/feedback", json={"rating": "liked"}, headers=key()
    )
    assert early.status_code == 409 and early.json()["error"]["code"] == "NOT_COMPLETED"


async def test_ending_mid_round_keeps_only_revealed_history(clients):
    a, b, room, sid = await setup(clients)
    await respond(a, sid, 1, text="CHỈ-A-BIẾT")
    view = await current(a, room)
    ended = await command(b, sid, "end", view["version"])
    assert ended.status_code == 200 and ended.json()["history"] == []
    assert "CHỈ-A-BIẾT" not in ended.text
