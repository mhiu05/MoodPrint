"""A bounded V3 workflow transfers child holds without losing unknown liability."""

from uuid import uuid4

import pytest
from sqlalchemy import select

from app.ai.accounting import UsageSnapshot, budget_liability, persist_snapshot, reserve_accounting
from app.ai.usage import UsageEvent
from app.core.errors import DomainError
from app.infrastructure.database.models import AiUsage, now
from tests.test_budget_reservations import make_run

pytestmark = pytest.mark.postgres
POOL = 280_000_000
CALL = 40_000_000


async def reserve(db, app, uid, worker, *, parent=None, role="root"):
    run = await make_run(db, uid, origin="agent" if parent else "user", parent=parent)
    run.status = "running"
    run.bot_id = "dieuphoi"
    await db.flush()
    await reserve_accounting(db, run.id, uid, worker, "gpt-6-luna", role, settings=app.state.settings)
    return run


def bounded(app):
    app.state.settings.ai_daily_budget_usd = 20
    app.state.settings.ai_accounting_enabled = True
    app.state.settings.ai_bounded_reservations_enabled = True


async def test_fifty_bounded_workflows_hold_under_twenty(clients):
    app, actors = clients
    bounded(app)
    uid, worker = actors[0][1], uuid4()
    async with app.state.database.sessions.begin() as db:
        for _ in range(50):
            parent = await reserve(db, app, uid, worker)
            for role in ("plan-planner+orchestration-v1", "consult-nhatky+orchestration-v1", "consult-hoatdong+orchestration-v1"):
                await reserve(db, app, uid, worker, parent=parent.id, role=role)
            assert await budget_liability(db, now()) <= 20_000_000_000
        assert await budget_liability(db, now()) == 50 * POOL


async def test_child_allocation_never_double_counts_and_unknown_retains_bound(clients):
    app, actors = clients
    bounded(app)
    uid, worker = actors[0][1], uuid4()
    async with app.state.database.sessions.begin() as db:
        parent = await reserve(db, app, uid, worker)
        assert await budget_liability(db, now()) == POOL
        child = await reserve(db, app, uid, worker, parent=parent.id, role="consult-nhatky+orchestration-v1")
        assert await budget_liability(db, now()) == POOL
        snapshot = UsageSnapshot()
        snapshot.observe(UsageEvent("request_started"))
        assert await persist_snapshot(db, child.id, worker, snapshot, terminal=True)
        assert (await db.get(AiUsage, child.id)).estimated_nano_usd == CALL
        assert await persist_snapshot(db, parent.id, worker, UsageSnapshot(), terminal=True)
        assert await budget_liability(db, now()) == CALL


@pytest.mark.parametrize("change", ["worker", "owner", "terminal", "expired", "unknown_role", "exhausted"])
async def test_child_cannot_borrow_invalid_or_exhausted_parent_hold(clients, change):
    from datetime import timedelta

    app, actors = clients
    bounded(app)
    uid, worker = actors[0][1], uuid4()
    async with app.state.database.sessions.begin() as db:
        parent = await reserve(db, app, uid, worker)
        usage = await db.get(AiUsage, parent.id)
        if change == "terminal":
            usage.state = "settled"
        elif change == "expired":
            usage.lease_until = now() - timedelta(seconds=1)
        elif change == "exhausted":
            for _ in range(4):
                await reserve(db, app, uid, worker, parent=parent.id, role="consult-nhatky+orchestration-v1")
        await db.flush()
    async with app.state.database.sessions.begin() as db:
        with pytest.raises(DomainError):
            await reserve(db, app, actors[1][1] if change == "owner" else uid,
                          uuid4() if change == "worker" else worker, parent=parent.id,
                          role="unknown" if change == "unknown_role" else "consult-nhatky+orchestration-v1")
    async with app.state.database.sessions() as db:
        # A rejected allocation must never lower the parent's hold.
        holds = (await db.scalars(select(AiUsage))).all()
        assert sum(row.estimated_nano_usd for row in holds) == POOL


async def test_parallel_child_transfers_cannot_reuse_settled_allocations(clients):
    import asyncio

    app, actors = clients
    bounded(app)
    uid, worker = actors[0][1], uuid4()
    async with app.state.database.sessions.begin() as db:
        parent = await reserve(db, app, uid, worker)

    async def child():
        try:
            async with app.state.database.sessions.begin() as db:
                run = await reserve(db, app, uid, worker, parent=parent.id,
                                    role="consult-nhatky+orchestration-v1")
                assert await persist_snapshot(db, run.id, worker, UsageSnapshot(), terminal=True)
            return True
        except DomainError as error:
            assert error.code == "AI_BUDGET_UNAVAILABLE"
            return False

    outcomes = await asyncio.gather(*(child() for _ in range(8)))
    assert outcomes.count(True) == 4
    async with app.state.database.sessions() as db:
        assert await budget_liability(db, now()) == 120_000_000


async def test_restart_retains_unknown_child_when_undispatched_parent_expires(clients):
    from datetime import timedelta

    from sqlalchemy import update

    from app.ai.accounting import recover_expired

    app, actors = clients
    bounded(app)
    uid, worker = actors[0][1], uuid4()
    async with app.state.database.sessions.begin() as db:
        parent = await reserve(db, app, uid, worker)
        child = await reserve(db, app, uid, worker, parent=parent.id,
                              role="consult-nhatky+orchestration-v1")
        snapshot = UsageSnapshot()
        snapshot.observe(UsageEvent("request_started"))
        assert await persist_snapshot(db, child.id, worker, snapshot)
        await db.execute(update(AiUsage).values(lease_until=now() - timedelta(seconds=1)))
    for _ in range(2):
        async with app.state.database.sessions.begin() as db:
            await recover_expired(db)
        async with app.state.database.sessions() as db:
            assert await budget_liability(db, now() + timedelta(days=3)) == CALL


async def test_planner_then_unknown_handoff_retains_allocated_three_call_hold(clients):
    app, actors = clients
    bounded(app)
    uid, worker = actors[0][1], uuid4()
    async with app.state.database.sessions.begin() as db:
        parent = await reserve(db, app, uid, worker)
        planner = await reserve(db, app, uid, worker, parent=parent.id,
                                role="plan-planner+orchestration-v1")
        assert await persist_snapshot(db, planner.id, worker, UsageSnapshot(), terminal=True)
        child = await reserve(db, app, uid, worker, parent=parent.id,
                              role="handoff-nhatky+orchestration-v1")
        assert (await db.get(AiUsage, parent.id)).estimated_nano_usd == 120_000_000
        snapshot = UsageSnapshot()
        snapshot.observe(UsageEvent("request_started"))
        assert await persist_snapshot(db, child.id, worker, snapshot, terminal=True)
        assert await persist_snapshot(db, parent.id, worker, UsageSnapshot(), terminal=True)
        assert await budget_liability(db, now()) == 120_000_000


@pytest.mark.parametrize("dispatch_enabled", [False, True])
@pytest.mark.parametrize("scenario", ["consult_both", "handoff"])
async def test_real_sdk_uses_pooled_parent_and_children(clients, dispatch_enabled, scenario):
    from app.ai.pooled_accounting import (
        POOL_CALL_VERSION,
        POOL_HANDOFF_VERSION,
        POOL_ROOT_VERSION,
    )
    from app.ai.provider import SdkProvider
    from tests.test_orchestration_sdk import (
        test_consult_both_specialists_through_real_as_tool,
        test_handoff_rebuilds_the_input_and_the_specialist_answers,
    )

    app, _ = clients
    bounded(app)
    app.state.settings.openai_model = "gpt-6-luna"
    await app.state.ai.provider.aclose()
    app.state.ai.provider = SdkProvider(app.state.settings)
    if scenario == "consult_both":
        await test_consult_both_specialists_through_real_as_tool(clients, dispatch_enabled)
    else:
        app.state.settings.ai_dispatch_gate_enabled = dispatch_enabled
        await test_handoff_rebuilds_the_input_and_the_specialist_answers(clients)
    async with app.state.database.sessions() as db:
        rows = (await db.scalars(select(AiUsage))).all()
        assert [row.pricing_version for row in rows].count(POOL_ROOT_VERSION) == 2
        assert [row.pricing_version for row in rows].count(POOL_CALL_VERSION) == (3 if scenario == "consult_both" else 1)
        assert [row.pricing_version for row in rows].count(POOL_HANDOFF_VERSION) == (0 if scenario == "consult_both" else 1)
        # The handoff proof also sends a third turn directly to the specialist.
        assert await budget_liability(db, now()) <= 2 * POOL + (120_000_000 if scenario == "handoff" else 0)
