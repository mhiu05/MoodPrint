"""Shared Focus (focus-v1): a server-timed Pomodoro for two (06 section 6).

The timer is plain JSON on the session; every function here is pure and takes `now`.
Phases: starting (5 s) -> focus -> break -> focus ... -> done (the final break is skipped).
Summary minutes are focus time intersected with each participant's presence.
"""

import copy
import math
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from app.modules.activities.definitions import FOCUS_MAX_CYCLES, FOCUS_PLANS
from app.modules.activities.machine import (
    HANDLERS,
    Command,
    MachineError,
    NoChange,
    SessionState,
    finish,
)

STARTING_SECONDS = 5
PAUSE_LIMIT = timedelta(minutes=15)
AWAY_LIMIT = timedelta(minutes=10)
MAX_INTERVALS = 20
Timer = dict[str, Any]


def _ts(value: datetime) -> str:
    return value.isoformat()


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def validate_options(options: dict[str, Any]) -> dict[str, Any]:
    plan = list(options.get("plan") or FOCUS_PLANS[0])
    cycles = options.get("cycles", 1)
    if tuple(plan) not in FOCUS_PLANS or not isinstance(cycles, int):
        raise MachineError("INVALID_RESPONSE", 422)
    if not 1 <= cycles <= FOCUS_MAX_CYCLES:
        raise MachineError("INVALID_RESPONSE", 422)
    return {"plan": plan, "cycles": cycles}


def start(
    options: dict[str, Any],
    participants: tuple[UUID, UUID],
    now: datetime,
    test_seconds: int | None = None,
) -> Timer:
    plan = validate_options(options)
    focus_sec = test_seconds or plan["plan"][0] * 60
    break_sec = max(1, test_seconds // 5) if test_seconds else plan["plan"][1] * 60
    return {
        **plan,
        "focusSec": focus_sec,
        "breakSec": break_sec,
        "phase": "starting",
        "cycle": 1,
        "phaseStartedAt": _ts(now),
        "phaseDurationSec": STARTING_SECONDS,
        "pausedAt": None,
        "pausedRemainingSec": None,
        "pausedBy": None,
        "presence": {str(uid): [[_ts(now), None]] for uid in participants},
        "focusWindows": [],
        "awaySince": None,
    }


def phase_end(timer: Timer) -> datetime:
    return _dt(timer["phaseStartedAt"]) + timedelta(seconds=timer["phaseDurationSec"])


def remaining(timer: Timer, now: datetime) -> int:
    if timer["pausedAt"]:
        return timer["pausedRemainingSec"]
    return max(0, math.ceil((phase_end(timer) - now).total_seconds()))


def _close_window(timer: Timer, at: datetime) -> None:
    if timer["focusWindows"] and timer["focusWindows"][-1][1] is None:
        timer["focusWindows"][-1][1] = _ts(at)


def _open_window(timer: Timer, at: datetime) -> None:
    timer["focusWindows"].append([_ts(at), None])


def advance(timer: Timer, now: datetime) -> tuple[Timer, bool]:
    """Apply every phase boundary up to `now`; returns (timer, completed)."""
    t = copy.deepcopy(timer)
    while not t["pausedAt"] and t["phase"] != "done" and now >= phase_end(t):
        at = phase_end(t)
        if t["phase"] == "starting":
            t["phase"], t["phaseDurationSec"] = "focus", t["focusSec"]
            _open_window(t, at)
        elif t["phase"] == "focus":
            _close_window(t, at)
            if t["cycle"] >= t["cycles"]:
                t["phase"] = "done"
                t["phaseStartedAt"] = _ts(at)
                return t, True
            t["phase"], t["phaseDurationSec"] = "break", t["breakSec"]
        else:
            t["phase"], t["phaseDurationSec"] = "focus", t["focusSec"]
            t["cycle"] += 1
            _open_window(t, at)
        t["phaseStartedAt"] = _ts(at)
    return t, t["phase"] == "done"


def pause(timer: Timer, actor: UUID, now: datetime) -> Timer:
    if timer["pausedAt"] or timer["phase"] not in ("focus", "break"):
        raise MachineError("ACTIVITY_CHANGED")
    t = copy.deepcopy(timer)
    t["pausedRemainingSec"] = remaining(t, now)
    t["pausedAt"], t["pausedBy"] = _ts(now), str(actor)
    if t["phase"] == "focus":
        _close_window(t, now)
    return t


def resume(timer: Timer, now: datetime) -> Timer:
    if not timer["pausedAt"]:
        raise MachineError("ACTIVITY_CHANGED")
    t = copy.deepcopy(timer)
    elapsed = t["phaseDurationSec"] - t["pausedRemainingSec"]
    t["phaseStartedAt"] = _ts(now - timedelta(seconds=elapsed))
    t["pausedAt"] = t["pausedRemainingSec"] = t["pausedBy"] = None
    if t["phase"] == "focus":
        _open_window(t, now)
    return t


def present(timer: Timer, user: UUID) -> bool:
    intervals = timer["presence"].get(str(user), [])
    return bool(intervals) and intervals[-1][1] is None


def leave(timer: Timer, actor: UUID, now: datetime) -> Timer:
    if not present(timer, actor):
        raise NoChange
    t = copy.deepcopy(timer)
    t["presence"][str(actor)][-1][1] = _ts(now)
    if not any(present(t, UUID(uid)) for uid in t["presence"]):
        t["awaySince"] = _ts(now)
    return t


def join(timer: Timer, actor: UUID, now: datetime) -> Timer:
    if present(timer, actor):
        raise NoChange
    t = copy.deepcopy(timer)
    intervals = t["presence"].setdefault(str(actor), [])
    if len(intervals) >= MAX_INTERVALS:
        intervals[-1][1] = None  # cap reached: treat the last gap as present
    else:
        intervals.append([_ts(now), None])
    t["awaySince"] = None
    return t


def close_all(timer: Timer, now: datetime) -> Timer:
    t = copy.deepcopy(timer)
    _close_window(t, now)
    for intervals in t["presence"].values():
        if intervals and intervals[-1][1] is None:
            intervals[-1][1] = _ts(now)
    return t


def _intervals(rows: list[list[str | None]], until: datetime) -> list[tuple[datetime, datetime]]:
    return [(_dt(a), min(_dt(b), until) if b else until) for a, b in rows if a]  # type: ignore[arg-type]


def _intersect(a, b):
    result, i, j = [], 0, 0
    while i < len(a) and j < len(b):
        start, end = max(a[i][0], b[j][0]), min(a[i][1], b[j][1])
        if start < end:
            result.append((start, end))
        if a[i][1] < b[j][1]:
            i += 1
        else:
            j += 1
    return result


def _minutes(intervals) -> int:
    return int(sum((end - start).total_seconds() for start, end in intervals) // 60)


def minutes(timer: Timer, until: datetime) -> dict[str, int]:
    """Factual focus minutes per participant and together (no points, no streaks)."""
    windows = _intervals(timer["focusWindows"], until)
    result: dict[str, int] = {}
    shared = windows
    for uid, rows in timer["presence"].items():
        overlap = _intersect(windows, _intervals(rows, until))
        result[uid] = _minutes(overlap)
        shared = _intersect(shared, _intervals(rows, until))
    result["together"] = _minutes(shared)
    return result


def deadline(timer: Timer, now: datetime) -> datetime | None:
    candidates = []
    if timer["pausedAt"]:
        candidates.append(_dt(timer["pausedAt"]) + PAUSE_LIMIT)
    elif timer["phase"] != "done":
        candidates.append(phase_end(timer))
    if timer["awaySince"]:
        candidates.append(_dt(timer["awaySince"]) + AWAY_LIMIT)
    return min(candidates) if candidates else None


class Focus:
    def on_accept(self, s: SessionState, now: datetime) -> None:
        s.timer = start(
            s.content.get("options", {}),
            (s.inviter_id, s.invitee_id),
            now,
            s.content.get("testSeconds"),
        )
        s.phase, s.round = "starting", 1

    def _sync(self, s: SessionState, now: datetime) -> bool:
        assert s.timer is not None
        s.timer, completed = advance(s.timer, now)
        s.phase, s.round = s.timer["phase"], s.timer["cycle"]
        if completed:
            finish(s, "completed", "completed", now)
        return completed

    def act(self, s: SessionState, cmd: Command, now: datetime) -> None:
        if cmd.op not in ("pause", "resume", "leave", "join") or s.timer is None:
            raise MachineError("ACTIVITY_CHANGED")
        if self._sync(s, now):
            return
        if cmd.op == "pause":
            s.timer, s.state = pause(s.timer, cmd.actor, now), "paused"
        elif cmd.op == "resume":
            if s.state != "paused":
                raise MachineError("ACTIVITY_CHANGED")
            s.timer, s.state = resume(s.timer, now), "active"
        elif cmd.op == "leave":
            s.timer = leave(s.timer, cmd.actor, now)
        else:
            s.timer = join(s.timer, cmd.actor, now)

    def tick(self, s: SessionState, now: datetime) -> bool:
        if s.timer is None:
            return False
        if s.timer["pausedAt"] and now >= _dt(s.timer["pausedAt"]) + PAUSE_LIMIT:
            finish(s, "ended", "pause_expired", now)
            return True
        if s.timer["awaySince"] and now >= _dt(s.timer["awaySince"]) + AWAY_LIMIT:
            finish(s, "ended", "idle_expired", now)
            return True
        before = s.timer
        self._sync(s, now)
        return s.terminal or s.timer != before

    def deadline(self, s: SessionState, now: datetime) -> datetime | None:
        return deadline(s.timer, now) if s.timer else None

    def on_end(self, s: SessionState, now: datetime) -> None:
        if s.timer is not None:
            s.timer = close_all(s.timer, now)


HANDLERS["focus"] = Focus()
