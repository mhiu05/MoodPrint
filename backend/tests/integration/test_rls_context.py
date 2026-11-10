"""Exercise transaction-scoped claims on real PostgreSQL, never a hosted DB.

Break caught: omitting SET LOCAL, rollback, or the RLS role switch leaks rows
between requests reusing the two-connection pool.
"""

import asyncio
import json
import os
from collections.abc import AsyncIterator
from dataclasses import replace
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from app.core.db import create_engine
from app.core.uow import user_uow
from dotenv import dotenv_values
from moodprint_shared.config import AppConfig
from moodprint_shared.contracts.auth import AuthContext
from moodprint_shared.env import EnvSettings
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

pytestmark = pytest.mark.integration


def _local_url(name: str) -> str:
    value = os.environ.get(name) or dotenv_values(
        Path(__file__).resolve().parents[3] / ".local/test.env"
    ).get(name)
    if not value:
        pytest.fail(f"{name} missing; run scripts/dev/bootstrap_local_db.py")
    url = make_url(value)
    if url.host not in {"127.0.0.1", "localhost", "::1"}:
        pytest.fail(f"{name} must use loopback; hosted integration tests forbidden")
    return str(url.set(drivername="postgresql+asyncpg").render_as_string(hide_password=False))


def _auth(user_id: UUID) -> AuthContext:
    return AuthContext(
        user_id=user_id,
        session_id=None,
        aal="aal1",
        claims_json=json.dumps({"sub": str(user_id), "role": "authenticated"}),
    )


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    database_url = _local_url("TEST_DATABASE_URL")
    # Explicit constructor values and _env_file=None prevent any hosted .env read.
    settings = EnvSettings(
        _env_file=None,
        app_env="test",
        database_url=database_url,
        supabase_url="http://127.0.0.1:54321",
        supabase_publishable_key="local-test-only",
        supabase_secret_key="local-test-only",
    )
    cfg = AppConfig()
    cfg = replace(cfg, api=replace(cfg.api, db_pool_size=2, db_max_overflow=0))
    result = create_engine(settings, cfg)
    try:
        yield result
    finally:
        await result.dispose()


@pytest_asyncio.fixture
async def owners() -> AsyncIterator[list[UUID]]:
    admin = create_async_engine(_local_url("TEST_ADMIN_DATABASE_URL"))
    user_ids = [uuid4() for _ in range(50)]
    try:
        async with admin.begin() as connection:
            for index, user_id in enumerate(user_ids):
                await connection.execute(
                    text("insert into auth.users(id) values (:id)"), {"id": user_id}
                )
                await connection.execute(
                    text("insert into app.profiles(user_id,nickname) values (:id,:name)"),
                    {"id": user_id, "name": f"Synthetic {index}"},
                )
        yield user_ids
    finally:
        async with admin.begin() as connection:
            await connection.execute(
                text("delete from auth.users where id = any(:ids)"), {"ids": user_ids}
            )
        await admin.dispose()


async def _assert_clean(engine: AsyncEngine) -> None:
    # Check both pooled physical connections, including the one just returned.
    async with engine.connect() as first, engine.connect() as second:
        for connection in (first, second):
            row = (
                await connection.execute(
                    text("select current_user,current_setting('request.jwt.claims',true)")
                )
            ).one()
            assert row[0] == "moodprint_api"
            assert row[1] in {None, ""}
            # The login has no auth schema privilege. Verify the identity on the
            # same physical connection after a role switch, without new claims.
            await connection.execute(text("SET LOCAL ROLE authenticated"))
            assert await connection.scalar(text("select auth.uid()")) is None


@pytest.mark.asyncio
async def test_auth_uid_matches_context(engine: AsyncEngine, owners: list[UUID]) -> None:
    async with user_uow(engine, _auth(owners[0])) as uow:
        row = (await uow.session.execute(text("select current_user,auth.uid()"))).one()
        assert row[0] == "authenticated"
        assert row[1] == owners[0]


@pytest.mark.asyncio
async def test_owner_only_sees_own_rows(engine: AsyncEngine, owners: list[UUID]) -> None:
    async with user_uow(engine, _auth(owners[0])) as uow:
        ids = (await uow.session.execute(text("select user_id from app.profiles"))).scalars().all()
        assert ids == [owners[0]]


@pytest.mark.asyncio
async def test_claims_cleared_after_commit(engine: AsyncEngine, owners: list[UUID]) -> None:
    async with user_uow(engine, _auth(owners[0])) as uow:
        await uow.session.execute(text("select auth.uid()"))
    await _assert_clean(engine)


@pytest.mark.asyncio
async def test_rollback_clears_role(engine: AsyncEngine, owners: list[UUID]) -> None:
    with pytest.raises(RuntimeError, match="synthetic rollback"):
        async with user_uow(engine, _auth(owners[0])) as uow:
            await uow.session.execute(
                text("update app.profiles set nickname='Rolled back' where user_id=:id"),
                {"id": owners[0]},
            )
            raise RuntimeError("synthetic rollback")
    await _assert_clean(engine)
    async with user_uow(engine, _auth(owners[0])) as uow:
        assert await uow.session.scalar(text("select nickname from app.profiles")) == "Synthetic 0"


@pytest.mark.asyncio
async def test_concurrent_users_never_share_claims(engine: AsyncEngine, owners: list[UUID]) -> None:
    async def request(user_id: UUID) -> None:
        async with user_uow(engine, _auth(user_id)) as uow:
            before = await uow.session.scalar(text("select auth.uid()"))
            await uow.session.execute(text("select pg_sleep(0.005)"))
            rows = (
                (await uow.session.execute(text("select user_id from app.profiles")))
                .scalars()
                .all()
            )
            after = await uow.session.scalar(text("select auth.uid()"))
            assert before == after == user_id
            assert rows == [user_id]

    await asyncio.gather(*(request(owner) for owner in owners))
    await _assert_clean(engine)


@pytest.mark.asyncio
async def test_no_transaction_held_outside_block(engine: AsyncEngine, owners: list[UUID]) -> None:
    async with user_uow(engine, _auth(owners[0])) as uow:
        await uow.session.execute(text("select 1"))
    assert engine.pool.checkedout() == 0
    async with engine.connect() as connection:
        assert not connection.in_transaction()


@pytest.mark.asyncio
async def test_second_reconciler_skips_locked_rows(engine: AsyncEngine, owners: list[UUID]) -> None:
    conversation_id, run_id = uuid4(), uuid4()
    auth = _auth(owners[0])
    async with user_uow(engine, auth) as uow:
        await uow.session.execute(
            text("insert into app.conversations(id,owner_id) values(:id,:owner)"),
            {"id": conversation_id, "owner": auth.user_id},
        )
        await uow.session.execute(
            text(
                "insert into app.agent_runs(id,conversation_id,owner_id,model,prompt_version,tools_version,heartbeat_at) values(:id,:conversation,:owner,'synthetic','v1','v1',now()-interval '1 hour')"
            ),
            {"id": run_id, "conversation": conversation_id, "owner": auth.user_id},
        )
    admin = create_async_engine(_local_url("TEST_ADMIN_DATABASE_URL"))
    try:
        async with admin.begin() as lock:
            await lock.execute(
                text("select id from app.agent_runs where id=:id for update"), {"id": run_id}
            )
            async with asyncio.timeout(2), engine.begin() as background:
                await background.execute(
                    text("select app_private.reconcile_stale_runs(interval '3 minutes')")
                )
            # Without SKIP LOCKED the background call times out above.
            assert (
                await lock.scalar(
                    text("select status from app.agent_runs where id=:id"), {"id": run_id}
                )
                == "running"
            )
        async with engine.begin() as background:
            await background.execute(
                text("select app_private.reconcile_stale_runs(interval '3 minutes')")
            )
        async with user_uow(engine, auth) as uow:
            assert (
                await uow.session.scalar(
                    text("select status from app.agent_runs where id=:id"), {"id": run_id}
                )
                == "interrupted"
            )
    finally:
        await admin.dispose()
