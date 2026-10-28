"""Detached daily liability: atomic reservations, uncertain charges, purge-proof budget (GE-07.2)."""

import asyncio
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select, update

from tests.guest_helpers import add_guest

LIMIT = 1_000  # tiny synthetic fixture amount (nano-USD), not an approved production figure
LIFETIME = timedelta(seconds=7200)

PRICING = {
    "ai": {
        "pricing_version": "synthetic-v1",
        "input_nano_per_token": 2,
        "cached_nano_per_token": 1,
        "output_nano_per_token": 5,
        "max_input_tokens": 100,
    },
    "voice": {"pricing_version": "synthetic-v1", "nano_per_second": 7, "quantum_seconds": 15},
    "embed": {"pricing_version": "synthetic-v1", "nano_per_request": 11},
}


class FixtureSettings:
    def __init__(self, **values):
        self.guest_paid_enabled = values.get("paid", True)
        self.guest_daily_budget_usd = values.get("budget", Decimal("0.000001"))
        self.guest_pricing_json = values.get("pricing", PRICING)


# ---- pure: unset budget / unknown price fail closed ----------------------------------------------


def test_unset_budget_or_unknown_price_fails_closed():
    from app.modules.guests import pricing

    assert pricing.budget_nano(None) is None and pricing.budget_nano(Decimal(0)) is None
    assert pricing.budget_nano(Decimal("0.000001")) == 1_000
    for settings in (
        FixtureSettings(paid=False),
        FixtureSettings(budget=None),
        FixtureSettings(budget=Decimal(0)),
        FixtureSettings(pricing={}),
    ):
        assert not any(pricing.kind_available(settings, kind) for kind in ("ai", "voice", "embed"))
    assert all(pricing.kind_available(FixtureSettings(), kind) for kind in ("ai", "voice", "embed"))
    # A partial, negative, zero, boolean or non-integer price makes only that kind unavailable.
    broken = {"ai": {**PRICING["ai"], "output_nano_per_token": 0}, "voice": {**PRICING["voice"], "quantum_seconds": True}, "embed": {**PRICING["embed"], "nano_per_request": "11"}}
    for kind in ("ai", "voice", "embed"):
        assert not pricing.kind_available(FixtureSettings(pricing=broken), kind)
    assert pricing.ai_upper({"ai": {**PRICING["ai"], "pricing_version": ""}}) is None
    assert not pricing.kind_available(FixtureSettings(), "unknown")


def test_upper_bounds_are_conservative_and_exact():
    from app.modules.guests import pricing

    # 3 requests * (100 tokens * max(2,1) + 1200 * 5)
    assert pricing.ai_upper(PRICING) == ("synthetic-v1", 3 * (100 * 2 + 1200 * 5))
    # 14.2 s bills in 15 s quanta; exactly 15 s is one quantum; 15.001 s rounds up to two.
    assert pricing.voice_upper(PRICING, 14.2) == ("synthetic-v1", 15 * 7)
    assert pricing.voice_upper(PRICING, 15.0) == ("synthetic-v1", 15 * 7)
    assert pricing.voice_upper(PRICING, 15.001) == ("synthetic-v1", 30 * 7)
    assert pricing.voice_upper(PRICING, 0) is None
    assert pricing.embed_upper(PRICING) == ("synthetic-v1", 11)
    assert pricing.actual_ai_cost(PRICING, 50, 20, 10) == 30 * 2 + 20 * 1 + 10 * 5
    assert pricing.actual_ai_cost({}, 1, 0, 1) is None


def test_voice_bound_keeps_fractional_sample_above_quantum():
    from app.modules.guests.pricing import voice_upper

    assert voice_upper(PRICING, 15.0) == ("synthetic-v1", 105)
    assert voice_upper(PRICING, 120001 / 8000) == ("synthetic-v1", 210)
    assert voice_upper(PRICING, 30.0) == ("synthetic-v1", 210)


# ---- database: reservations ----------------------------------------------------------------------


async def reserve(app, guest, upper, key=None, digest="d" * 64, limit=LIMIT):
    from app.infrastructure.database.models import User
    from app.modules.guests.accounting import reserve_guest_operation

    async with app.state.database.sessions.begin() as db:
        user = await db.get(User, guest.user_id)
        return await reserve_guest_operation(
            db, user, "ai", upper, operation_key=key or str(uuid4()), payload_digest=digest, limit_nano_usd=limit
        )


async def run(app, call):
    async with app.state.database.sessions.begin() as db:
        return await call(db)


async def today_row(app):
    from app.modules.guests.models import GuestBudgetDay

    async with app.state.database.sessions() as db:
        return (await db.scalars(select(GuestBudgetDay).order_by(GuestBudgetDay.day.desc()))).first()


@pytest.mark.postgres
async def test_budget_reservations_prevent_concurrent_overshoot(clients):
    from app.core.errors import DomainError

    app, _ = clients
    guests = [await add_guest(app) for _ in range(8)]

    async def attempt(guest):
        try:
            return await reserve(app, guest, 300)
        except DomainError as error:
            return error.code

    results = await asyncio.gather(*(attempt(guest) for guest in guests))
    assert sum(not isinstance(r, str) for r in results) == 3
    assert results.count("GUEST_BUDGET_EXHAUSTED") == 5
    day = await today_row(app)
    assert day.spent_nano_usd + day.reserved_nano_usd <= day.limit_nano_usd
    assert (day.reserved_nano_usd, day.spent_nano_usd) == (900, 0)


@pytest.mark.postgres
async def test_replay_of_one_operation_reserves_once(clients):
    from app.core.errors import DomainError

    app, _ = clients
    guest = await add_guest(app)
    first = await reserve(app, guest, 300, key="same")
    second = await reserve(app, guest, 300, key="same")
    assert first.id == second.id and (await today_row(app)).reserved_nano_usd == 300
    with pytest.raises(DomainError) as conflict:
        await reserve(app, guest, 300, key="same", digest="e" * 64)
    assert conflict.value.status == 409


@pytest.mark.postgres
async def test_uncertain_spend_charges_upper_once(clients):
    from app.modules.guests.accounting import mark_guest_dispatched, settle_guest_operation
    from app.modules.guests.models import GuestCostReservation

    app, _ = clients
    guest = await add_guest(app)
    reservation = await reserve(app, guest, 300)
    await run(app, lambda db: mark_guest_dispatched(db, reservation.id))
    await run(app, lambda db: settle_guest_operation(db, reservation, None))  # timeout / crash
    row = await today_row(app)
    assert (row.spent_nano_usd, row.reserved_nano_usd) == (300, 0)
    async with app.state.database.sessions() as db:
        stored = await db.get(GuestCostReservation, reservation.id)
    assert stored.state == "uncertain" and stored.charged_nano_usd == stored.upper_nano_usd
    # A repeat, and a late "actual" figure, never change an uncertain charge.
    await run(app, lambda db: settle_guest_operation(db, reservation, None))
    await run(app, lambda db: settle_guest_operation(db, reservation, 10))
    assert (await today_row(app)).spent_nano_usd == 300


@pytest.mark.postgres
async def test_known_actual_overrun_and_release_semantics(clients):
    from app.core.errors import DomainError
    from app.modules.guests.accounting import (
        mark_guest_dispatched,
        release_guest_operation,
        settle_guest_operation,
    )

    app, _ = clients
    guest = await add_guest(app)
    cheap = await reserve(app, guest, 300)
    await run(app, lambda db: mark_guest_dispatched(db, cheap.id))
    await run(app, lambda db: settle_guest_operation(db, cheap, 120))
    await run(app, lambda db: settle_guest_operation(db, cheap, 200))  # duplicate: no-op
    assert ((await today_row(app)).spent_nano_usd, (await today_row(app)).reserved_nano_usd) == (120, 0)

    never = await reserve(app, guest, 300)  # definite no-dispatch is released once, not charged
    await run(app, lambda db: release_guest_operation(db, never.id))
    await run(app, lambda db: release_guest_operation(db, never.id))
    assert ((await today_row(app)).spent_nano_usd, (await today_row(app)).reserved_nano_usd) == (120, 0)

    over = await reserve(app, guest, 300)
    await run(app, lambda db: mark_guest_dispatched(db, over.id))
    await run(app, lambda db: settle_guest_operation(db, over, 450))  # actual > upper
    row = await today_row(app)
    assert row.spent_nano_usd == 570 and row.halted_at is not None
    with pytest.raises(DomainError) as halted:
        await reserve(app, guest, 1)
    assert halted.value.code == "GUEST_PAID_UNAVAILABLE", "an overrun halts paid admission until reviewed"


@pytest.mark.postgres
async def test_purging_all_guests_cannot_reopen_daily_budget(clients):
    from app.core.errors import DomainError
    from app.infrastructure.database.models import Base, User
    from app.modules.guests.accounting import mark_guest_dispatched
    from app.modules.guests.lifecycle import purge_guest
    from app.modules.guests.models import GuestBudgetDay, GuestCleanupJob, GuestCostReservation

    app, _ = clients
    guests = [await add_guest(app) for _ in range(3)]
    for guest in guests:
        reservation = await reserve(app, guest, 300)
        await run(app, lambda db, r=reservation: mark_guest_dispatched(db, r.id))
    before = await today_row(app)
    assert (before.spent_nano_usd, before.reserved_nano_usd) == (0, 900)

    # Every guest expires and is purged while their paid work is still unsettled.
    async with app.state.database.sessions.begin() as db:
        for guest in guests:
            await db.execute(text_expire(guest))
    for guest in guests:
        token = uuid4()
        async with app.state.database.sessions.begin() as db:
            await db.execute(
                update(GuestCleanupJob)
                .where(GuestCleanupJob.user_id == guest.user_id)
                .values(state="running", lease_token=token, lease_until=func.clock_timestamp() + timedelta(seconds=30))
            )
        async with app.state.database.sessions.begin() as db:
            assert await purge_guest(db, guest.user_id, token) == "removed"
    async with app.state.database.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(User).where(User.account_kind == "guest")) == 0
    row = await today_row(app)
    assert (row.spent_nano_usd, row.reserved_nano_usd) == (900, 0), "in-flight work is charged uncertain"

    newcomer = await add_guest(app)
    with pytest.raises(DomainError) as blocked:
        await reserve(app, newcomer, 300)
    assert blocked.value.status == 429 and blocked.value.code == "GUEST_BUDGET_EXHAUSTED"

    # The retained accounting rows carry no user, run, provider, session or address column.
    for table in (GuestBudgetDay, GuestCostReservation):
        names = " ".join(column.name for column in table.__table__.columns)
        for forbidden in ("user", "run", "provider", "session", "ip", "address", "subject"):
            assert forbidden not in names, (table.__tablename__, forbidden)
    assert Base.metadata.tables["moodprint.guest_budget_days"].foreign_keys == set()


def text_expire(guest):
    from app.infrastructure.database.models import User

    return (
        update(User)
        .where(User.id == guest.user_id)
        .values(status="deleting")
    )


@pytest.mark.postgres
async def test_late_settlement_charges_the_original_day_and_never_recreates_owner(clients):
    from app.modules.guests.accounting import settle_guest_operation
    from app.modules.guests.models import GuestBudgetDay, GuestCostReservation, GuestOperationLink

    app, _ = clients
    yesterday = date.today() - timedelta(days=1)
    reservation_id = uuid4()
    async with app.state.database.sessions.begin() as db:
        # Calendar midnight passed while the call was in flight; the owner was already purged.
        db.add(GuestBudgetDay(day=yesterday, limit_nano_usd=LIMIT, reserved_nano_usd=300))
        await db.flush()
        db.add(
            GuestCostReservation(
                id=reservation_id, day=yesterday, kind="ai", upper_nano_usd=300, state="dispatched"
            )
        )
    await run(app, lambda db: settle_guest_operation(db, reservation_id, 100))
    async with app.state.database.sessions() as db:
        days = (await db.scalars(select(GuestBudgetDay))).all()
        links = await db.scalar(select(func.count()).select_from(GuestOperationLink))
    assert [(d.day, d.spent_nano_usd, d.reserved_nano_usd) for d in days] == [(yesterday, 100, 0)]
    assert links == 0, "a late settlement recreates no user-linked row"


@pytest.mark.postgres
async def test_stale_reservations_become_uncertain_never_replayed(clients):
    from app.modules.guests.accounting import mark_guest_dispatched, settle_stale_reservations
    from app.modules.guests.models import GuestCostReservation

    app, _ = clients
    guest = await add_guest(app)
    lost = await reserve(app, guest, 300)  # reserved, never dispatched: released
    sent = await reserve(app, guest, 300)  # dispatched, worker died: charged
    await run(app, lambda db: mark_guest_dispatched(db, sent.id))
    async with app.state.database.sessions.begin() as db:
        await db.execute(update(GuestCostReservation).values(lease_until=func.clock_timestamp() - timedelta(seconds=1)))
    assert await run(app, settle_stale_reservations) == 2
    row = await today_row(app)
    assert (row.spent_nano_usd, row.reserved_nano_usd) == (300, 0)
    assert await run(app, settle_stale_reservations) == 0
    del lost


@pytest.mark.postgres
async def test_unset_budget_blocks_reservation_in_the_database_layer(clients):
    from app.core.errors import DomainError

    app, _ = clients
    guest = await add_guest(app)
    with pytest.raises(DomainError) as closed:
        await reserve(app, guest, 300, limit=0)
    assert closed.value.code == "GUEST_PAID_UNAVAILABLE"
    assert await today_row(app) is None, "an unset budget never creates a spend-enabled row"


@pytest.mark.postgres
async def test_retention_expires_counters_and_resolved_records_but_never_live_liability(clients):
    from app.modules.guests import jobs
    from app.modules.guests.models import GuestAbuseBucket, GuestBudgetDay, GuestCostReservation

    app, _ = clients
    old = date.today() - timedelta(days=40)
    recent = date.today() - timedelta(days=2)
    async with app.state.database.sessions.begin() as db:
        db.add_all(
            [
                GuestBudgetDay(day=old, limit_nano_usd=LIMIT),
                GuestBudgetDay(day=recent, limit_nano_usd=LIMIT),
                GuestBudgetDay(day=old - timedelta(days=1), limit_nano_usd=LIMIT, reserved_nano_usd=300),
            ]
        )
        await db.flush()
        db.add(
            GuestCostReservation(
                id=uuid4(), day=old - timedelta(days=1), kind="ai", upper_nano_usd=300,
                state="dispatched", lease_until=func.clock_timestamp() - timedelta(days=39),
            )
        )
        db.add(
            GuestCostReservation(
                id=uuid4(), day=recent, kind="ai", upper_nano_usd=1, charged_nano_usd=1,
                state="settled", lease_until=func.clock_timestamp() - timedelta(hours=30),
            )
        )
        db.add(
            GuestAbuseBucket(
                scope="intent", key_hash="a" * 64, window_start=func.clock_timestamp() - timedelta(days=2),
                count=1, expires_at=func.clock_timestamp() - timedelta(days=1),
            )
        )
    removed = await jobs.retention_tick(app)
    assert removed == {"buckets": 1, "reservations": 1, "days": 1}
    async with app.state.database.sessions() as db:
        days = {d.day for d in (await db.scalars(select(GuestBudgetDay))).all()}
        live = await db.scalar(select(func.count()).select_from(GuestCostReservation))
    assert old not in days and recent in days
    assert (old - timedelta(days=1)) in days and live == 1, "outstanding liability keeps its day"
