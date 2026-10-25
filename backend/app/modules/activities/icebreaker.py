"""Icebreaker (icebreaker-v1): three questions, independent answers, reciprocal reveal.

A round is revealed once both have answered or skipped; a participant sees the peer's
answer only if they answered themselves (06 section 4). Mutual "next" advances.
"""

import random
from datetime import datetime
from typing import Any

from app.modules.activities import content
from app.modules.activities.machine import (
    HANDLERS,
    Command,
    MachineError,
    NoChange,
    ResponseState,
    SessionState,
    finish,
)

BANK = "icebreaker_v1"
TEXT_LIMIT = 140


def pick_items(session_id: Any) -> list[str]:
    """One question per tier, seeded by the session id (deterministic, never repeated)."""
    rng = random.Random(str(session_id))
    items = content.load_bank(BANK)
    return [
        rng.choice([item for item in items if item["tier"] == tier])["id"] for tier in content.TIERS
    ]


def round_item(s: SessionState, round_number: int) -> dict[str, Any]:
    ids = s.content.get("items", [])
    return content.item_by_id(s.content.get("bank", BANK), ids[round_number - 1])


def normalize(payload: dict[str, Any], item: dict[str, Any]) -> tuple[int | None, str | None, bool]:
    if payload.get("skipped"):
        return None, None, True
    choice = payload.get("choice")
    text = (payload.get("text") or "").strip() or None
    if choice is not None and choice not in range(len(item["options"])):
        raise MachineError("INVALID_RESPONSE", 422)
    if text is not None and (not item.get("allowText", True) or len(text) > TEXT_LIMIT):
        raise MachineError("INVALID_RESPONSE", 422)
    if choice is None and text is None:
        raise MachineError("INVALID_RESPONSE", 422)
    return choice, text, False


def record_response(s: SessionState, cmd: Command, now: datetime, item: dict[str, Any]) -> None:
    """Shared by turn-based kinds: idempotent per (participant, round), CAS on the round."""
    if cmd.round is None:
        raise MachineError("ROUND_CHANGED")
    key = (cmd.actor, cmd.round)
    existing = s.responses.get(key)
    choice, text, skipped = normalize(dict(cmd.payload), item)
    if existing is not None:
        if (existing.choice, existing.text, existing.skipped) == (choice, text, skipped):
            raise NoChange
        raise MachineError("RESPONSE_CONFLICT")
    if cmd.round != s.round or s.phase != "answering":
        raise MachineError("ROUND_CHANGED")
    s.responses[key] = ResponseState(cmd.actor, cmd.round, item["id"], choice, text, skipped, now)


def both_answered(s: SessionState) -> bool:
    return all((uid, s.round) in s.responses for uid in s.participants)


def mark_ready(s: SessionState, cmd: Command, now: datetime, total: int) -> bool:
    """Returns True when both are ready and the session moved on (or completed)."""
    if cmd.round != s.round or s.phase != "revealed":
        raise MachineError("ROUND_CHANGED")
    participant = s.participants[cmd.actor]
    if participant.ready_round >= s.round:
        raise NoChange
    participant.ready_round = s.round
    if any(p.ready_round < s.round for p in s.participants.values()):
        return False
    if s.round >= total:
        finish(s, "completed", "completed", now)
    else:
        s.round, s.phase = s.round + 1, "answering"
    return True


class Icebreaker:
    total = 3

    def on_accept(self, s: SessionState, now: datetime) -> None:
        s.content = {"bank": BANK, "items": pick_items(s.id)}
        s.round, s.phase = 1, "answering"

    def act(self, s: SessionState, cmd: Command, now: datetime) -> None:
        if cmd.op == "respond":
            record_response(s, cmd, now, round_item(s, cmd.round or s.round))
            if both_answered(s):
                s.phase = "revealed"
        elif cmd.op == "ready":
            mark_ready(s, cmd, now, self.total)
        else:
            raise MachineError("ACTIVITY_CHANGED")

    def tick(self, s: SessionState, now: datetime) -> bool:
        return False

    def deadline(self, s: SessionState, now: datetime) -> datetime | None:
        return None

    def on_end(self, s: SessionState, now: datetime) -> None:
        return None


HANDLERS["icebreaker"] = Icebreaker()
