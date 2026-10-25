"""T-ACT-01: common activity state machine; kind rules are stubbed by a test handler."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from app.modules.activities import machine
from app.modules.activities.machine import (
    Command,
    MachineError,
    NoChange,
    ParticipantState,
    SessionState,
)

T0 = datetime(2026, 10, 25, 9, tzinfo=UTC)
INVITER = UUID("00000000-0000-4000-8000-00000000000a")
INVITEE = UUID("00000000-0000-4000-8000-00000000000b")
STRANGER = UUID("00000000-0000-4000-8000-00000000000c")


class TurnHandler:
    """Minimal turn-based rules: accept starts round 1, 'ready' completes."""

    def on_accept(self, s, now):
        s.round, s.phase = 1, "answering"

    def act(self, s, cmd, now):
        if cmd.op == "ready":
            machine.finish(s, "completed", "completed", now)

    def tick(self, s, now):
        return False

    def deadline(self, s, now):
        return None

    def on_end(self, s, now):
        s.content["ended_handled"] = True


@pytest.fixture(autouse=True)
def turn_handler(monkeypatch):
    monkeypatch.setitem(machine.HANDLERS, "icebreaker", TurnHandler())


def invited(**changes) -> SessionState:
    state = SessionState(
        id=UUID("00000000-0000-4000-8000-000000000001"),
        kind="icebreaker",
        state="invited",
        round=0,
        phase="invited",
        inviter_id=INVITER,
        invitee_id=INVITEE,
        content={},
        timer=None,
        score=None,
        version=1,
        participants={
            INVITER: ParticipantState(INVITER, "inviter", accepted_at=T0),
            INVITEE: ParticipantState(INVITEE, "invitee"),
        },
        created_at=T0,
        deadline_at=T0 + timedelta(minutes=10),
    )
    for key, value in changes.items():
        setattr(state, key, value)
    return state


def active() -> SessionState:
    return machine.apply(invited(), Command("accept", INVITEE), T0)


@pytest.mark.parametrize(
    ("op", "actor", "state", "reason"),
    [
        ("accept", INVITEE, "active", None),
        ("decline", INVITEE, "declined", "invite_declined"),
        ("cancel", INVITER, "cancelled", "invite_cancelled"),
    ],
)
def test_allowed_invitation_transitions(op, actor, state, reason):
    result = machine.apply(invited(), Command(op, actor), T0 + timedelta(minutes=1))
    assert (result.state, result.end_reason) == (state, reason)
    if op == "accept":
        assert result.round == 1 and result.started_at == T0 + timedelta(minutes=1)
        assert result.participants[INVITEE].accepted_at is not None
        assert result.deadline_at == T0 + timedelta(minutes=1, hours=24)  # idle limit
    else:
        assert result.deadline_at is None and result.ended_at is not None


@pytest.mark.parametrize(
    ("op", "actor", "code", "status"),
    [
        ("accept", INVITER, "WRONG_ACTOR", 403),
        ("decline", INVITER, "WRONG_ACTOR", 403),
        ("cancel", INVITEE, "WRONG_ACTOR", 403),
        ("accept", STRANGER, "WRONG_ACTOR", 403),
        ("end", INVITER, "ACTIVITY_CHANGED", 409),
        ("respond", INVITEE, "ACTIVITY_CHANGED", 409),
        ("feedback", INVITEE, "NOT_COMPLETED", 409),
        ("pause", INVITER, "ACTIVITY_CHANGED", 409),
    ],
)
def test_forbidden_invitation_commands(op, actor, code, status):
    with pytest.raises(MachineError) as error:
        machine.apply(invited(), Command(op, actor), T0)
    assert (error.value.code, error.value.status) == (code, status)


@pytest.mark.parametrize("actor", [INVITER, INVITEE])
def test_either_participant_can_end_an_active_session(actor):
    result = machine.apply(active(), Command("end", actor), T0 + timedelta(minutes=3))
    role = "inviter" if actor == INVITER else "invitee"
    assert (result.state, result.end_reason) == ("ended", f"ended_by_{role}")
    assert result.content["ended_handled"] is True


def test_accepting_twice_or_after_cancel_is_refused():
    with pytest.raises(MachineError) as error:
        machine.apply(active(), Command("accept", INVITEE), T0)
    assert error.value.code == "ACTIVITY_CHANGED"
    cancelled = machine.apply(invited(), Command("cancel", INVITER), T0)
    with pytest.raises(MachineError):
        machine.apply(cancelled, Command("accept", INVITEE), T0)


@pytest.mark.parametrize("op", ["accept", "end", "respond", "ready", "cancel", "decline"])
def test_terminal_states_are_immutable(op):
    done = machine.apply(active(), Command("ready", INVITER), T0)
    assert done.state == "completed"
    with pytest.raises(MachineError) as error:
        machine.apply(done, Command(op, INVITEE), T0)
    assert error.value.code == "ACTIVITY_CHANGED"
    assert machine.tick(done, T0 + timedelta(days=9)) is None
    assert machine.abort(done, "blocked", T0) is None


def test_feedback_only_after_completion_and_repeat_is_a_no_change():
    done = machine.apply(active(), Command("ready", INVITER), T0)
    rated = machine.apply(done, Command("feedback", INVITEE, payload={"rating": "liked"}), T0)
    assert rated.participants[INVITEE].feedback == "liked"
    assert done.participants[INVITEE].feedback is None  # apply never mutates its input
    with pytest.raises(NoChange):
        machine.apply(rated, Command("feedback", INVITEE, payload={"rating": "liked"}), T0)


def test_focus_controls_are_refused_for_other_kinds():
    with pytest.raises(MachineError) as error:
        machine.apply(active(), Command("pause", INVITER), T0)
    assert (error.value.code, error.value.status) == ("NOT_FOCUS", 422)


def test_tick_expires_invites_after_ten_minutes():
    assert machine.tick(invited(), T0 + timedelta(minutes=9, seconds=59)) is None
    expired = machine.tick(invited(), T0 + timedelta(minutes=10))
    assert (expired.state, expired.end_reason) == ("expired", "invite_expired")


def test_tick_expires_idle_turn_based_sessions_after_a_day():
    session = active()
    assert machine.tick(session, T0 + timedelta(hours=23)) is None
    expired = machine.tick(session, T0 + timedelta(hours=24))
    assert (expired.state, expired.end_reason) == ("expired", "idle_expired")


def test_abort_records_the_system_reason():
    aborted = machine.abort(active(), "blocked", T0)
    assert (aborted.state, aborted.end_reason, aborted.deadline_at) == ("aborted", "blocked", None)
    assert aborted.content["ended_handled"] is True


def test_deadline_matches_state():
    assert machine.deadline(invited(), T0) == T0 + timedelta(minutes=10)
    assert machine.deadline(active(), T0 + timedelta(hours=1)) == T0 + timedelta(hours=25)
    assert machine.deadline(machine.abort(active(), "blocked", T0), T0) is None


def test_unregistered_kind_is_not_implemented(monkeypatch):
    monkeypatch.delitem(machine.HANDLERS, "icebreaker")
    with pytest.raises(MachineError) as error:
        machine.apply(invited(), Command("accept", INVITEE), T0)
    assert (error.value.code, error.value.status) == ("NOT_IMPLEMENTED", 501)
