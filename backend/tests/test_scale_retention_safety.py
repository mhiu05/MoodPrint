from datetime import timedelta
from uuid import uuid4

import pytest
from app.ai.accounting import budget_liability, reserve_accounting
from app.core.config import Settings
from app.infrastructure.database.models import AiRun, AiUsage, now
from app.jobs.retention import purge_expired


@pytest.mark.postgres
@pytest.mark.parametrize("bounded", [False, True])
async def test_retention_cannot_refund_old_unknown_child_or_parent_liability(clients, bounded):
    app, actors = clients
    settings = Settings(_env_file=None, ai_daily_budget_usd=50, openai_model="gpt-6-luna", ai_accounting_enabled=True,
                        ai_bounded_reservations_enabled=bounded)
    old = now() - timedelta(days=100)
    async with app.state.database.sessions.begin() as db:
        parent = AiRun(id=uuid4(), user_id=actors[0][1], conversation_id=uuid4(), bot_id="may",
                       origin="user", status="completed", created_at=old)
        db.add(parent)
        await db.flush()
        child = AiRun(id=uuid4(), user_id=actors[0][1], conversation_id=None, bot_id="may",
                      origin="agent", parent_run_id=parent.id, status="interrupted", created_at=old)
        db.add(child)
        await db.flush()
        await reserve_accounting(db, child.id, child.user_id, uuid4(), "gpt-6-luna", "test", settings=settings)
        row = await db.get(AiUsage, child.id)
        row.state, row.requests_started, row.created_at = "uncertain", 1, old
        parent_id, child_id = parent.id, child.id
    await purge_expired(app)
    async with app.state.database.sessions() as db:
        assert await db.get(AiRun, parent_id) is not None
        assert await db.get(AiUsage, child_id) is not None
        assert await budget_liability(db, now()) == (120_000_000 if bounded else 2_000_000_000)


@pytest.mark.postgres
async def test_registered_transaction_lock_timeout_is_local_and_bounded(clients):
    import asyncio

    from app.core.security import Actor, transaction
    from app.infrastructure.database.models import AuthSession, User
    from sqlalchemy import select, text
    from sqlalchemy.exc import DBAPIError
    from starlette.requests import Request

    app, actors = clients
    uid = actors[0][1]
    app.state.settings.database_transaction_timeouts_enabled = True
    app.state.settings.database_lock_timeout_ms = 50
    async with app.state.database.sessions() as db:
        session = await db.scalar(select(AuthSession).where(AuthSession.user_id == uid))
        actor = Actor(uid, session.id, 1)
    request = Request({"type": "http", "app": app, "headers": []})
    async with app.state.database.sessions.begin() as blocker:
        await blocker.scalar(select(User).where(User.id == uid).with_for_update())
        with pytest.raises(DBAPIError) as caught:
            async with asyncio.timeout(2):
                async with transaction(request, actor):
                    pytest.fail("Lock holder was bypassed")
        assert caught.value.orig.sqlstate == "55P03"
    async with app.state.database.sessions() as db:
        assert await db.scalar(text("show lock_timeout")) == "0"
