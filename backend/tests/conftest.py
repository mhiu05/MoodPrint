import asyncio
import hashlib
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

SESSION_HELPER = (
    Path(__file__).resolve().parents[1] / "app/infrastructure/database/provider_session.sql"
).read_text(encoding="utf-8")


def _identity_helper() -> str:
    import importlib.util

    path = Path(__file__).resolve().parents[1] / "alembic/versions/0010_account_deletion.py"
    spec = importlib.util.spec_from_file_location("migration_0010", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.FUNCTION_SQL


IDENTITY_HELPER = _identity_helper()


def pytest_configure(config):
    # The user's editable .env must never turn synthetic tests into live calls.
    os.environ.update(
        {
            "APP_ENV": "test",
            "DATABASE_URL": "",
            "DATABASE_MIGRATION_URL": "",
            "SUPABASE_URL": "",
            "SUPABASE_PUBLISHABLE_KEY": "",
            "OPENAI_API_KEY": "",
            "OPENAI_MODEL": "",
            "AI_ENABLED": "false",
            "VOYAGE_API_KEY": "",
            "SEMANTIC_MEMORY_ENABLED": "false",
            "VOYAGE_DIMENSIONS": "1024",
        }
    )


def pytest_asyncio_loop_factories(config, item):
    return {"selector": asyncio.SelectorEventLoop}


@pytest.fixture
async def database():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL must identify a disposable real PostgreSQL database")
    from tests.database_target import require_local_test_database

    require_local_test_database(url)
    from app.ai import (
        embedding_models,  # noqa: F401
        memory_models,  # noqa: F401
    )
    from app.ai import models as chat_models  # noqa: F401
    from app.infrastructure.database.models import Base
    from app.modules.moderation import models as safety_models  # noqa: F401
    from app.modules.social import models  # noqa: F401 -- register every table before reset
    from app.modules.users import models as lifecycle_models  # noqa: F401

    engine = create_async_engine(url, connect_args={"prepare_threshold": None})
    async with engine.begin() as conn:
        # Tests run only against an explicitly named disposable DB, never DATABASE_URL.
        name = await conn.scalar(text("select current_database()"))
        if not name or not name.endswith("_test"):
            raise RuntimeError("Integration tests require a database name ending _test")
        await conn.execute(text("create schema if not exists moodprint"))
        await conn.execute(text("create schema if not exists extensions"))
        await conn.execute(text("create extension if not exists vector with schema extensions"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("create schema if not exists auth"))
        await conn.execute(
            text(
                "create table if not exists auth.sessions (id uuid primary key, user_id uuid not null)"
            )
        )
        await conn.execute(text("truncate auth.sessions"))
        await conn.execute(text("create table if not exists auth.users (id uuid primary key)"))
        await conn.execute(text("truncate auth.users"))
        await conn.execute(
            text(SESSION_HELPER.replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1))
        )
        await conn.execute(text(IDENTITY_HELPER))
    yield engine
    await engine.dispose()


@pytest.fixture
async def clients(database):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.core.config import Settings
    from app.infrastructure.database.models import AuthSession, Consent, User
    from app.main import create_app

    app = create_app(Settings(_env_file=None, database_url=str(database.url.render_as_string(hide_password=False))))
    # Using the injected engine keeps test teardown and application queries on the same event loop.
    await app.state.database.engine.dispose()
    app.state.database.engine = database
    app.state.database.sessions = async_sessionmaker(database, expire_on_commit=False)
    actors = []
    for index in range(2):
        uid, sid = uuid4(), uuid4()
        token, csrf = f"test-session-{index}-{uuid4()}", f"csrf-{uuid4()}"
        async with app.state.database.sessions.begin() as db:
            db.add(User(id=uid, auth_subject=uid, alias=f"User {index}", age_band="adult"))
            await db.flush()
            db.add(
                AuthSession(
                    user_id=uid,
                    token_hash=hashlib.sha256(token.encode()).hexdigest(),
                    csrf_hash=hashlib.sha256(csrf.encode()).hexdigest(),
                    provider_session_id=sid,
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                )
            )
            for purpose in ("AI", "MEM", "MATCH", "VOICE"):
                db.add(Consent(user_id=uid, purpose=purpose, enabled=False, version=1))
            await db.execute(
                text("insert into auth.sessions(id,user_id) values (:id,:uid)"),
                {"id": sid, "uid": uid},
            )
        client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
        client.cookies.set("moodprint_session", token)
        client.headers["X-CSRF-Token"] = csrf
        actors.append((client, uid))
    yield app, actors
    for client, _ in actors:
        await client.aclose()
    await app.state.ai.close()


@pytest.fixture
def write_headers():
    return {"Idempotency-Key": str(uuid4())}
