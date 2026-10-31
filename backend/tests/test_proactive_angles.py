"""Anti-repetition: a content-free daily angle rotates per companion and slot (07 §9)."""

from datetime import date, timedelta


def test_angle_rotates_over_a_week_for_every_companion_and_slot():
    from app.ai.proactive.context import ANGLES, angle_for

    start = date(2026, 11, 2)
    for (bot, slot), options in ANGLES.items():
        week = [angle_for(bot, slot, start + timedelta(days=offset)) for offset in range(7)]
        assert len(set(week)) >= min(5, len(options)), (bot, slot, week)
        assert all(value in options for value in week)
    assert angle_for("caunoi", "morning", start) is None


def test_angle_is_deterministic_and_sent_without_user_data():
    from app.ai.proactive.context import ProactivePayload, angle_for

    day = date(2026, 11, 3)
    assert angle_for("guong", "morning", day) == angle_for("guong", "morning", day)
    payload = ProactivePayload(bot_id="guong", slot="morning", local_date=day, local_time="07:30")
    assert payload.data()["angle"] == angle_for("guong", "morning", day)
