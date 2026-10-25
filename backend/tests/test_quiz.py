"""T-QUIZ-01: hidden answers before reveal, cooperative scoring, five rounds."""

import json
import re

import pytest

from app.modules.activities import content
from app.modules.activities.quiz import round_points
from tests.activity_helpers import current, enable, ready, respond, started
from tests.social_helpers import open_room

pytestmark = pytest.mark.postgres


def answer_of(view):
    return content.item_by_id("coop_quiz_v1", view["current"]["item"]["id"])


@pytest.mark.parametrize(
    ("correct", "points"),
    [([False, False], 0), ([True, False], 1), ([False, True], 1), ([True, True], 3)],
)
def test_round_points_table(correct, points):
    assert round_points(correct) == points


async def test_correct_answers_stay_hidden_until_both_answer_and_the_team_scores(clients):
    app, actors, _, room = await open_room(clients)
    enable(app)
    (a, _), (b, _) = actors
    sid = (await started(a, b, room, "coop_quiz"))["id"]
    plan = [(True, True), (True, False), (False, False), ("skip", True), (True, True)]
    expected = 0
    for round_number, (mine, theirs) in enumerate(plan, 1):
        view = await current(a, room)
        item = answer_of(view)
        for client in (a, b):
            response = await client.get(f"/api/v1/activities/{sid}")
            body = response.json()
            # Only earlier, revealed rounds may carry answers; the current one never does.
            assert not re.search(r'"correctIndex":\s*\d', json.dumps(body["current"]))
            assert all(row["round"] < round_number for row in body["history"])
            assert item["explanation"] not in response.text
        right, wrong = item["correctIndex"], (item["correctIndex"] + 1) % 4
        first = (
            await respond(a, sid, round_number, skipped=True)
            if mine == "skip"
            else await respond(a, sid, round_number, choice=right if mine else wrong)
        )
        assert first.status_code == 200, first.text
        assert not re.search(r'"correctIndex":\s*\d', json.dumps(first.json()["current"]))
        revealed = await respond(b, sid, round_number, choice=right if theirs else wrong)
        reveal = revealed.json()["current"]["reveal"]
        assert reveal["correctIndex"] == right and reveal["explanation"] == item["explanation"]
        points = round_points([mine is True, theirs is True])
        expected += points
        assert reveal["points"] == points
        assert revealed.json()["score"]["team"] == expected
        await ready(a, sid, round_number)
        await ready(b, sid, round_number)
    final_a, final_b = await current(a, room), await current(b, room)
    assert final_a["state"] == "completed" and final_a["score"]["rounds"] == [3, 1, 0, 1, 3]
    assert final_a["summary"] == final_b["summary"]
    assert final_a["summary"]["teamScore"] == expected == 8 and final_a["summary"]["maxScore"] == 15
    assert [row["reveal"]["correctIndex"] is not None for row in final_a["history"]] == [True] * 5


async def test_quiz_answers_are_choices_not_free_text(clients):
    app, actors, _, room = await open_room(clients)
    enable(app)
    (a, _), (b, _) = actors
    sid = (await started(a, b, room, "coop_quiz"))["id"]
    text_only = await respond(a, sid, 1, text="đáp án tự do")
    assert text_only.status_code == 422
