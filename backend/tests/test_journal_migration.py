"""Journal migration preserves Mood data and keeps all new tables backend private."""

import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import select, text

from app.infrastructure.database.models import Mood
from tests.test_journal import today

pytestmark = pytest.mark.postgres
MIGRATION_PATH = Path(__file__).resolve().parents[1] / "alembic/versions/0019_journal.py"


async def test_journal_upgrade_downgrade_preserves_legacy_mood_and_private_acl(clients):
    app, actors = clients
    async with app.state.database.sessions.begin() as db:
        db.add(
            Mood(
                user_id=actors[0][1],
                local_date=today(),
                value=2,
                note="untouched",
                timezone="Asia/Bangkok",
            )
        )
    spec = importlib.util.spec_from_file_location("journal_migration", MIGRATION_PATH)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    def migrate(connection):
        with Operations.context(MigrationContext.configure(connection)):
            migration.downgrade()
            migration.upgrade()

    async with app.state.database.engine.begin() as connection:
        await connection.execute(
            text("""DO $$ BEGIN
          IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='moodprint_runtime') THEN
            CREATE ROLE moodprint_runtime NOLOGIN NOBYPASSRLS; END IF;
          IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN CREATE ROLE anon NOLOGIN; END IF;
          IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN CREATE ROLE authenticated NOLOGIN; END IF;
          IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='service_role') THEN CREATE ROLE service_role NOLOGIN; END IF;
        END $$""")
        )
        await connection.run_sync(migrate)
        for table in migration.TABLES:
            assert await connection.scalar(
                text("select relrowsecurity from pg_class where oid=cast(:t as regclass)"),
                {"t": f"moodprint.{table}"},
            )
            for role in ("anon", "authenticated", "service_role"):
                assert not await connection.scalar(
                    text("select has_table_privilege(:r,:t,'SELECT,INSERT,UPDATE,DELETE')"),
                    {"r": role, "t": f"moodprint.{table}"},
                )
            assert await connection.scalar(
                text(
                    "select has_table_privilege('moodprint_runtime',:t,'SELECT,INSERT,UPDATE,DELETE')"
                ),
                {"t": f"moodprint.{table}"},
            )
        assert (
            await connection.scalar(
                text(
                    "select count(*) from pg_constraint where conrelid='moodprint.journal_storage_deletions'::regclass and contype='f'"
                )
            )
            == 0
        )
        # Role DDL is cluster-wide; roll back this rehearsal, including temporary roles.
        await connection.rollback()
    async with app.state.database.sessions() as db:
        assert (await db.scalars(select(Mood.note))).all() == ["untouched"]
