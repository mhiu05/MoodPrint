"""Single-worker load fixture for mood/matching/human-chat. Synthetic users only."""
# ruff: noqa: E402 -- sanitize configuration before importing application modules

import asyncio
import hashlib
import os
import time
from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, uuid5

from tests.database_target import require_local_test_database

DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")
require_local_test_database(DATABASE_URL)
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
        "STT_ENABLED": "false",
        "VOYAGE_API_KEY": "",
        "SEMANTIC_MEMORY_ENABLED": "false",
    }
)

import uvicorn
from sqlalchemy import event, text

from app.ai import (
    embedding_models,  # noqa: F401 -- register every table before reset
    memory_models,  # noqa: F401
)
from app.ai import models as chat_models  # noqa: F401
from app.core.config import Settings
from app.infrastructure.database.models import AuthSession, Base, Consent, User
from app.main import create_app
from app.modules.guests import models as guest_models  # noqa: F401
from app.modules.moderation import models as safety_models  # noqa: F401
from app.modules.social import models as social_models  # noqa: F401
from app.modules.users import models as lifecycle_models  # noqa: F401
from tests.guest_schema import install_auth_fixture, install_guest_guards

USERS = int(os.environ.get("MOODPRINT_LOAD_USERS", "50"))
PORT = int(os.environ.get("MOODPRINT_LOAD_PORT", "8005"))

def identity(kind: str, number: int):
    return uuid5(NAMESPACE_URL, f"moodprint-social-load:{kind}:{number}")


# Production pool defaults (config.py); the driver samples checked-out connections.
app = create_app(
    Settings(
        _env_file=None,
        app_env="test",
        database_url=DATABASE_URL,
        frontend_origin=f"http://127.0.0.1:{PORT}",
        # Beta feature set (J-02): shared activities on, scorer chosen by the driver.
        activities_enabled=True,
        matching_scorer=os.environ.get("MOODPRINT_LOAD_SCORER", "v2"),
    )
)

# Local fixture instrumentation only: no SQL text, parameters or account data.
sql_count = 0
sql_seconds = 0.0


@event.listens_for(app.state.database.engine.sync_engine, "before_cursor_execute")
def before_sql(conn, cursor, statement, parameters, context, executemany):
    context._load_started = time.perf_counter()


@event.listens_for(app.state.database.engine.sync_engine, "after_cursor_execute")
def after_sql(conn, cursor, statement, parameters, context, executemany):
    global sql_count, sql_seconds
    sql_count += 1
    sql_seconds += time.perf_counter() - context._load_started


@app.get("/__load/pool", include_in_schema=False)
async def pool_state():
    pool = app.state.database.engine.pool
    return {
        "checkedOut": pool.checkedout(),
        "overflow": pool.overflow(),
        "size": pool.size(),
        "sqlCount": sql_count,
        "sqlSeconds": round(sql_seconds, 3),
        "processCpuSeconds": round(time.process_time(), 3),
    }


async def seed():
    async with app.state.database.engine.begin() as connection:
        await connection.execute(text("create schema if not exists moodprint"))
        await connection.execute(text("create schema if not exists extensions"))
        await connection.execute(
            text("create extension if not exists vector with schema extensions")
        )
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
        await install_guest_guards(connection)
        await install_auth_fixture(connection)
    async with app.state.database.sessions.begin() as db:
        for number in range(USERS):
            uid, provider = identity("user", number), identity("provider", number)
            db.add(User(id=uid, auth_subject=uid, alias=f"Tải {number}", age_band="adult"))
            await db.flush()
            for purpose in ("AI", "MEM", "MATCH", "VOICE"):
                db.add(Consent(user_id=uid, purpose=purpose, enabled=False, version=1))
            db.add(
                AuthSession(
                    user_id=uid,
                    token_hash=hashlib.sha256(f"load-session-{number}".encode()).hexdigest(),
                    csrf_hash=hashlib.sha256(f"load-csrf-{number}".encode()).hexdigest(),
                    provider_session_id=provider,
                    expires_at=datetime.now(UTC) + timedelta(hours=2),
                )
            )
            await db.execute(
                text("insert into auth.sessions(id,user_id) values (:id,:uid)"),
                {"id": provider, "uid": uid},
            )
    await app.state.database.engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed(), loop_factory=asyncio.SelectorEventLoop)
    uvicorn.run(
        app, host="127.0.0.1", port=PORT, loop="app.core.loop:selector_factory", log_config=None
    )
