"""Durable check-in queue (P1-12): materialize, claim, lease, retry, expiry, two workers."""

import asyncio
from datetime import date, time, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select, text, update

from app.jobs import proactive as worker
from tests.fakes import make_test_model


def ready(app, **overrides):
    app.state.settings.proactive_enabled = True
    app.state.settings.proactive_worker_enabled = True
    app.state.ai.model_override = make_test_model("ok")
    for name, value in overrides.items():
        setattr(app.state.settings, name, value)


async def schedule(app, uid, *, bot="nhip", slot="morning", due=None, local_time=time(7, 30), **fields):
    from app.ai.proactive.models import AiProactiveSchedule, AiProactiveSettings
    from app.infrastructure.database.models import now

    async with app.state.database.sessions.begin() as db:
        if await db.get(AiProactiveSettings, uid) is None:
            db.add(AiProactiveSettings(user_id=uid, timezone="Asia/Ho_Chi_Minh"))
        row = AiProactiveSchedule(user_id=uid, bot_id=bot, slot=slot, enabled=True,
                                  local_time=local_time, next_due_at=due or now(), **fields)
        db.add(row)
    return row.id


async def jobs(app, uid=None):
    from app.ai.proactive.models import AiProactiveJob

    async with app.state.database.sessions() as db:
        statement = select(AiProactiveJob).order_by(AiProactiveJob.created_at)
        if uid:
            statement = statement.where(AiProactiveJob.user_id == uid)
        return (await db.scalars(statement)).all()


async def db_now(app):
    async with app.state.database.sessions() as db:
        return await db.scalar(select(text("clock_timestamp()")))


class Recorder:
    """Fake executor: records claims and delivers through a real run row."""

    def __init__(self, outcome="delivered", delay=0.0):
        self.claims = []
        self.outcome = outcome
        self.delay = delay
        self.active = self.peak = 0

    async def __call__(self, runtime, claimed):
        from app.infrastructure.database.models import AiRun

        self.claims.append(claimed.id)
        self.active += 1
        self.peak = max(self.peak, self.active)
        await asyncio.sleep(self.delay)
        self.active -= 1
        run_id = None
        async with worker.transaction(runtime.database) as db:
            if self.outcome == "delivered":
                run_id = uuid4()
                db.add(AiRun(id=run_id, user_id=claimed.user_id, bot_id=claimed.bot_id, status="completed",
                             origin="proactive", proactive_slot=claimed.slot, conversation_id=None))
                await db.flush()
            await worker.finish(db, claimed, self.outcome, run_id=run_id,
                                reason="guardrail" if self.outcome == "skipped" else None)


async def test_tick_does_nothing_while_worker_flag_is_off(clients):
    app, [(_client, uid), _] = clients
    ready(app, proactive_worker_enabled=False)
    await schedule(app, uid)
    result = await worker.proactive_tick(app.state.ai, execute=Recorder())
    assert result == {"enabled": False}
    assert await jobs(app) == []


async def test_materialize_creates_one_pending_job_and_advances_schedule(clients):
    from app.ai.proactive.models import AiProactiveSchedule

    app, [(_client, uid), _] = clients
    ready(app)
    at = await db_now(app)
    await schedule(app, uid, due=at - timedelta(minutes=1))
    async with worker.transaction(app.state.database) as db:
        assert await worker.materialize_due(db, app.state.settings, at) == 1
    [job] = await jobs(app)
    assert job.status == "pending" and job.attempts == 0
    assert job.expires_at - job.due_at == timedelta(minutes=90)
    assert job.local_date == worker.local_date(job.due_at, "Asia/Ho_Chi_Minh")
    async with app.state.database.sessions() as db:
        row = await db.scalar(select(AiProactiveSchedule))
    assert row.next_due_at > at
    async with worker.transaction(app.state.database) as db:
        assert await worker.materialize_due(db, app.state.settings, at) == 0


async def test_missed_window_after_long_downtime_creates_no_backlog(clients):
    from app.ai.proactive.models import AiProactiveSchedule

    app, [(_client, uid), _] = clients
    ready(app)
    at = await db_now(app)
    await schedule(app, uid, due=at - timedelta(days=2))
    async with worker.transaction(app.state.database) as db:
        await worker.materialize_due(db, app.state.settings, at)
        await worker.materialize_due(db, app.state.settings, at)
    [job] = await jobs(app)
    assert (job.status, job.skip_reason) == ("skipped", "missed_window")
    async with app.state.database.sessions() as db:
        row = await db.scalar(select(AiProactiveSchedule))
    assert at < row.next_due_at <= at + timedelta(days=1)


async def test_auto_paused_schedule_advances_without_jobs(clients):
    from app.infrastructure.database.models import now

    app, [(_client, uid), _] = clients
    ready(app)
    at = await db_now(app)
    await schedule(app, uid, due=at - timedelta(minutes=1), auto_paused_at=now())
    async with worker.transaction(app.state.database) as db:
        assert await worker.materialize_due(db, app.state.settings, at) == 0
    assert await jobs(app) == []


async def test_two_workers_deliver_exactly_once(clients):
    from app.ai.runtime import AiRuntime

    app, [(_client, uid), _] = clients
    ready(app)
    await schedule(app, uid, due=(await db_now(app)) - timedelta(seconds=5))
    other = AiRuntime(app.state.settings, app.state.database)
    other.model_override = app.state.ai.model_override
    executor = Recorder(delay=0.2)
    for _ in range(2):
        await asyncio.gather(worker.proactive_tick(app.state.ai, execute=executor),
                             worker.proactive_tick(other, execute=executor))
    [job] = await jobs(app)
    assert job.status == "delivered" and job.run_id is not None
    assert len(executor.claims) == 1


async def claim(app, runtime=None, at=None):
    runtime = runtime or app.state.ai
    async with worker.transaction(app.state.database) as db:
        return await worker.claim_job(db, app.state.settings, runtime.worker_id, at or await db_now(app))


async def test_expired_lease_is_reclaimed_and_stale_worker_is_fenced(clients):
    from app.ai.runtime import AiRuntime

    app, [(_client, uid), _] = clients
    ready(app)
    at = await db_now(app)
    await schedule(app, uid, due=at - timedelta(seconds=5))
    async with worker.transaction(app.state.database) as db:
        await worker.materialize_due(db, app.state.settings, at)
    first = await claim(app)
    assert first.attempts == 1
    assert await claim(app) is None  # lease still valid
    later = at + timedelta(seconds=worker.LEASE_SECONDS + 1)
    other = AiRuntime(app.state.settings, app.state.database)
    second = await claim(app, other, at=later)
    assert second.id == first.id and second.attempts == 2 and second.lease_token != first.lease_token
    async with worker.transaction(app.state.database) as db:
        assert await worker.finish(db, first, "failed", error="stale") is False
        assert await worker.finish(db, second, "skipped", reason="guardrail") is True
    [job] = await jobs(app)
    assert (job.status, job.skip_reason) == ("skipped", "guardrail")


async def test_attempts_exhausted_fails_on_reclaim(clients):
    from app.ai.proactive.models import AiProactiveJob

    app, [(_client, uid), _] = clients
    ready(app, proactive_max_attempts=2)
    at = await db_now(app)
    await schedule(app, uid, due=at - timedelta(seconds=5))
    async with worker.transaction(app.state.database) as db:
        await worker.materialize_due(db, app.state.settings, at)
        await db.execute(update(AiProactiveJob).values(attempts=2, status="retry"))
    assert await claim(app) is None
    [job] = await jobs(app)
    assert (job.status, job.last_error) == ("failed", "attempts_exhausted")


async def test_expired_pending_job_is_skipped(clients):
    from app.ai.proactive.models import AiProactiveJob

    app, [(_client, uid), _] = clients
    ready(app)
    at = await db_now(app)
    await schedule(app, uid, due=at - timedelta(seconds=5))
    async with worker.transaction(app.state.database) as db:
        await worker.materialize_due(db, app.state.settings, at)
    async with worker.transaction(app.state.database) as db:
        await db.execute(update(AiProactiveJob).values(
            due_at=at - timedelta(hours=3), expires_at=at - timedelta(hours=1)))
        await worker.expire_stale(db, at)
    [job] = await jobs(app)
    assert (job.status, job.skip_reason) == ("skipped", "expired")


async def test_one_running_job_per_user(clients):
    app, [(_client, uid), (_other, other_uid)] = clients
    ready(app)
    at = await db_now(app)
    await schedule(app, uid, bot="nhip", due=at - timedelta(seconds=9))
    await schedule(app, uid, bot="may", due=at - timedelta(seconds=8))
    await schedule(app, other_uid, bot="may", due=at - timedelta(seconds=7))
    async with worker.transaction(app.state.database) as db:
        assert await worker.materialize_due(db, app.state.settings, at) == 3
    first, second = await claim(app), await claim(app)
    assert first.user_id == uid and second.user_id == other_uid
    assert await claim(app) is None


async def test_retry_backoff_and_defer_refund(clients):
    app, [(_client, uid), _] = clients
    ready(app)
    at = await db_now(app)
    await schedule(app, uid, due=at - timedelta(seconds=5))
    async with worker.transaction(app.state.database) as db:
        await worker.materialize_due(db, app.state.settings, at)
    claimed = await claim(app)
    async with worker.transaction(app.state.database) as db:
        assert await worker.retry(db, claimed, error="AI_TIMEOUT", at=at)
    [job] = await jobs(app)
    assert job.status == "retry" and job.attempts == 1
    assert job.available_at == at + timedelta(seconds=60)
    claimed = await claim(app, at=at + timedelta(seconds=61))
    async with worker.transaction(app.state.database) as db:
        assert await worker.defer(db, claimed, reason="active_chat", at=at + timedelta(seconds=61))
    [job] = await jobs(app)
    # Deferring is not a failure: the attempt is given back.
    assert job.status == "retry" and job.attempts == 1
    assert job.available_at == at + timedelta(seconds=61 + 300)


async def test_retry_past_expiry_becomes_expired(clients):
    app, [(_client, uid), _] = clients
    ready(app, proactive_grace_minutes=15)
    at = await db_now(app)
    await schedule(app, uid, due=at - timedelta(minutes=14, seconds=30))
    async with worker.transaction(app.state.database) as db:
        await worker.materialize_due(db, app.state.settings, at)
    claimed = await claim(app)
    async with worker.transaction(app.state.database) as db:
        await worker.retry(db, claimed, error="AI_TIMEOUT", at=at)
    [job] = await jobs(app)
    assert (job.status, job.skip_reason) == ("skipped", "expired")


async def test_cancelled_job_is_resurrected_when_rescheduled_the_same_day(clients):
    from app.ai.proactive.models import AiProactiveJob, AiProactiveSchedule

    app, [(_client, uid), _] = clients
    ready(app)
    at = await db_now(app)
    await schedule(app, uid, due=at - timedelta(minutes=2))
    async with worker.transaction(app.state.database) as db:
        await worker.materialize_due(db, app.state.settings, at)
        await db.execute(update(AiProactiveJob).values(status="cancelled"))
        await db.execute(update(AiProactiveSchedule).values(next_due_at=at - timedelta(minutes=1), version=2))
        assert await worker.materialize_due(db, app.state.settings, at) == 1
    [job] = await jobs(app)
    assert job.status == "pending" and job.schedule_version == 2


async def test_worker_transactions_carry_safety_timeouts(clients):
    app, _ = clients
    async with worker.transaction(app.state.database) as db:
        values = (await db.execute(text(
            "select current_setting('lock_timeout'), current_setting('statement_timeout'),"
            " current_setting('idle_in_transaction_session_timeout')"))).one()
    assert tuple(values) == ("2s", "5s", "15s")


async def test_tick_reports_metrics_without_identifiers(clients, caplog):
    import logging

    app, [(_client, uid), _] = clients
    ready(app)
    await schedule(app, uid, due=(await db_now(app)) - timedelta(seconds=5))
    with caplog.at_level(logging.INFO, logger="moodprint"):
        result = await worker.proactive_tick(app.state.ai, execute=Recorder())
    assert result["claimed"] == 1 and result["materialized"] == 1
    assert "metric=proactive_tick_ms" in caplog.text
    assert str(uid) not in caplog.text


async def test_tick_runs_up_to_configured_concurrency(clients):
    app, [(_client, uid), (_other, other_uid)] = clients
    ready(app, proactive_worker_concurrency=2)
    at = await db_now(app)
    await schedule(app, uid, due=at - timedelta(seconds=5))
    await schedule(app, other_uid, due=at - timedelta(seconds=5))
    executor = Recorder(delay=0.3)
    result = await worker.proactive_tick(app.state.ai, execute=executor)
    assert result["claimed"] == 2
    assert executor.peak == 2  # ran side by side, never more than configured


def test_health_check_reads_heartbeat_age(tmp_path):
    path = tmp_path / "beat"
    assert worker.healthy(path, max_age=60) is False
    worker.beat(path)
    assert worker.healthy(path, max_age=60) is True


@pytest.mark.parametrize("attempts,seconds", [(1, 60), (2, 120), (3, 240), (6, 900)])
def test_backoff_schedule(attempts, seconds):
    assert worker.backoff(attempts) == timedelta(seconds=seconds)


def test_local_date_reexported():
    from datetime import UTC, datetime

    assert worker.local_date(datetime(2026, 10, 31, 23, 30, tzinfo=UTC), "Asia/Ho_Chi_Minh") == date(2026, 11, 1)


def test_connection_budget_includes_the_worker():
    from app.infrastructure.database import budget

    assert budget.headroom(5, 2) == 4  # (5+2)x2 API + 2 worker of 20
    assert budget.has_deployment_headroom(5, 2) is True
    assert budget.has_deployment_headroom(5, 2, worker_connections=3) is False
    assert budget.has_deployment_headroom(5, 2, role_limit=30, worker_connections=4) is True
