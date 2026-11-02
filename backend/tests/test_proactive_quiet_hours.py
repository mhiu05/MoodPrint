"""Run real authorization with a fixed clock and a minimal asynchronous row store."""

from datetime import UTC, datetime, time, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.ai.proactive import policy
from app.ai.proactive.models import AiProactiveSettings
from app.core.config import Settings


@pytest.mark.parametrize("lock", [True, False])
@pytest.mark.parametrize(
    "hour,minute,blocked",
    [(21, 59, False), (22, 0, True), (22, 15, True), (0, 15, True), (6, 59, True), (7, 0, False)],
)
async def test_authorization_checks_actual_delivery_time_in_schedule_timezone(monkeypatch, lock, hour, minute, blocked):
    # A legal 21:45 schedule can be delayed into 22:00 quiet hours within its grace period.
    local = datetime(2026, 11, 2, hour, minute, tzinfo=ZoneInfo("Asia/Bangkok"))
    at = local.astimezone(UTC)
    uid, sid = uuid4(), uuid4()
    user = SimpleNamespace(id=uid, status="active", account_kind="registered", deletion_pending=False,
                           suspended_until=None, last_seen_at=at, age_band="adult")
    prefs = SimpleNamespace(timezone="Asia/Bangkok", version=1, quiet_start=time(22), quiet_end=time(7))
    schedule = SimpleNamespace(user_id=uid, enabled=True, updated_at=at, version=1,
                               paused_until=None, auto_paused_at=None)
    job = SimpleNamespace(user_id=uid, schedule_id=sid, local_date=local.date(),
                          schedule_version=1, settings_version=1, bot_id="may",
                          due_at=at - timedelta(minutes=30))

    async def get(model, key):
        return prefs if model is AiProactiveSettings else schedule

    db = SimpleNamespace(scalar=AsyncMock(return_value=user), get=get)
    monkeypatch.setattr(policy, "now", lambda: at)
    monkeypatch.setattr(policy, "is_adult_eligible", AsyncMock(return_value=True))
    monkeypatch.setattr(policy, "assert_purpose", AsyncMock())
    result = await policy.authorize_proactive(db, Settings(proactive_enabled=True),
                                             SimpleNamespace(available_for=lambda _: True), job, lock=lock)
    if blocked:
        assert isinstance(result, policy.Decision)
        assert (result.outcome, result.reason) == ("skip", "quiet_hours")
    else:
        assert isinstance(result, policy.Authorized)


@pytest.mark.postgres
@pytest.mark.parametrize("cross_during_generation", [False, True])
async def test_delayed_delivery_does_not_publish_in_quiet_hours(clients, monkeypatch, cross_during_generation):
    import asyncio

    from sqlalchemy import update

    from tests.test_proactive_executor import (
        due_schedule,
        only_job,
        proactive_messages,
        ready,
        reply,
        tick,
    )

    app, [(_client, uid), _] = clients
    model = reply("Một lời hỏi thăm nhỏ.")
    model.hold = cross_during_generation
    ready(app, model)
    await due_schedule(app, uid, slot="evening", local_time=time(21, 45))
    async with app.state.database.sessions.begin() as db:
        await db.execute(update(AiProactiveSettings).where(AiProactiveSettings.user_id == uid)
                         .values(quiet_start=time(22), quiet_end=time(7)))
    today = datetime.now(ZoneInfo("Asia/Bangkok")).date()
    clock = [datetime.combine(today, time(21, 59) if cross_during_generation else time(22, 15),
                              tzinfo=ZoneInfo("Asia/Bangkok")).astimezone(UTC)]
    monkeypatch.setattr(policy, "now", lambda: clock[0])
    task = asyncio.create_task(tick(app))
    if cross_during_generation:
        await asyncio.wait_for(model.started.wait(), 10)
        clock[0] += timedelta(minutes=2)
        model.release.set()
    await asyncio.wait_for(task, 15)
    job = await only_job(app, uid)
    assert (job.status, job.skip_reason) == ("skipped", "quiet_hours")
    assert await proactive_messages(app, uid) == []
    assert len(model.calls) == (1 if cross_during_generation else 0)
