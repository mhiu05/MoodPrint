"""Pure schedule math for proactive check-ins (phase-1/03 §4).

Every function here is deterministic and side-effect free: the API validates with it and
the worker materializes occurrences with it. Instants are always timezone-aware; the
returned next occurrence is a UTC instant.
"""

from collections.abc import Iterable
from datetime import UTC, date, datetime, time, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo, available_timezones

SLOTS = ("morning", "evening")
STEP_MINUTES = 15
# OD-02: the database CHECK (0022) encodes the same windows.
WINDOWS = {"morning": (time(5, 0), time(11, 30)), "evening": (time(17, 0), time(22, 30))}
# OD-03: 16–17 year olds get no evening check-in after 21:00 and earlier quiet hours.
TEEN_EVENING_LAST = time(21, 0)
DEFAULT_TIMES = {"morning": time(7, 30), "evening": time(20, 0)}
DEFAULT_QUIET = {"adult": (time(22, 0), time(7, 0)), "teen": (time(21, 30), time(7, 0))}
QUIET_MIN_HOURS, QUIET_MAX_HOURS = 4, 12
# Two weeks is enough to find any day allowed by a non-empty weekday mask.
HORIZON_DAYS = 15
ALL_WEEKDAYS = 127


def window_for(slot: str, age_band: str) -> tuple[time, time]:
    if slot not in WINDOWS:
        raise ValueError("unknown slot")
    start, end = WINDOWS[slot]
    if slot == "evening" and age_band == "teen":
        end = TEEN_EVENING_LAST
    return start, end


def on_step(value: time) -> bool:
    return value.second == 0 and value.microsecond == 0 and value.minute % STEP_MINUTES == 0


def time_allowed(slot: str, value: time, age_band: str) -> bool:
    start, end = window_for(slot, age_band)
    return on_step(value) and start <= value <= end


def in_quiet_hours(value: time, start: time, end: time) -> bool:
    """Quiet interval is [start, end); it may wrap past midnight."""
    if start <= end:
        return start <= value < end
    return value >= start or value < end


def _minutes(value: time) -> int:
    return value.hour * 60 + value.minute


def quiet_hours_valid(start: time, end: time) -> bool:
    if not (on_step(start) and on_step(end)):
        return False
    length = (_minutes(end) - _minutes(start)) % (24 * 60)
    return QUIET_MIN_HOURS * 60 <= length <= QUIET_MAX_HOURS * 60


def default_quiet_hours(age_band: str) -> tuple[time, time]:
    return DEFAULT_QUIET["teen" if age_band == "teen" else "adult"]


def default_time(slot: str, age_band: str) -> time:
    window_for(slot, age_band)
    return DEFAULT_TIMES[slot]


def allowed_times(slot: str, age_band: str, quiet_start: time, quiet_end: time) -> list[time]:
    start, end = window_for(slot, age_band)
    values, minute = [], _minutes(start)
    while minute <= _minutes(end):
        value = time(minute // 60, minute % 60)
        if not in_quiet_hours(value, quiet_start, quiet_end):
            values.append(value)
        minute += STEP_MINUTES
    return values


def quiet_conflict(local_time: time, quiet_start: time, quiet_end: time) -> bool:
    return in_quiet_hours(local_time, quiet_start, quiet_end)


def weekdays_to_mask(days: Iterable[int]) -> int:
    """ISO weekdays (1 = Monday … 7 = Sunday) → bit mask (bit 0 = Monday)."""
    values = list(days)
    if not values or len(set(values)) != len(values) or any(d not in range(1, 8) for d in values):
        raise ValueError("weekdays must be distinct ISO weekdays 1..7")
    mask = 0
    for day in values:
        mask |= 1 << (day - 1)
    return mask


def mask_to_weekdays(mask: int) -> list[int]:
    return [day for day in range(1, 8) if mask & (1 << (day - 1))]


def weekday_allowed(mask: int, day: date) -> bool:
    return bool(mask & (1 << day.weekday()))


@lru_cache(maxsize=1)
def _zones() -> frozenset[str]:
    return frozenset(available_timezones())


def timezone_valid(name: str) -> bool:
    return bool(name) and len(name) <= 64 and name in _zones()


def resolve_local(day: date, value: time, zone: ZoneInfo) -> datetime:
    naive = datetime.combine(day, value)
    first = naive.replace(tzinfo=zone, fold=0)
    round_trip = first.astimezone(UTC).astimezone(zone)
    if round_trip.replace(tzinfo=None) != naive:
        # Non-existent wall time (spring forward): move forward by the gap (02:30 → 03:30).
        return round_trip
    # Repeated wall time (fall back): fold=0 is the earlier instant; the unique
    # (user, bot, slot, local_date) job key prevents a second delivery that day.
    return first


def next_occurrence(
    *,
    local_time: time,
    weekdays: int,
    paused_until: date | None,
    timezone: str,
    after: datetime,
) -> datetime | None:
    """The first valid occurrence strictly after ``after`` (UTC), or None within the horizon."""
    if after.tzinfo is None:
        raise ValueError("after must be timezone-aware")
    zone = ZoneInfo(timezone)
    start = after.astimezone(zone).date()
    for offset in range(HORIZON_DAYS):
        day = start + timedelta(days=offset)
        if not weekday_allowed(weekdays, day) or (paused_until is not None and day <= paused_until):
            continue
        candidate = resolve_local(day, local_time, zone)
        if candidate > after:
            return candidate.astimezone(UTC)
    return None


def local_date(instant: datetime, timezone: str) -> date:
    return instant.astimezone(ZoneInfo(timezone)).date()


def expires_at(due_at: datetime, *, grace_minutes: int) -> datetime:
    return due_at + timedelta(minutes=grace_minutes)


def missed(expires: datetime, *, at: datetime) -> bool:
    return at >= expires


def within_cap(*, enabled_after: int, cap: int) -> bool:
    return enabled_after <= cap
