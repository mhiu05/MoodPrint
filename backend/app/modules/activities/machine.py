"""Pure activity state machine (06 section 2). Routes only load rows, lock, call
apply/tick/abort, persist and bump the connection's activity watermark.

Kind-specific rules live in icebreaker.py, quiz.py and focus.py behind `Handler`.
"""

import copy
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, Protocol
from uuid import UUID

from app.modules.activities.definitions import DEFINITIONS

TERMINAL = frozenset({"completed", "ended", "declined", "cancelled", "expired", "aborted"})
FOCUS_OPS = frozenset({"pause", "resume", "leave", "join"})
Op = Literal[
    "accept",
    "decline",
    "cancel",
    "end",
    "respond",
    "ready",
    "pause",
    "resume",
    "leave",
    "join",
    "feedback",
]


class MachineError(Exception):
    """A refused command; `status` and `code` map onto the API error envelope."""

    MESSAGES = {
        "WRONG_ACTOR": "Bạn không thể thực hiện thao tác này.",
        "ACTIVITY_CHANGED": "Hoạt động vừa thay đổi. Đã cập nhật trạng thái mới nhất.",
        "ROUND_CHANGED": "Câu hỏi đã chuyển sang lượt khác.",
        "RESPONSE_CONFLICT": "Bạn đã gửi một câu trả lời khác cho câu này.",
        "NOT_FOCUS": "Thao tác này chỉ dành cho phiên cùng tập trung.",
        "NOT_COMPLETED": "Chỉ có thể đánh giá sau khi hoạt động hoàn tất.",
        "INVALID_RESPONSE": "Câu trả lời chưa hợp lệ.",
        "NOT_IMPLEMENTED": "Hoạt động này chưa sẵn sàng.",
    }

    def __init__(self, code: str, status: int = 409):
        self.code, self.status = code, status
        super().__init__(code)

    @property
    def message(self) -> str:
        return self.MESSAGES.get(self.code, "Không thể thực hiện thao tác này.")


class NoChange(Exception):
    """The command repeats what already happened (idempotent); nothing to persist."""


@dataclass
class ParticipantState:
    user_id: UUID
    role: str
    accepted_at: datetime | None = None
    ready_round: int = 0
    feedback: str | None = None
    feedback_at: datetime | None = None


@dataclass
class ResponseState:
    user_id: UUID
    round: int
    item_id: str
    choice: int | None = None
    text: str | None = None
    skipped: bool = False
    submitted_at: datetime | None = None


@dataclass
class SessionState:
    id: UUID
    kind: str
    state: str
    round: int
    phase: str
    inviter_id: UUID
    invitee_id: UUID
    content: dict[str, Any]
    timer: dict[str, Any] | None
    score: dict[str, Any] | None
    version: int
    participants: dict[UUID, ParticipantState]
    responses: dict[tuple[UUID, int], ResponseState] = field(default_factory=dict)
    end_reason: str | None = None
    created_at: datetime | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    deadline_at: datetime | None = None

    @property
    def terminal(self) -> bool:
        return self.state in TERMINAL

    def peer_of(self, user_id: UUID) -> UUID:
        return self.invitee_id if user_id == self.inviter_id else self.inviter_id


@dataclass(frozen=True)
class Command:
    op: Op
    actor: UUID
    round: int | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)


class Handler(Protocol):
    def on_accept(self, s: SessionState, now: datetime) -> None: ...
    def act(self, s: SessionState, cmd: Command, now: datetime) -> None: ...
    def tick(self, s: SessionState, now: datetime) -> bool: ...
    def deadline(self, s: SessionState, now: datetime) -> datetime | None: ...
    def on_end(self, s: SessionState, now: datetime) -> None: ...


class _NotImplemented:
    """Placeholder for a kind whose rules are not registered (refuses with 501)."""

    def on_accept(self, s: SessionState, now: datetime) -> None:
        raise MachineError("NOT_IMPLEMENTED", 501)

    def act(self, s: SessionState, cmd: Command, now: datetime) -> None:
        raise MachineError("NOT_IMPLEMENTED", 501)

    def tick(self, s: SessionState, now: datetime) -> bool:
        return False

    def deadline(self, s: SessionState, now: datetime) -> datetime | None:
        return None

    def on_end(self, s: SessionState, now: datetime) -> None:
        return None


HANDLERS: dict[str, Handler] = {}


def handler(kind: str) -> Handler:
    return HANDLERS.get(kind, _NotImplemented())


def finish(s: SessionState, state: str, reason: str, now: datetime) -> None:
    if s.state in ("active", "paused"):
        handler(s.kind).on_end(s, now)
    s.state, s.end_reason, s.ended_at, s.deadline_at = state, reason, now, None
    s.phase = "done" if state == "completed" else state


def deadline(s: SessionState, now: datetime) -> datetime | None:
    """The next instant the sweeper must act: invite expiry, phase end, idle or pause limits."""
    if s.terminal:
        return None
    definition = DEFINITIONS[s.kind]
    if s.state == "invited":
        return (s.created_at or now) + definition.invite_ttl
    if s.kind == "focus":
        return handler(s.kind).deadline(s, now)
    return now + definition.idle_ttl if definition.idle_ttl else None


def apply(state: SessionState, cmd: Command, now: datetime) -> SessionState:
    """Return the new state for `cmd`; raise MachineError (refused) or NoChange (replay)."""
    if cmd.actor not in state.participants:
        raise MachineError("WRONG_ACTOR", 403)
    s = copy.deepcopy(state)
    if cmd.op == "feedback":
        if s.state != "completed":
            raise MachineError("NOT_COMPLETED")
        rating = cmd.payload.get("rating")
        participant = s.participants[cmd.actor]
        if participant.feedback == rating:
            raise NoChange
        participant.feedback, participant.feedback_at = rating, now
        return s
    if s.terminal:
        raise MachineError("ACTIVITY_CHANGED")
    role = s.participants[cmd.actor].role
    if cmd.op in ("accept", "decline", "cancel"):
        if s.state != "invited":
            raise MachineError("ACTIVITY_CHANGED")
        if role != ("inviter" if cmd.op == "cancel" else "invitee"):
            raise MachineError("WRONG_ACTOR", 403)
        if cmd.op == "accept":
            s.state, s.started_at = "active", now
            s.participants[cmd.actor].accepted_at = now
            handler(s.kind).on_accept(s, now)
        else:
            finish(
                s,
                "declined" if cmd.op == "decline" else "cancelled",
                "invite_declined" if cmd.op == "decline" else "invite_cancelled",
                now,
            )
    elif s.state == "invited":
        raise MachineError("ACTIVITY_CHANGED")
    elif cmd.op == "end":
        finish(s, "ended", f"ended_by_{role}", now)
    elif cmd.op in FOCUS_OPS:
        if s.kind != "focus":
            raise MachineError("NOT_FOCUS", 422)
        handler(s.kind).act(s, cmd, now)
    else:
        if s.state != "active":
            raise MachineError("ACTIVITY_CHANGED")
        handler(s.kind).act(s, cmd, now)
    s.deadline_at = deadline(s, now)
    return s


def tick(state: SessionState, now: datetime) -> SessionState | None:
    """Deadline-driven transitions; None when nothing is due."""
    if state.terminal or (state.deadline_at and now < state.deadline_at):
        return None
    s = copy.deepcopy(state)
    if s.state == "invited":
        if now < (s.created_at or now) + DEFINITIONS[s.kind].invite_ttl:
            return None
        finish(s, "expired", "invite_expired", now)
    elif s.kind == "focus":
        if not handler(s.kind).tick(s, now):
            return None
    elif s.deadline_at is not None:
        finish(s, "expired", "idle_expired", now)
    else:
        return None
    if not s.terminal:
        s.deadline_at = deadline(s, now)
    return s


def abort(state: SessionState, reason: str, now: datetime) -> SessionState | None:
    """System stop (block, room closed, consent, restriction, deletion)."""
    if state.terminal:
        return None
    s = copy.deepcopy(state)
    finish(s, "aborted", reason, now)
    return s
