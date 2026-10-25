"""The only path from session state to an API view, projected for one viewer.

Privacy rules (06 section 1, T-ICE-01, T-QUIZ-01):
- a peer's answer appears only after the round is revealed, and only if the viewer
  answered too (reciprocal reveal); skips are shown as skips;
- quiz correctIndex and explanations appear only for revealed rounds;
- the peer's private feedback never appears.
"""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from app.modules.activities import content, focus
from app.modules.activities.definitions import DEFINITIONS
from app.modules.activities.machine import ResponseState, SessionState
from app.modules.activities.schemas import (
    ActivityItemView,
    ActivitySessionView,
    AnswerView,
    CurrentView,
    HistoryRound,
    PeerView,
    ProgressView,
    RevealView,
    ScoreView,
    SelfView,
    SummaryView,
    TimerView,
)

TURN_BASED = ("icebreaker", "coop_quiz")


def _item(s: SessionState, round_number: int) -> dict[str, Any]:
    return content.item_by_id(s.content["bank"], s.content["items"][round_number - 1])


def _item_view(item: dict[str, Any]) -> ActivityItemView:
    return ActivityItemView(
        id=item["id"],
        prompt=item["prompt"],
        options=list(item["options"]),
        allow_text=bool(item.get("allowText", False)),
    )


def _answer(response: ResponseState | None) -> AnswerView | None:
    if response is None:
        return None
    return AnswerView(choice=response.choice, text=response.text, skipped=response.skipped)


def _revealed(s: SessionState, round_number: int) -> bool:
    if round_number < s.round:
        return True
    return round_number == s.round and (s.phase == "revealed" or s.state == "completed")


def _reveal(s: SessionState, viewer: UUID, round_number: int) -> RevealView:
    mine = s.responses.get((viewer, round_number))
    theirs = s.responses.get((s.peer_of(viewer), round_number))
    peer: AnswerView | Literal["hidden", "skipped"] | None
    if theirs is None:
        peer = None
    elif theirs.skipped:
        peer = "skipped"
    elif mine is None or mine.skipped:
        peer = "hidden"
    else:
        peer = _answer(theirs)
    reveal = RevealView(me=_answer(mine), peer=peer)
    if s.kind == "coop_quiz":
        item = _item(s, round_number)
        reveal.correct_index = item["correctIndex"]
        reveal.explanation = item["explanation"]
        rounds = (s.score or {}).get("rounds", [])
        reveal.points = rounds[round_number - 1] if len(rounds) >= round_number else None
    return reveal


def _summary(s: SessionState, viewer: UUID, until: datetime) -> SummaryView | None:
    if s.kind == "icebreaker" and s.state == "completed":
        together = sum(
            1
            for round_number in range(1, s.round + 1)
            if all(
                (uid, round_number) in s.responses and not s.responses[(uid, round_number)].skipped
                for uid in s.participants
            )
        )
        return SummaryView(answered_together=together)
    if s.kind == "coop_quiz" and s.score and s.state in ("completed", "ended"):
        return SummaryView(team_score=s.score["team"], max_score=s.score["max"])
    if s.kind == "focus" and s.timer and s.state in ("completed", "ended", "aborted"):
        minutes = focus.minutes(s.timer, until)
        return SummaryView(
            focus_minutes_self=minutes.get(str(viewer), 0),
            focus_minutes_peer=minutes.get(str(s.peer_of(viewer)), 0),
            focus_minutes_together=minutes["together"],
        )
    return None


def _timer(s: SessionState, viewer: UUID, now: datetime) -> TimerView | None:
    if s.kind != "focus" or not s.timer:
        return None
    t = s.timer
    running = s.state in ("active", "paused") and t["phase"] != "done"
    return TimerView(
        phase=t["phase"],
        cycle=t["cycle"],
        cycles=t["cycles"],
        plan=list(t["plan"]),
        phase_ends_at=focus.phase_end(t) if running and not t["pausedAt"] else None,
        paused_remaining_sec=t["pausedRemainingSec"],
        paused_by_self=(t["pausedBy"] == str(viewer)) if t["pausedBy"] else None,
        self_present=focus.present(t, viewer),
        peer_present=focus.present(t, s.peer_of(viewer)),
    )


def project(
    s: SessionState, connection_id: UUID, viewer: UUID, now: datetime
) -> ActivitySessionView:
    definition = DEFINITIONS[s.kind]
    me, them = s.participants[viewer], s.participants[s.peer_of(viewer)]
    current = None
    history: list[HistoryRound] = []
    if s.kind in TURN_BASED and s.round >= 1 and s.content.get("items"):
        last = min(s.round, len(s.content["items"]))
        for round_number in range(1, last + 1):
            if _revealed(s, round_number) and (round_number < s.round or s.terminal):
                history.append(
                    HistoryRound(
                        round=round_number,
                        item=_item_view(_item(s, round_number)),
                        reveal=_reveal(s, viewer, round_number),
                    )
                )
        if s.state == "active":
            mine = s.responses.get((viewer, s.round))
            current = CurrentView(
                item=_item_view(_item(s, s.round)),
                self_response=_answer(mine),
                peer_submitted=(s.peer_of(viewer), s.round) in s.responses,
                reveal=_reveal(s, viewer, s.round) if s.phase == "revealed" else None,
            )
    focus_kind = s.kind == "focus" and s.timer is not None
    return ActivitySessionView(
        id=str(s.id),
        connection_id=str(connection_id),
        kind=s.kind,  # type: ignore[arg-type]
        definition_version=definition.version,
        state=s.state,
        end_reason=_relative_reason(s.end_reason, me.role),
        version=s.version,
        role=me.role,  # type: ignore[arg-type]
        created_at=s.created_at or now,
        started_at=s.started_at,
        ended_at=s.ended_at,
        expires_at=s.deadline_at if s.state == "invited" else None,
        server_time=now,
        me=SelfView(
            accepted=me.accepted_at is not None,
            ready_round=me.ready_round,
            joined=focus.present(s.timer, viewer) if focus_kind and s.timer else None,
            feedback_given=me.feedback is not None,
        ),
        peer=PeerView(
            accepted=them.accepted_at is not None,
            ready_round=them.ready_round,
            joined=focus.present(s.timer, them.user_id) if focus_kind and s.timer else None,
        ),
        progress=ProgressView(round=s.round, total_rounds=definition.rounds, phase=s.phase),
        current=current,
        history=history,
        score=ScoreView(**s.score) if s.kind == "coop_quiz" and s.score else None,
        timer=_timer(s, viewer, now),
        summary=_summary(s, viewer, s.ended_at or now),
    )


def _relative_reason(reason: str | None, role: str) -> str | None:
    if reason and reason.startswith("ended_by_"):
        return "ended_by_self" if reason == f"ended_by_{role}" else "ended_by_peer"
    return reason
