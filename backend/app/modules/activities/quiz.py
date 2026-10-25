"""Cooperative quiz (coop_quiz-v1): five shared questions, one team score.

correctIndex and the explanation are only ever projected after a round is revealed.
Scoring per round: +1 per correct participant, +1 team bonus when both are correct.
"""

import random
from datetime import datetime
from typing import Any

from app.modules.activities import content
from app.modules.activities.icebreaker import both_answered, mark_ready, record_response
from app.modules.activities.machine import HANDLERS, Command, MachineError, SessionState

BANK = "coop_quiz_v1"
ROUNDS = 5
MAX_PER_ROUND = 3


def pick_items(session_id: Any) -> list[str]:
    """Five questions from at least four categories when possible, seeded by session."""
    rng = random.Random(str(session_id))
    items = list(content.load_bank(BANK))
    rng.shuffle(items)
    chosen: list[dict[str, Any]] = []
    for item in items:
        if len(chosen) == ROUNDS:
            break
        if sum(other["category"] == item["category"] for other in chosen) < 2:
            chosen.append(item)
    return [item["id"] for item in chosen]


def round_item(s: SessionState, round_number: int) -> dict[str, Any]:
    return content.item_by_id(BANK, s.content["items"][round_number - 1])


def round_points(correct: list[bool]) -> int:
    hits = sum(correct)
    return hits + (1 if correct and all(correct) else 0)


class CoopQuiz:
    def on_accept(self, s: SessionState, now: datetime) -> None:
        s.content = {"bank": BANK, "items": pick_items(s.id)}
        s.score = {"team": 0, "max": ROUNDS * MAX_PER_ROUND, "rounds": []}
        s.round, s.phase = 1, "answering"

    def act(self, s: SessionState, cmd: Command, now: datetime) -> None:
        if cmd.op == "respond":
            item = round_item(s, cmd.round or s.round)
            payload = dict(cmd.payload)
            payload.pop("text", None)  # quiz answers are choices or skips only
            record_response(s, Command(cmd.op, cmd.actor, cmd.round, payload), now, item)
            if both_answered(s):
                s.phase = "revealed"
                correct = [
                    s.responses[(uid, s.round)].choice == item["correctIndex"]
                    and not s.responses[(uid, s.round)].skipped
                    for uid in s.participants
                ]
                score = dict(s.score or {"team": 0, "max": ROUNDS * MAX_PER_ROUND, "rounds": []})
                points = round_points(correct)
                score["rounds"] = [*score["rounds"], points]
                score["team"] = score["team"] + points
                s.score = score
        elif cmd.op == "ready":
            mark_ready(s, cmd, now, ROUNDS)
        else:
            raise MachineError("ACTIVITY_CHANGED")

    def tick(self, s: SessionState, now: datetime) -> bool:
        return False

    def deadline(self, s: SessionState, now: datetime) -> datetime | None:
        return None

    def on_end(self, s: SessionState, now: datetime) -> None:
        return None


HANDLERS["coop_quiz"] = CoopQuiz()
