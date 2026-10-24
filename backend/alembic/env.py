import asyncio
from pathlib import Path
import sys

from alembic import context
from sqlalchemy import pool, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.config import Settings
from app.infrastructure.database.models import Base
from app.modules.social import models  # Register all owned domain tables.
from app.modules.moderation import models as moderation_models  # noqa: F401
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
        await connection.commit()
        await connection.run_sync(configure)
        # Local bootstrap installs the same private helper reviewed for Supabase.
        # PL/pgSQL defers the Auth relation lookup until invocation; no Auth DDL here.
        await connection.execute(text(session_helper.replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1)))
        await connection.commit()
    await engine.dispose()


if context.is_offline_mode():
    offline()
else:
    asyncio.run(online(), loop_factory=asyncio.SelectorEventLoop)
