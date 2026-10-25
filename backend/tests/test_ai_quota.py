"""T-AIQ-01/02: daily AI turn quota (Asia/Bangkok day) and global spend ceiling."""

import logging
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.ai.persistence import admission, quota_day_start
from app.core.errors import DomainError
from app.infrastructure.database.models import AiRun, User, now

pytestmark = pytest.mark.postgres


def test_quota_day_starts_at_bangkok_midnight_not_utc():
    at = datetime(2026, 10, 25, 23, 30, tzinfo=UTC)  # 06:30 on the 26th in Bangkok
    assert quota_day_start(at) == datetime(2026, 10, 25, 17, 0, tzinfo=UTC)


async def seed_runs(app, uid, count, created_at):
    async with app.state.database.sessions.begin() as db:
        for _ in range(count):
            db.add(
                AiRun(
                    user_id=uid,
                    conversation_id=uuid4(),
                    bot_id="may",
                    status="completed",
                    created_at=created_at,
                )
            )


async def admit(app, uid, **settings):
    for name, value in settings.items():
        setattr(app.state.settings, name, value)
    async with app.state.database.sessions.begin() as db:
        user = await db.get(User, uid)
        await admission(db, user, app.state.settings)


async def test_sixty_turns_today_exhaust_the_quota_but_yesterday_does_not_count(clients):
    app, actors = clients
    uid = actors[0][1]
    start = quota_day_start(now())
    await seed_runs(app, uid, 59, start + timedelta(seconds=1))
    await seed_runs(app, uid, 5, start - timedelta(minutes=1))  # yesterday in Bangkok
    await admit(app, uid, ai_requests_per_minute=120)  # 59 today: allowed
    await seed_runs(app, uid, 1, start + timedelta(seconds=2))
    with pytest.raises(DomainError) as error:
        await admit(app, uid, ai_requests_per_minute=120)
    assert (error.value.status, error.value.code) == (429, "AI_DAILY_QUOTA")
    assert error.value.retryable is True


async def seed_usage(app, uid, nano):
    run = uuid4()
    async with app.state.database.sessions.begin() as db:
        db.add(
            AiRun(id=run, user_id=uid, conversation_id=uuid4(), bot_id="may", status="completed")
        )
        await db.flush()
        await db.execute(
            text(
                "insert into moodprint.ai_usage (run_id, user_id, worker_id, model, prompt_version,"
                " pricing_version, estimated_nano_usd, state, sequence, requests_started,"
                " responses_received, input_tokens, cached_input_tokens, output_tokens,"
                " tool_calls, lease_until, created_at) values (:run, :uid, :worker, 'm', 'p',"
                " 'v', :nano, 'settled', 0, 1, 1, 10, 0, 10, 0, now(), now())"
            ),
            {"run": run, "uid": uid, "worker": uuid4(), "nano": nano},
        )


async def test_global_budget_ceiling_and_its_off_switches(clients, caplog):
    app, actors = clients
    uid = actors[0][1]
    await seed_usage(app, uid, 800_000_000)  # 0.80 USD
    with caplog.at_level(logging.WARNING, logger="moodprint"):
        await admit(app, uid, ai_daily_budget_usd=1.0, ai_accounting_enabled=True)
    assert any("metric=ai_budget_ratio value=0.80" in r.getMessage() for r in caplog.records)
    await seed_usage(app, uid, 250_000_000)
    with pytest.raises(DomainError) as error:
        await admit(app, uid, ai_daily_budget_usd=1.0, ai_accounting_enabled=True)
    assert (error.value.status, error.value.code) == (503, "AI_BUDGET_EXHAUSTED")
    await admit(app, uid, ai_daily_budget_usd=0.0, ai_accounting_enabled=True)  # 0 = off
    await admit(app, uid, ai_daily_budget_usd=1.0, ai_accounting_enabled=False)


def test_budget_without_accounting_logs_a_startup_warning(caplog):
    from app.core.config import Settings
    from app.main import create_app

    with caplog.at_level(logging.WARNING, logger="moodprint"):
        create_app(Settings(_env_file=None, ai_daily_budget_usd=5, ai_accounting_enabled=False))
    assert any("ai_budget_unenforced" in r.getMessage() for r in caplog.records)


async def test_session_reports_remaining_turns_only_when_ai_is_available(clients):
    app, actors = clients
    client = actors[0][0]
    features = (await client.get("/api/v1/session")).json()["features"]
    assert features["ai"] is False and features["aiQuotaRemaining"] is None
