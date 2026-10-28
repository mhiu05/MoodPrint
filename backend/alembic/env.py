import asyncio
import sys
from pathlib import Path

from sqlalchemy import pool, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.ai import (
    embedding_models,  # noqa: F401
    memory_models,  # noqa: F401
)
from app.ai import models as chat_models  # noqa: F401
from app.core.config import Settings
from app.infrastructure.database.models import Base
from app.modules.activities import models as activity_models  # noqa: F401
from app.modules.feedback import models as feedback_models  # noqa: F401
from app.modules.guests import models as guest_models  # noqa: F401
from app.modules.moderation import models as moderation_models  # noqa: F401
from app.modules.social import models  # noqa: F401 -- register all owned domain tables
from app.modules.users import models as lifecycle_models  # noqa: F401

config = context.config
settings = Settings()
raw = settings.database_migration_url or settings.database_url
url = raw.get_secret_value() if raw else "postgresql+psycopg://localhost/moodprint"
url = url.replace("postgres://", "postgresql+psycopg://", 1).replace(
    "postgresql://", "postgresql+psycopg://", 1
)
session_helper = (Path(__file__).resolve().parents[1] / "app/infrastructure/database/provider_session.sql").read_text(encoding="utf-8")


def offline():
    context.configure(
        url=url,
        target_metadata=Base.metadata,
        literal_binds=True,
        version_table_schema="moodprint",
        include_schemas=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def configure(connection):
    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
        version_table_schema="moodprint",
        include_schemas=True,
        include_name=lambda name, type_, parent: type_ != "schema" or name == "moodprint",
    )
    with context.begin_transaction():
        context.run_migrations()


async def online():
    target = make_url(url)
    # This local workflow intentionally cannot mutate a hosted database accidentally.
    if target.host not in ("localhost", "127.0.0.1", "::1", "database"):
        raise RuntimeError(
            "Remote migrations require project/role/schema review and explicit authorization; local runner refuses this target"
        )
    engine = create_async_engine(
        url, poolclass=pool.NullPool, connect_args={"prepare_threshold": None}
    )
    async with engine.connect() as connection:
        await connection.execute(text("create schema if not exists moodprint"))
        # Local bootstrap installs the private helper reviewed for Supabase, but only when it is
        # absent and before migrations: revision 0017 replaces it with the guest-aware version, and a
        # later no-op upgrade must never overwrite that newer definition. PL/pgSQL defers the Auth
        # relation lookup until invocation; no Auth DDL here.
        exists = await connection.scalar(
            text("select to_regprocedure('moodprint.is_provider_session_active(uuid,uuid)') is not null")
        )
        if not exists:
            await connection.execute(text(session_helper))
        await connection.commit()
        await connection.run_sync(configure)
        await connection.commit()
    await engine.dispose()


if context.is_offline_mode():
    offline()
else:
    asyncio.run(online(), loop_factory=asyncio.SelectorEventLoop)
