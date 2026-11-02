"""Guest money is a purge-proof subset of the registered/global ceiling."""

from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.ai.accounting import budget_liability, reserve_accounting
from app.core.config import Settings
from app.core.errors import DomainError
from app.infrastructure.database.models import AiRun, User, now
from app.modules.guests.accounting import reserve_guest_operation
from app.modules.guests.models import GuestBudgetDay
from app.modules.guests.pricing import kind_available
from tests.guest_helpers import add_guest

PRICES = {"ai": {"pricing_version": "openai-conservative-2026-11-02-v1",
                  "input_nano_per_token": 550, "cached_nano_per_token": 550,
                  "output_nano_per_token": 1650, "max_input_tokens": 922000}}
UPPER = 1_527_240_000


def capped_settings(**overrides):
    return Settings(_env_file=None, ai_daily_budget_usd=20, ai_accounting_enabled=True,
                    openai_model="gpt-6-luna", guest_paid_enabled=True,
                    guest_daily_budget_usd=Decimal(5), guest_pricing_json=PRICES, **overrides)


def test_capped_guest_prices_require_real_model_bound_and_only_ai():
    settings = capped_settings()
    assert kind_available(settings, "ai")
    settings.guest_pricing_json = {"ai": {**PRICES["ai"], "max_input_tokens": 100}}
    assert not kind_available(settings, "ai")
    settings.guest_pricing_json = {**PRICES, "voice": {"pricing_version": "unfunded", "nano_per_second": 1, "quantum_seconds": 1}}
    assert not kind_available(settings, "voice")


@pytest.mark.postgres
async def test_detached_guest_liability_counts_without_guest_identity(clients):
    app, _ = clients
    async with app.state.database.sessions.begin() as db:
        db.add(GuestBudgetDay(day=now().date(), limit_nano_usd=5_000_000_000,
                              spent_nano_usd=1_000_000_000, reserved_nano_usd=UPPER))
    async with app.state.database.sessions() as db:
        assert await budget_liability(db, now()) == 2_527_240_000


async def reserve(app, guest, settings):
    async with app.state.database.sessions.begin() as db:
        owner = await db.scalar(select(User).where(User.id == guest.user_id).with_for_update())
        return await reserve_guest_operation(db, owner, "ai", UPPER, operation_key=str(uuid4()),
            payload_digest="d" * 64, limit_nano_usd=5_000_000_000, settings=settings)


@pytest.mark.postgres
async def test_parallel_guest_reservations_stop_at_five_dollars(clients):
    import asyncio

    app, _ = clients
    guests = [await add_guest(app) for _ in range(5)]

    async def attempt(guest):
        try:
            await reserve(app, guest, capped_settings())
            return True
        except DomainError as error:
            assert error.code == "GUEST_BUDGET_EXHAUSTED"
            return False

    assert (await asyncio.gather(*(attempt(guest) for guest in guests))).count(True) == 3
    async with app.state.database.sessions() as db:
        assert await budget_liability(db, now()) == 4_581_720_000


@pytest.mark.postgres
async def test_mixed_registered_guest_race_shares_one_global_reservation_lock(clients):
    import asyncio

    app, actors = clients
    settings = capped_settings()
    async with app.state.database.sessions.begin() as db:
        for _ in range(7):
            run = AiRun(id=uuid4(), user_id=actors[0][1], bot_id="may", conversation_id=uuid4(), status="completed")
            db.add(run)
            await db.flush()
            await reserve_accounting(db, run.id, run.user_id, uuid4(), "gpt-6-luna", "test", settings=settings)
    guests = [await add_guest(app) for _ in range(3)]

    async def attempt(guest=None):
        try:
            if guest is not None:
                await reserve(app, guest, settings)
                return UPPER
            async with app.state.database.sessions.begin() as db:
                run = AiRun(id=uuid4(), user_id=actors[0][1], bot_id="may", conversation_id=uuid4(), status="completed")
                db.add(run)
                await db.flush()
                await reserve_accounting(db, run.id, run.user_id, uuid4(), "gpt-6-luna", "test", settings=settings)
            return 2_000_000_000
        except DomainError as error:
            assert error.code == "AI_BUDGET_EXHAUSTED"
            return 0

    results = await asyncio.gather(*(attempt(guest) for guest in guests), *(attempt() for _ in range(3)))
    async with app.state.database.sessions() as db:
        total = await budget_liability(db, now())
    assert total == 14_000_000_000 + sum(results)
    assert 18_000_000_000 <= total <= 20_000_000_000
    assert results.count(0) >= 3


@pytest.mark.postgres
async def test_registered_and_guest_share_cap_and_purge_cannot_refund(clients):
    from sqlalchemy import func, update

    from app.modules.guests.accounting import mark_guest_dispatched
    from app.modules.guests.lifecycle import purge_guest
    from app.modules.guests.models import GuestCleanupJob

    app, actors = clients
    settings = capped_settings()
    async with app.state.database.sessions.begin() as db:
        for _ in range(9):
            run = AiRun(id=uuid4(), user_id=actors[0][1], bot_id="may", conversation_id=uuid4(), status="completed")
            db.add(run)
            await db.flush()
            await reserve_accounting(db, run.id, run.user_id, uuid4(), "gpt-6-luna", "test", settings=settings)
    guest = await add_guest(app)
    reservation = await reserve(app, guest, settings)
    async with app.state.database.sessions.begin() as db:
        await mark_guest_dispatched(db, reservation.id)
    second = await add_guest(app)
    with pytest.raises(DomainError) as blocked:
        await reserve(app, second, settings)
    assert blocked.value.code == "AI_BUDGET_EXHAUSTED"
    token = uuid4()
    async with app.state.database.sessions.begin() as db:
        await db.execute(update(User).where(User.id == guest.user_id).values(status="deleting"))
        await db.execute(update(GuestCleanupJob).where(GuestCleanupJob.user_id == guest.user_id)
                         .values(state="running", lease_token=token, lease_until=func.clock_timestamp() + timedelta(seconds=30)))
    async with app.state.database.sessions.begin() as db:
        assert await purge_guest(db, guest.user_id, token) == "removed"
    async with app.state.database.sessions() as db:
        assert await budget_liability(db, now()) == 19_527_240_000


@pytest.mark.postgres
async def test_guest_usage_metadata_is_not_counted_twice(clients):
    app, _ = clients
    guest = await add_guest(app)
    settings = capped_settings()
    reservation = await reserve(app, guest, settings)
    async with app.state.database.sessions.begin() as db:
        run = AiRun(id=uuid4(), user_id=guest.user_id, bot_id="may", conversation_id=uuid4(), status="completed")
        db.add(run)
        await db.flush()
        await reserve_accounting(db, run.id, run.user_id, uuid4(), "gpt-6-luna", "test", settings=settings,
                                 guest_reservation_id=reservation.id)
    async with app.state.database.sessions() as db:
        assert await budget_liability(db, now()) == UPPER


@pytest.mark.postgres
async def test_unfunded_guest_metadata_cannot_bypass_detached_accounting(clients):
    app, _ = clients
    guest = await add_guest(app)
    async with app.state.database.sessions.begin() as db:
        run = AiRun(id=uuid4(), user_id=guest.user_id, bot_id="may", conversation_id=uuid4(), status="completed")
        db.add(run)
        await db.flush()
        with pytest.raises(DomainError) as denied:
            await reserve_accounting(db, run.id, run.user_id, uuid4(), "gpt-6-luna", "test", settings=capped_settings())
        assert denied.value.code == "AI_BUDGET_UNAVAILABLE"


@pytest.mark.postgres
async def test_legacy_small_guest_reservation_cannot_fund_current_model(clients):
    app, _ = clients
    guest = await add_guest(app)
    async with app.state.database.sessions.begin() as db:
        owner = await db.get(User, guest.user_id)
        old = await reserve_guest_operation(db, owner, "ai", 300, operation_key="legacy-key",
            payload_digest="d" * 64, limit_nano_usd=5_000_000_000)
        run = AiRun(id=uuid4(), user_id=guest.user_id, bot_id="may", conversation_id=uuid4(), status="completed")
        db.add(run)
        await db.flush()
        with pytest.raises(DomainError) as denied:
            await reserve_accounting(db, run.id, run.user_id, uuid4(), "gpt-6-luna", "test",
                                     settings=capped_settings(), guest_reservation_id=old.id)
        assert denied.value.code == "AI_BUDGET_UNAVAILABLE"


@pytest.mark.postgres
async def test_legacy_guest_usage_cannot_disappear_from_financial_guard_on_purge(clients):
    from sqlalchemy import func, update

    from app.infrastructure.database.models import AiUsage
    from app.modules.guests.lifecycle import purge_guest
    from app.modules.guests.models import GuestCleanupJob

    app, _ = clients
    guest = await add_guest(app)
    async with app.state.database.sessions.begin() as db:
        run = AiRun(id=uuid4(), user_id=guest.user_id, bot_id="may", conversation_id=uuid4(), status="completed")
        db.add(run)
        await db.flush()
        await reserve_accounting(db, run.id, run.user_id, uuid4(), "gpt-6-luna", "legacy")
        usage = await db.get(AiUsage, run.id)
        usage.state, usage.requests_started = "uncertain", 1
    async with app.state.database.sessions() as db:
        with pytest.raises(DomainError):
            await budget_liability(db, now())
    token = uuid4()
    async with app.state.database.sessions.begin() as db:
        await db.execute(update(User).where(User.id == guest.user_id).values(status="deleting"))
        await db.execute(update(GuestCleanupJob).where(GuestCleanupJob.user_id == guest.user_id)
                         .values(state="running", lease_token=token, lease_until=func.clock_timestamp() + timedelta(seconds=30)))
    async with app.state.database.sessions.begin() as db:
        assert await purge_guest(db, guest.user_id, token) == "removed"
    async with app.state.database.sessions() as db:
        with pytest.raises(DomainError) as halted:
            await budget_liability(db, now())
        assert halted.value.code == "AI_BUDGET_UNAVAILABLE"


@pytest.mark.postgres
async def test_utc_midnight_and_retention_never_erase_guest_uncertainty(clients):
    from app.modules.guests.accounting import mark_guest_dispatched, settle_guest_operation
    from app.modules.guests.jobs import retention_tick
    from app.modules.guests.models import GuestCostReservation, GuestOperationLink

    app, _ = clients
    guest = await add_guest(app)
    reservation = await reserve(app, guest, capped_settings())
    async with app.state.database.sessions.begin() as db:
        await mark_guest_dispatched(db, reservation.id)
        await settle_guest_operation(db, reservation, None)
        row = await db.get(GuestCostReservation, reservation.id)
        row.lease_until = now() - timedelta(days=2)
        from sqlalchemy import delete

        await db.execute(delete(GuestOperationLink).where(GuestOperationLink.user_id == guest.user_id))
    await retention_tick(app)
    async with app.state.database.sessions() as db:
        assert await db.get(GuestCostReservation, reservation.id) is not None
        assert await budget_liability(db, now() + timedelta(days=10)) == UPPER


@pytest.mark.postgres
async def test_guest_real_sdk_route_settles_once_and_global_denial_never_dispatches(clients):
    from openai.types.responses.response_usage import ResponseUsage

    from app.infrastructure.database.models import AiUsage
    from tests.fakes import make_test_model
    from tests.test_guest_paid_dispatch import open_chat, send

    app, actors = clients
    configured = capped_settings()
    for name in ("ai_daily_budget_usd", "ai_accounting_enabled", "openai_model", "guest_paid_enabled",
                 "guest_daily_budget_usd", "guest_pricing_json"):
        setattr(app.state.settings, name, getattr(configured, name))
    guest = await add_guest(app, consents=True)
    model = make_test_model("A synthetic reply.")
    original = model.stream_response

    async def priced(*args, **kwargs):
        async for event in original(*args, **kwargs):
            if event.type == "response.completed":
                event.response.usage = ResponseUsage.model_validate({
                    "input_tokens": 100, "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
                    "output_tokens": 10, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 110,
                })
            yield event

    model.stream_response = priced
    created = await open_chat(app, guest, model)
    assert created.status_code == 201, created.text
    accepted = await send(app, guest, created.json())
    assert accepted.status_code == 202, accepted.text
    events = await guest.client.get(accepted.json()["eventsUrl"])
    assert "event: completed" in events.text, events.text
    import asyncio

    for _ in range(40):
        async with app.state.database.sessions() as db:
            total = await budget_liability(db, now())
        if total == 71_500:
            break
        await asyncio.sleep(0.05)
    assert total == 71_500 and len(model.calls) == 1
    async with app.state.database.sessions() as db:
        usage = (await db.scalars(select(AiUsage).where(AiUsage.user_id == guest.user_id))).one()
        assert usage.estimated_nano_usd == 71_500 and usage.state == "settled"
    # Fill global headroom with registered reservations. A later guest send must
    # fail before the SDK model, quota claim and detached cost reservation change.
    async with app.state.database.sessions.begin() as db:
        for _ in range(9):
            run = AiRun(id=uuid4(), user_id=actors[0][1], bot_id="may", conversation_id=uuid4(), status="completed")
            db.add(run)
            await db.flush()
            await reserve_accounting(db, run.id, run.user_id, uuid4(), "gpt-6-luna", "test", settings=configured)
    async with app.state.database.sessions.begin() as db:
        # Another guest's uncertain liability fits once and leaves less than a new envelope.
        from app.modules.guests.accounting import mark_guest_dispatched, settle_guest_operation

        extra_guest = await add_guest(app)
        owner = await db.get(User, extra_guest.user_id)
        extra = await reserve_guest_operation(db, owner, "ai", UPPER, operation_key=str(uuid4()),
            payload_digest="e" * 64, limit_nano_usd=5_000_000_000, settings=configured)
        await mark_guest_dispatched(db, extra.id)
        await settle_guest_operation(db, extra, None)
    another = await guest.client.post("/api/v1/ai/conversations", json={"botId": "may"},
                                     headers={"Idempotency-Key": str(uuid4())})
    refused = await send(app, guest, another.json())
    assert refused.status_code == 503 and refused.json()["error"]["code"] == "AI_BUDGET_EXHAUSTED"
    assert len(model.calls) == 1
