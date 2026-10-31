"""Pure schedule math for proactive check-ins (no database)."""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.ai.proactive import schedule as s

HCM = ZoneInfo("Asia/Ho_Chi_Minh")
NY = ZoneInfo("America/New_York")


def utc(*args) -> datetime:
    return datetime(*args, tzinfo=UTC)


# --- windows, steps and age limits ---------------------------------------------------


def test_window_for_adult_and_teen():
    assert s.window_for("morning", "adult") == (time(5, 0), time(11, 30))
    assert s.window_for("evening", "adult") == (time(17, 0), time(22, 30))
    assert s.window_for("morning", "teen") == (time(5, 0), time(11, 30))
    assert s.window_for("evening", "teen") == (time(17, 0), time(21, 0))


@pytest.mark.parametrize(
    "slot,value,age,ok",
    [
        ("morning", time(5, 0), "adult", True),
        ("morning", time(11, 30), "adult", True),
        ("morning", time(4, 45), "adult", False),
        ("morning", time(11, 45), "adult", False),
        ("morning", time(7, 10), "adult", False),  # not on the 15-minute step
        ("morning", time(7, 15, 30), "adult", False),  # seconds are never allowed
        ("evening", time(22, 30), "adult", True),
        ("evening", time(22, 30), "teen", False),
        ("evening", time(21, 0), "teen", True),
        ("evening", time(21, 15), "teen", False),
        ("evening", time(16, 45), "adult", False),
    ],
)
def test_time_allowed(slot, value, age, ok):
    assert s.time_allowed(slot, value, age) is ok


def test_unknown_slot_is_rejected():
    with pytest.raises(ValueError):
        s.window_for("noon", "adult")


# --- quiet hours ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,inside",
    [
        (time(22, 0), True),  # start is inclusive
        (time(23, 59), True),
        (time(0, 0), True),
        (time(6, 59), True),
        (time(7, 0), False),  # end is exclusive
        (time(21, 45), False),
        (time(12, 0), False),
    ],
)
def test_quiet_hours_across_midnight(value, inside):
    assert s.in_quiet_hours(value, time(22, 0), time(7, 0)) is inside


def test_quiet_hours_within_one_day():
    assert s.in_quiet_hours(time(13, 0), time(12, 0), time(16, 0))
    assert not s.in_quiet_hours(time(16, 0), time(12, 0), time(16, 0))
    assert not s.in_quiet_hours(time(11, 59), time(12, 0), time(16, 0))


@pytest.mark.parametrize(
    "start,end,ok",
    [
        (time(22, 0), time(7, 0), True),  # 9 h
        (time(22, 0), time(2, 0), True),  # 4 h
        (time(22, 0), time(1, 45), False),  # 3 h 45
        (time(20, 0), time(8, 0), True),  # 12 h
        (time(20, 0), time(8, 15), False),  # 12 h 15
        (time(7, 0), time(7, 0), False),  # zero length
        (time(22, 10), time(7, 0), False),  # off-step
    ],
)
def test_quiet_duration_bounds(start, end, ok):
    assert s.quiet_hours_valid(start, end) is ok


def test_default_quiet_hours_by_age():
    assert s.default_quiet_hours("adult") == (time(22, 0), time(7, 0))
    assert s.default_quiet_hours("teen") == (time(21, 30), time(7, 0))


def test_default_times_stay_outside_default_quiet_hours():
    for age in ("adult", "teen"):
        start, end = s.default_quiet_hours(age)
        for slot in s.SLOTS:
            value = s.default_time(slot, age)
            assert s.time_allowed(slot, value, age)
            assert not s.in_quiet_hours(value, start, end)


def test_allowed_times_respect_window_step_and_quiet_hours():
    evening = s.allowed_times("evening", "adult", time(22, 0), time(7, 0))
    assert evening[0] == time(17, 0) and evening[-1] == time(21, 45)
    assert all(value.minute % 15 == 0 for value in evening)
    morning = s.allowed_times("morning", "adult", time(22, 0), time(7, 0))
    assert morning[0] == time(7, 0) and morning[-1] == time(11, 30)
    assert s.allowed_times("evening", "teen", time(21, 30), time(7, 0))[-1] == time(21, 0)


# --- weekdays ------------------------------------------------------------------------


def test_weekday_mask_round_trip_and_bits():
    assert s.weekdays_to_mask([1, 2, 3, 4, 5, 6, 7]) == 127
    assert s.weekdays_to_mask([1]) == 1  # bit 0 = Monday
    assert s.weekdays_to_mask([7]) == 64  # bit 6 = Sunday
    assert s.mask_to_weekdays(s.weekdays_to_mask([5, 1, 3])) == [1, 3, 5]
    monday, sunday = date(2026, 11, 2), date(2026, 11, 8)
    assert s.weekday_allowed(1, monday) and not s.weekday_allowed(1, sunday)
    assert s.weekday_allowed(64, sunday)


@pytest.mark.parametrize("bad", [[], [0], [8], [1, 1]])
def test_weekday_mask_rejects_invalid(bad):
    with pytest.raises(ValueError):
        s.weekdays_to_mask(bad)


# --- resolving local wall times ------------------------------------------------------


def test_resolve_local_without_dst():
    value = s.resolve_local(date(2026, 11, 1), time(7, 30), HCM)
    assert value.astimezone(UTC) == utc(2026, 11, 1, 0, 30)


def test_resolve_local_spring_forward_gap_moves_forward():
    # 2026-03-08 02:30 does not exist in New York (02:00 → 03:00).
    value = s.resolve_local(date(2026, 3, 8), time(2, 30), NY)
    assert value.astimezone(UTC) == utc(2026, 3, 8, 7, 30)  # 03:30 EDT
    assert value.astimezone(NY).time() == time(3, 30)


def test_resolve_local_fall_back_overlap_uses_first_instance():
    # 2026-11-01 01:30 happens twice in New York; the earlier (EDT) instant is used.
    value = s.resolve_local(date(2026, 11, 1), time(1, 30), NY)
    assert value.astimezone(UTC) == utc(2026, 11, 1, 5, 30)


# --- next occurrence ------------------------------------------------------------------


def nxt(after, *, at=time(7, 30), weekdays=127, paused_until=None, tz="Asia/Ho_Chi_Minh"):
    return s.next_occurrence(
        local_time=at, weekdays=weekdays, paused_until=paused_until, timezone=tz, after=after
    )


def test_next_occurrence_same_day_and_next_day():
    # 06:00 local (23:00 UTC previous day) → 07:30 the same local day.
    assert nxt(utc(2026, 10, 31, 23, 0)) == utc(2026, 11, 1, 0, 30)
    # Exactly at the occurrence → strictly later, the next day.
    assert nxt(utc(2026, 11, 1, 0, 30)) == utc(2026, 11, 2, 0, 30)
    assert nxt(utc(2026, 11, 1, 0, 31)) == utc(2026, 11, 2, 0, 30)


def test_next_occurrence_result_is_utc():
    value = nxt(utc(2026, 10, 31, 23, 0))
    assert value is not None and value.tzinfo == UTC


def test_next_occurrence_requires_aware_instant():
    with pytest.raises(ValueError):
        nxt(datetime(2026, 11, 1, 0, 0))


def test_next_occurrence_weekday_mask_skips_weekend():
    friday_after = utc(2026, 11, 6, 1, 0)  # Fri 08:00 local, after the 07:30 slot
    weekdays = s.weekdays_to_mask([1, 2, 3, 4, 5])
    assert nxt(friday_after, weekdays=weekdays) == utc(2026, 11, 9, 0, 30)  # Monday


def test_next_occurrence_respects_pause_through_inclusive_date():
    after = utc(2026, 11, 1, 1, 0)  # Sun 08:00 local
    assert nxt(after, paused_until=date(2026, 11, 3)) == utc(2026, 11, 4, 0, 30)


def test_next_occurrence_none_when_no_valid_day_within_horizon():
    after = utc(2026, 11, 1, 1, 0)
    assert nxt(after, paused_until=date(2026, 12, 31)) is None


def test_next_occurrence_dst_gap_and_overlap_deliver_once_per_day():
    tz = "America/New_York"
    gap = s.next_occurrence(
        local_time=time(2, 30), weekdays=127, paused_until=None, timezone=tz,
        after=utc(2026, 3, 8, 5, 0),
    )
    assert gap == utc(2026, 3, 8, 7, 30)
    first = s.next_occurrence(
        local_time=time(1, 30), weekdays=127, paused_until=None, timezone=tz,
        after=utc(2026, 11, 1, 4, 0),
    )
    assert first == utc(2026, 11, 1, 5, 30)
    # After the first 01:30 the repeated 01:30 (06:30 UTC) is not a new occurrence.
    second = s.next_occurrence(
        local_time=time(1, 30), weekdays=127, paused_until=None, timezone=tz, after=first
    )
    assert second == utc(2026, 11, 2, 6, 30)


def test_next_occurrence_after_long_downtime_jumps_to_the_future():
    # Two days offline: the next occurrence is computed from "now", never a backlog.
    now = utc(2026, 11, 3, 2, 0)
    assert nxt(now) == utc(2026, 11, 4, 0, 30)


def test_timezone_change_recomputes_the_same_wall_time():
    after = utc(2026, 11, 1, 0, 0)
    assert nxt(after, tz="Asia/Ho_Chi_Minh") == utc(2026, 11, 1, 0, 30)
    assert nxt(after, tz="Asia/Tokyo") == utc(2026, 11, 1, 22, 30)


def test_invalid_timezone_is_rejected():
    assert s.timezone_valid("Asia/Ho_Chi_Minh")
    assert not s.timezone_valid("Mars/Olympus")
    assert not s.timezone_valid("")
    assert not s.timezone_valid("../etc/passwd")


# --- local dates and occurrence identity --------------------------------------------------


def test_local_date_follows_schedule_timezone():
    instant = utc(2026, 10, 31, 23, 30)  # 06:30 on 1 Nov in Ho Chi Minh City
    assert s.local_date(instant, "Asia/Ho_Chi_Minh") == date(2026, 11, 1)
    assert s.local_date(instant, "America/New_York") == date(2026, 10, 31)


def test_occurrence_window_marks_missed_runs():
    due = utc(2026, 11, 1, 0, 30)
    expires = s.expires_at(due, grace_minutes=90)
    assert expires == due + timedelta(minutes=90)
    assert not s.missed(expires, at=due + timedelta(minutes=89))
    assert s.missed(expires, at=due + timedelta(minutes=90))


def test_quiet_conflict_detects_schedule_in_new_quiet_hours():
    assert s.quiet_conflict(time(21, 30), time(21, 0), time(7, 0))
    assert not s.quiet_conflict(time(20, 45), time(21, 0), time(7, 0))


def test_enabled_slot_cap():
    assert s.within_cap(enabled_after=4, cap=4)
    assert not s.within_cap(enabled_after=5, cap=4)
