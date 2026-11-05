"""Conservative liability must survive partial usage, crashes and quota races."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.ai.accounting import UsageSnapshot, persist_snapshot, reserve_accounting
from app.ai.usage import UsageEvent
from app.core.config import Settings
from app.core.errors import DomainError
from app.infrastructure.database.models import AiRun, AiUsage, now


class RowSession:
    """Only replace database I/O; exercise real snapshot settlement on an ORM row."""

    def __init__(self, row):
        self.row = row

    async def scalar(self, statement):
        return self.row

    async def flush(self):
        pass


def reserved_row():
    return AiUsage(
        run_id=uuid4(), user_id=uuid4(), worker_id=uuid4(), model="gpt-6-luna",
        prompt_version="test", pricing_version="openai-conservative-2026-11-02-v1",
        input_nano_rate=550, cached_nano_rate=550, output_nano_rate=1650,
        estimated_nano_usd=2_000_000_000, state="open", sequence=0,
        requests_started=0, responses_received=0, input_tokens=0,
        cached_input_tokens=0, output_tokens=0, tool_calls=0,
        lease_until=now() + timedelta(seconds=45),
    )


@pytest.mark.parametrize("terminal", [False, True])
async def test_incomplete_response_never_releases_reserved_liability(terminal):
    row = reserved_row()
    snapshot = UsageSnapshot()
    snapshot.observe(UsageEvent(kind="request_started"))
    await persist_snapshot(RowSession(row), row.run_id, row.worker_id, snapshot, terminal=terminal)
    assert row.estimated_nano_usd == 2_000_000_000
    assert row.state == ("uncertain" if terminal else "open")


async def test_complete_partial_snapshot_keeps_envelope_until_terminal():
    row = reserved_row()
    snapshot = UsageSnapshot()
    snapshot.observe(UsageEvent(kind="request_started"))
    snapshot.observe(UsageEvent(kind="response_received", input_tokens=100, output_tokens=10))
    db = RowSession(row)
    await persist_snapshot(db, row.run_id, row.worker_id, snapshot)
    assert row.estimated_nano_usd == 2_000_000_000
    await persist_snapshot(db, row.run_id, row.worker_id, snapshot, terminal=True)
    assert row.state == "settled" and row.estimated_nano_usd == 71_500


def test_response_without_usage_is_not_financially_known():
    snapshot = UsageSnapshot()
    snapshot.observe(UsageEvent(kind="request_started"))
    snapshot.observe(UsageEvent(kind="response_received"))
    assert snapshot.responses_received == 0


def test_capped_provider_rejects_differently_priced_override_before_client_creation():
    from app.ai.provider import SdkProvider

    settings = Settings(_env_file=None, ai_daily_budget_usd=20, ai_accounting_enabled=True,
                        openai_model="gpt-6-luna", openai_api_key="synthetic", ai_enabled=True)
    provider = SdkProvider(settings)
    with pytest.raises(DomainError) as denied:
        provider.model("unpriced-model", uuid4())
    assert denied.value.code == "AI_BUDGET_UNAVAILABLE"
    assert provider._client is None


async def make_run(db, uid, *, origin="user", parent=None, created=None):
    run = AiRun(id=uuid4(), user_id=uid, conversation_id=uuid4() if origin == "user" else None,
                bot_id="may", origin=origin, parent_run_id=parent, status="completed",
                created_at=created or now())
    db.add(run)
    await db.flush()
    return run


@pytest.mark.postgres
@pytest.mark.parametrize("budget,attempts,accepted", [(20, 12, 10), (50, 30, 25)])
async def test_parallel_admissions_reserve_the_configured_legacy_budget(clients, budget, attempts, accepted):
    import asyncio

    app, actors = clients
    settings = Settings(_env_file=None, ai_daily_budget_usd=budget, ai_accounting_enabled=True)

    async def attempt():
        try:
            async with app.state.database.sessions.begin() as db:
                run = await make_run(db, actors[0][1])
                await reserve_accounting(db, run.id, run.user_id, uuid4(), "gpt-6-luna", "test", settings=settings)
            return True
        except DomainError as error:
            assert error.code == "AI_BUDGET_EXHAUSTED"
            return False

    outcomes = await asyncio.gather(*(attempt() for _ in range(attempts)))
    assert outcomes.count(True) == accepted
    async with app.state.database.sessions() as db:
        assert await db.scalar(select(func.sum(AiUsage.estimated_nano_usd))) == budget * 1_000_000_000


@pytest.mark.postgres
async def test_fifty_bounded_parents_and_children_reserve_atomically_under_fifty(clients):
    import asyncio

    from app.ai.accounting import budget_liability
    from app.ai.envelope import BOUNDED_RESERVATION_NANO

    app, actors = clients
    settings = Settings(_env_file=None, ai_daily_budget_usd=50, ai_accounting_enabled=True,
                        ai_bounded_reservations_enabled=True)

    async def workflow():
        async with app.state.database.sessions.begin() as db:
            parent = await make_run(db, actors[0][1])
            await reserve_accounting(db, parent.id, parent.user_id, uuid4(), "gpt-6-luna", "test", settings=settings)
            for _ in range(2):
                child = await make_run(db, actors[0][1], origin="agent", parent=parent.id)
                await reserve_accounting(db, child.id, child.user_id, uuid4(), "gpt-6-luna", "test", settings=settings)
    await asyncio.gather(*(workflow() for _ in range(50)))
    async with app.state.database.sessions() as db:
        assert await budget_liability(db, now()) == 150 * BOUNDED_RESERVATION_NANO
        assert await budget_liability(db, now()) <= 50_000_000_000


@pytest.mark.postgres
async def test_child_runs_unknown_models_and_unknown_history_cannot_bypass_cap(clients):
    app, actors = clients
    settings = Settings(_env_file=None, ai_daily_budget_usd=2, ai_accounting_enabled=True)
    async with app.state.database.sessions.begin() as db:
        parent = await make_run(db, actors[0][1])
        await reserve_accounting(db, parent.id, parent.user_id, uuid4(), "gpt-6-luna", "test", settings=settings)
    with pytest.raises(DomainError) as denied:
        async with app.state.database.sessions.begin() as db:
            child = await make_run(db, actors[0][1], origin="agent", parent=parent.id)
            await reserve_accounting(db, child.id, child.user_id, uuid4(), "gpt-6-luna", "planner", settings=settings)
    assert denied.value.code == "AI_BUDGET_EXHAUSTED"
    with pytest.raises(DomainError) as unknown:
        async with app.state.database.sessions.begin() as db:
            run = await make_run(db, actors[0][1])
            await reserve_accounting(db, run.id, run.user_id, uuid4(), "unpriced-model", "test", settings=settings)
    assert unknown.value.code == "AI_BUDGET_UNAVAILABLE"
    async with app.state.database.sessions.begin() as db:
        await db.execute(AiUsage.__table__.update().values(estimated_nano_usd=None))
    settings.ai_daily_budget_usd = 20
    with pytest.raises(DomainError) as history:
        async with app.state.database.sessions.begin() as db:
            run = await make_run(db, actors[0][1])
            await reserve_accounting(db, run.id, run.user_id, uuid4(), "gpt-6-luna", "test", settings=settings)
    assert history.value.code == "AI_BUDGET_UNAVAILABLE"


@pytest.mark.postgres
async def test_yesterday_and_unresolved_liability_carries_across_midnight(clients):
    from app.ai.persistence import spent_today_nano

    app, actors = clients
    settings = Settings(_env_file=None, ai_daily_budget_usd=20, ai_accounting_enabled=True)
    async with app.state.database.sessions.begin() as db:
        run = await make_run(db, actors[0][1])
        await reserve_accounting(db, run.id, run.user_id, uuid4(), "gpt-6-luna", "test", settings=settings)
        row = await db.get(AiUsage, run.id)
        row.created_at = datetime(2026, 11, 1, 23, 59, tzinfo=UTC)
        row.state = "settled"
    async with app.state.database.sessions() as db:
        assert await spent_today_nano(db, datetime(2026, 11, 2, 0, 1, tzinfo=UTC)) == 2_000_000_000
    async with app.state.database.sessions.begin() as db:
        row = await db.get(AiUsage, run.id)
        row.state = "uncertain"
    async with app.state.database.sessions() as db:
        assert await spent_today_nano(db, datetime(2026, 12, 1, tzinfo=UTC)) == 2_000_000_000


@pytest.mark.postgres
async def test_crash_retains_dispatched_envelope_and_releases_definite_no_dispatch(clients):
    from app.ai.accounting import recover_expired

    app, actors = clients
    settings = Settings(_env_file=None, ai_daily_budget_usd=20, ai_accounting_enabled=True)
    ids = []
    async with app.state.database.sessions.begin() as db:
        for started, received in ((0, 0), (1, 0), (1, 1)):
            run = await make_run(db, actors[0][1])
            await reserve_accounting(db, run.id, run.user_id, uuid4(), "gpt-6-luna", "test", settings=settings)
            row = await db.get(AiUsage, run.id)
            row.requests_started, row.responses_received = started, received
            row.lease_until = now() - timedelta(seconds=1)
            ids.append(run.id)
    async with app.state.database.sessions.begin() as db:
        await recover_expired(db)
    async with app.state.database.sessions() as db:
        rows = [await db.get(AiUsage, identity) for identity in ids]
        assert [(row.state, row.estimated_nano_usd) for row in rows] == [
            ("settled", 0), ("uncertain", 2_000_000_000), ("settled", 2_000_000_000),
        ]


@pytest.mark.postgres
async def test_proactive_children_leave_interactive_budget_available(clients):
    app, actors = clients
    settings = Settings(_env_file=None, ai_daily_budget_usd=20, ai_accounting_enabled=True)
    async with app.state.database.sessions.begin() as db:
        parent = AiRun(id=uuid4(), user_id=actors[0][1], conversation_id=None, bot_id="may",
                       origin="proactive", proactive_slot="morning", status="completed")
        db.add(parent)
        await db.flush()
        await reserve_accounting(db, parent.id, parent.user_id, uuid4(), "gpt-6-luna", "proactive", settings=settings)
        for _ in range(4):
            child = await make_run(db, actors[0][1], origin="collaboration", parent=parent.id)
            await reserve_accounting(db, child.id, child.user_id, uuid4(), "gpt-6-luna", "specialist", settings=settings)
    with pytest.raises(DomainError) as denied:
        async with app.state.database.sessions.begin() as db:
            child = await make_run(db, actors[0][1], origin="collaboration", parent=parent.id)
            await reserve_accounting(db, child.id, child.user_id, uuid4(), "gpt-6-luna", "specialist", settings=settings)
    assert denied.value.code == "AI_BUDGET_EXHAUSTED"
    async with app.state.database.sessions.begin() as db:
        run = await make_run(db, actors[1][1])
        await reserve_accounting(db, run.id, run.user_id, uuid4(), "gpt-6-luna", "interactive", settings=settings)


@pytest.mark.postgres
async def test_account_purge_cannot_reopen_reserved_budget(clients):
    from sqlalchemy import text

    from app.ai.persistence import spent_today_nano
    from app.infrastructure.database.models import User
    from app.modules.journal.models import JournalEntry
    from app.modules.users.lifecycle import process_deletions
    from app.modules.users.models import DataJob

    app, actors = clients
    uid = actors[0][1]
    settings = app.state.settings
    settings.ai_daily_budget_usd, settings.ai_accounting_enabled = 20, True
    async with app.state.database.sessions.begin() as db:
        run = await make_run(db, uid)
        await reserve_accounting(db, run.id, uid, uuid4(), "gpt-6-luna", "test", settings=settings)
        db.add(JournalEntry(user_id=uid, timezone="Asia/Bangkok", local_date=now().date(),
                            text="private content to purge", mood=3, status="saved"))
        db.add(DataJob(user_id=uid, kind="deletion", scope="account", status="queued"))
        await db.execute(text("insert into auth.users(id) values (:id) on conflict (id) do nothing"), {"id": uid})
    await process_deletions(app)
    async with app.state.database.sessions() as db:
        assert (await db.get(User, uid)).status == "deleted"
        assert await db.scalar(select(func.count()).select_from(JournalEntry).where(JournalEntry.user_id == uid)) == 0
        assert await spent_today_nano(db, now()) == 2_000_000_000
