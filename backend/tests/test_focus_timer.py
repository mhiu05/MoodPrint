"""T-FOCUS-01: focus timer math with an injected clock (no sleeping, no wall time)."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from app.modules.activities import focus
from app.modules.activities.machine import MachineError, NoChange

T0 = datetime(2026, 10, 25, 9, tzinfo=UTC)
A = UUID("00000000-0000-4000-8000-00000000000a")
B = UUID("00000000-0000-4000-8000-00000000000b")


def at(**delta) -> datetime:
    return T0 + timedelta(**delta)


def started(plan=(25, 5), cycles=2):
    return focus.start({"plan": list(plan), "cycles": cycles}, (A, B), T0)


def test_two_cycles_run_starting_focus_break_focus_done_without_a_final_break():
    timer = started()
    assert timer["phase"] == "starting" and focus.phase_end(timer) == at(seconds=5)
    timer, done = focus.advance(timer, at(seconds=5))
    assert (timer["phase"], timer["cycle"], done) == ("focus", 1, False)
    timer, done = focus.advance(timer, at(seconds=5, minutes=25))
    assert (timer["phase"], done) == ("break", False)
    timer, done = focus.advance(timer, at(seconds=5, minutes=30))
    assert (timer["phase"], timer["cycle"], done) == ("focus", 2, False)
    timer, done = focus.advance(timer, at(seconds=5, minutes=55))
    assert (timer["phase"], done) == ("done", True)
    assert focus.minutes(timer, at(hours=1)) == {str(A): 50, str(B): 50, "together": 50}


def test_advance_catches_up_several_boundaries_after_a_long_sleep():
    timer, done = focus.advance(started(), at(hours=2))
    assert done and timer["phase"] == "done"
    assert timer["phaseStartedAt"] == at(seconds=5, minutes=55).isoformat()


def test_pause_keeps_the_remaining_time_and_resume_restores_it():
    timer, _ = focus.advance(started(cycles=1), at(minutes=15, seconds=5))  # 10:00 left
    paused = focus.pause(timer, A, at(minutes=15, seconds=5))
    assert paused["pausedRemainingSec"] == 600 and paused["pausedBy"] == str(A)
    assert focus.remaining(paused, at(minutes=40)) == 600  # frozen while paused
    resumed = focus.resume(paused, at(minutes=40))
    assert focus.remaining(resumed, at(minutes=40)) == 600
    assert focus.phase_end(resumed) == at(minutes=50)
    with pytest.raises(MachineError):
        focus.resume(resumed, at(minutes=41))


def test_pause_and_away_limits_drive_the_deadline():
    timer, _ = focus.advance(started(cycles=1), at(minutes=1))
    paused = focus.pause(timer, B, at(minutes=1))
    assert focus.deadline(paused, at(minutes=1)) == at(minutes=16)
    away = focus.leave(focus.leave(timer, A, at(minutes=2)), B, at(minutes=3))
    assert away["awaySince"] == at(minutes=3).isoformat()
    assert focus.deadline(away, at(minutes=3)) == at(minutes=13)
    back = focus.join(away, A, at(minutes=4))
    assert back["awaySince"] is None


def test_minutes_intersect_focus_windows_with_presence_gaps():
    timer, _ = focus.advance(started(cycles=1), at(seconds=5))
    timer = focus.leave(timer, B, at(minutes=10, seconds=5))
    timer = focus.join(timer, B, at(minutes=20, seconds=5))
    timer, done = focus.advance(timer, at(minutes=25, seconds=5))
    assert done
    result = focus.minutes(focus.close_all(timer, at(minutes=30)), at(minutes=30))
    assert result == {str(A): 25, str(B): 15, "together": 15}


def test_paused_focus_time_does_not_count():
    timer, _ = focus.advance(started(cycles=1), at(seconds=5))
    timer = focus.pause(timer, A, at(minutes=5, seconds=5))
    timer = focus.resume(timer, at(minutes=15, seconds=5))
    timer, done = focus.advance(timer, at(minutes=35, seconds=5))
    assert done
    assert focus.minutes(timer, at(hours=1))["together"] == 25


def test_presence_is_capped_at_twenty_intervals_and_repeats_are_no_changes():
    timer = started()
    for minute in range(1, 40):
        timer = focus.leave(timer, A, at(minutes=minute, seconds=1))
        timer = focus.join(timer, A, at(minutes=minute, seconds=30))
    assert len(timer["presence"][str(A)]) <= 20
    with pytest.raises(NoChange):
        focus.join(timer, A, at(hours=1))


@pytest.mark.parametrize("options", [{"plan": [20, 5]}, {"cycles": 0}, {"cycles": 5}])
def test_invalid_options_are_rejected(options):
    with pytest.raises(MachineError) as error:
        focus.validate_options(options)
    assert error.value.status == 422


def test_test_plan_seconds_shorten_the_phases():
    timer = focus.start({"plan": [25, 5], "cycles": 1}, (A, B), T0, test_seconds=60)
    assert (timer["focusSec"], timer["breakSec"]) == (60, 12)
