from uuid import uuid4

import pytest


@pytest.mark.postgres
async def test_fee_liability_survives_identity_and_run_deletion(clients):
    from sqlalchemy import delete, select

    from app.ai.search.accounting import external_liability
    from app.ai.search.maps_jobs import detach_searches
    from app.ai.search.models import AiSearchUsage
    from app.infrastructure.database.models import AiRun, now

    app, actors = clients
    _, uid = actors[0]
    rid = uuid4()
    async with app.state.database.sessions.begin() as db:
        db.add(AiRun(id=rid, user_id=uid, conversation_id=uuid4(), bot_id="dieuphoi"))
        await db.flush()
        operation = AiSearchUsage(user_id=uid, parent_run_id=rid, provider="openai_web",
             reservation_nano_usd=10_000_000, pricing_version="test-v1", state="uncertain")
        db.add(operation)
    async with app.state.database.sessions.begin() as db:
        await db.execute(delete(AiRun).where(AiRun.id == rid))
        await detach_searches(db, uid)  # Real account deletion tombstones users, rather than deleting them.
    async with app.state.database.sessions() as db:
        assert await external_liability(db, now()) == 10_000_000
        row = await db.scalar(select(AiSearchUsage))
        assert row.user_id is None and row.parent_run_id is None


@pytest.mark.postgres
async def test_atomic_shared_user_concurrency_and_unknown_tokens_cross_midnight(clients):
    import asyncio
    from datetime import timedelta

    from sqlalchemy import select

    from app.ai.search.accounting import claim, external_liability
    from app.ai.search.models import AiSearchUsage
    from app.core.errors import DomainError
    from app.infrastructure.database.models import AiRun, User, now

    app, actors = clients
    uid = actors[0][1]
    s = app.state.settings
    s.ai_web_search_enabled = s.ai_accounting_enabled = s.ai_multi_message_enabled = True
    s.openai_model, s.ai_daily_budget_usd = "gpt-6-luna", 20
    s.ai_web_search_token_bound_verified, s.ai_web_search_pricing_version = True, "test-bound"
    async def reserve():
        try:
            async with app.state.database.sessions.begin() as db:
                user = await db.scalar(select(User).where(User.id == uid).with_for_update())
                run = AiRun(user_id=uid, conversation_id=uuid4(), bot_id="hoatdong")
                db.add(run)
                await db.flush()
                row = await claim(db, s, user, run.id, "openai_web")
                return row.id
        except DomainError as error:
            return error.code
    results = await asyncio.gather(reserve(), reserve())
    assert sum(value == "SEARCH_QUOTA" for value in results) == 1
    async with app.state.database.sessions.begin() as db:
        row = await db.scalar(select(AiSearchUsage).where(AiSearchUsage.user_id == uid))
        row.created_at = now()-timedelta(days=5)
        row.state, row.actual_nano_usd = "settled", 10_000_000
        row.active = False
        row.tokens_uncertain = True
    async with app.state.database.sessions() as db:
        assert await external_liability(db, now()) == 2_010_000_000


WEB_FEE, TOKENS = 10_000_000, 2_000_000_000


def web_settings(app):
    s = app.state.settings
    s.ai_web_search_enabled = s.ai_accounting_enabled = s.ai_multi_message_enabled = True
    s.openai_model, s.ai_daily_budget_usd, s.ai_search_daily_budget_usd = "gpt-6-luna", 20, 5
    s.ai_web_search_token_bound_verified, s.ai_web_search_pricing_version = True, "test-bound"
    return s


async def web_operation(app, uid, *, child_usage=None, state="settled", age_days=0, fallback=TOKENS):
    """One Web operation; ``child_usage`` is (estimated, usage state, usage age days) or None."""
    from datetime import timedelta

    from app.ai.accounting import CAPPED_PRICING_VERSION
    from app.ai.search.models import AiSearchUsage
    from app.infrastructure.database.models import AiRun, AiUsage, now

    parent, child = uuid4(), uuid4()
    async with app.state.database.sessions.begin() as db:
        db.add(AiRun(id=parent, user_id=uid, conversation_id=uuid4(), bot_id="hoatdong", status="completed"))
        db.add(AiRun(id=child, user_id=uid, conversation_id=None, bot_id="hoatdong", origin="agent",
                     parent_run_id=parent, status="completed"))
        await db.flush()
        if child_usage is not None:
            estimated, usage_state, usage_age = child_usage
            db.add(AiUsage(run_id=child, user_id=uid, worker_id=uuid4(), model="gpt-6-luna",
                           prompt_version="isolated-web-v1", pricing_version=CAPPED_PRICING_VERSION,
                           estimated_nano_usd=estimated, state=usage_state, requests_started=1,
                           responses_received=1, input_tokens=10, output_tokens=10,
                           lease_until=now(), created_at=now() - timedelta(days=usage_age)))
        db.add(AiSearchUsage(user_id=uid, parent_run_id=parent, child_run_id=child, provider="openai_web",
                             state=state, active=False, reservation_nano_usd=WEB_FEE,
                             actual_nano_usd=WEB_FEE if state == "settled" else None,
                             token_liability_nano_usd=fallback, tokens_uncertain=state != "settled",
                             pricing_version="test-bound", call_count=1,
                             created_at=now() - timedelta(days=age_days)))
    return parent, child


async def totals(app):
    from app.ai.accounting import budget_liability
    from app.ai.search.accounting import external_liability
    from app.infrastructure.database.models import now

    async with app.state.database.sessions() as db:
        at = now()
        return await budget_liability(db, at), await external_liability(db, at, subset=True)


@pytest.mark.postgres
@pytest.mark.parametrize("usage_state", ["settled", "uncertain"])
async def test_attached_child_tokens_count_once_in_global_and_subset(clients, usage_state):
    app, actors = clients
    web_settings(app)
    await web_operation(app, actors[0][1], child_usage=(300_000_000, usage_state, 0), state="uncertain")
    global_total, subset = await totals(app)
    # Child tokens via AiUsage only (never also the 2 USD fallback), plus the unknown fee once.
    assert global_total == subset == 300_000_000 + WEB_FEE


@pytest.mark.postgres
async def test_detached_child_uses_fallback_once_after_run_and_usage_deletion(clients):
    from sqlalchemy import delete

    from app.infrastructure.database.models import AiRun
    app, actors = clients
    web_settings(app)
    _, child = await web_operation(app, actors[0][1], child_usage=(300_000_000, "uncertain", 0), state="uncertain")
    async with app.state.database.sessions.begin() as db:
        await db.execute(delete(AiRun).where(AiRun.id == child))  # Cascades the AiUsage row.
    global_total, subset = await totals(app)
    assert global_total == subset == TOKENS + WEB_FEE


@pytest.mark.postgres
async def test_midnight_window_and_released_old_tokens_keep_subset_inside_global(clients):
    app, actors = clients
    uid = actors[0][1]
    web_settings(app)
    await web_operation(app, uid, child_usage=(100_000_000, "settled", 1), age_days=1)  # yesterday: carried
    await web_operation(app, uid, child_usage=(100_000_000, "settled", 3), age_days=3)  # released
    # An old fee that is still unknown stays; its old settled tokens are released in both views.
    await web_operation(app, uid, child_usage=(100_000_000, "settled", 4), state="uncertain", age_days=4)
    global_total, subset = await totals(app)
    assert global_total == subset == (100_000_000 + WEB_FEE) + WEB_FEE


@pytest.mark.postgres
async def test_tombstone_retention_and_flags_off_keep_unknown_liability(clients):
    from app.ai.search.accounting import recover_searches
    from app.ai.search.maps_jobs import detach_searches
    app, actors = clients
    uid = actors[0][1]
    settings = web_settings(app)
    await web_operation(app, uid, child_usage=(250_000_000, "uncertain", 0), state="uncertain")
    before = await totals(app)
    async with app.state.database.sessions.begin() as db:
        await detach_searches(db, uid)
        await recover_searches(db)  # Retention/startup reconcile must not refund or replay.
    settings.ai_web_search_enabled = settings.ai_maps_search_enabled = False
    assert await totals(app) == before == (250_000_000 + WEB_FEE, 250_000_000 + WEB_FEE)


@pytest.mark.postgres
async def test_daily_cap_and_global_concurrency_are_atomic(clients):
    import asyncio

    from sqlalchemy import func, select, update

    from app.ai.search.accounting import claim
    from app.ai.search.models import AiSearchUsage
    from app.core.errors import DomainError
    from app.infrastructure.database.models import AiRun, User

    app, actors = clients
    settings = web_settings(app)

    async def reserve(uid):
        try:
            async with app.state.database.sessions.begin() as db:
                user = await db.scalar(select(User).where(User.id == uid).with_for_update())
                run = AiRun(user_id=uid, conversation_id=uuid4(), bot_id="hoatdong")
                db.add(run)
                await db.flush()
                return (await claim(db, settings, user, run.id, "openai_web")).id
        except DomainError as error:
            return error.code

    async def finish_all():
        async with app.state.database.sessions.begin() as db:
            await db.execute(update(AiSearchUsage).values(active=False, state="settled", actual_nano_usd=0,
                                                          token_liability_nano_usd=0, tokens_uncertain=False))

    first, second = actors[0][1], actors[1][1]
    settings.ai_search_global_concurrency = 1
    results = await asyncio.gather(reserve(first), reserve(second))
    assert sorted(map(str, results)).count("SEARCH_QUOTA") == 1  # 1 global slot, never 2.
    await finish_all()
    settings.ai_search_global_concurrency = 2
    for _ in range(4):
        assert not isinstance(await reserve(first), str)
        await finish_all()
    # Whether or not the first user won the race above, today ends at exactly five operations.
    async with app.state.database.sessions() as db:
        used = await db.scalar(select(func.count()).select_from(AiSearchUsage).where(AiSearchUsage.user_id == first))
    for _ in range(5 - used):
        assert not isinstance(await reserve(first), str)
        await finish_all()
    assert await reserve(first) == "SEARCH_QUOTA"
    assert not isinstance(await reserve(second), str)  # Another user's day is independent.
