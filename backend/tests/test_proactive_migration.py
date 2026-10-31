"""M-P1-B (0022): five private proactive tables with RLS, no client-role access (P1-02)."""

import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text

from app.infrastructure.database.models import Base

MIGRATION_PATH = Path(__file__).resolve().parents[1] / "alembic/versions/0022_proactive_messages.py"
TABLES = (
    "ai_proactive_settings",
    "ai_proactive_schedules",
    "ai_proactive_jobs",
    "ai_conversation_reads",
    "ai_message_sources",
)
EXPECTED_CONSTRAINTS = {
    "uq_ai_proactive_schedules_user_id",
    "ck_ai_proactive_schedules_bot",
    "ck_ai_proactive_schedules_slot",
    "ck_ai_proactive_schedules_window",
    "ck_ai_proactive_schedules_step",
    "ck_ai_proactive_schedules_weekdays",
    "ck_ai_proactive_schedules_version",
    "ck_ai_proactive_settings_version",
    "ck_ai_proactive_settings_policy",
    "uq_ai_proactive_jobs_user_id",
    "ck_ai_proactive_jobs_status",
    "ck_ai_proactive_jobs_attempts",
    "ck_ai_proactive_jobs_window",
    "ck_ai_proactive_jobs_skip",
    "ck_ai_proactive_jobs_delivery",
    "ck_ai_proactive_jobs_lease",
    "ck_ai_conversation_reads_sequence",
    "uq_ai_message_sources_run_id",
    "ck_ai_message_sources_kind",
    "ck_ai_message_sources_revision",
}


@pytest.mark.postgres
async def test_0022_creates_private_tables_with_constraints_and_rls(database):
    spec = importlib.util.spec_from_file_location("proactive_migration", MIGRATION_PATH)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.down_revision == "0021_multi_message"

    def migrate(connection):
        context = MigrationContext.configure(connection, opts={"target_metadata": Base.metadata})
        with Operations.context(context):
            migration.upgrade()

    async with database.begin() as connection:
        for table in reversed(TABLES):
            await connection.execute(text(f"drop table moodprint.{table}"))
        await connection.run_sync(migrate)
        names = set(
            (
                await connection.execute(
                    text(
                        "select conname from pg_constraint c join pg_class t on t.oid = c.conrelid "
                        "join pg_namespace n on n.oid = t.relnamespace "
                        "where n.nspname = 'moodprint' and t.relname = any(:tables)"
                    ),
                    {"tables": list(TABLES)},
                )
            ).scalars()
        )
        assert EXPECTED_CONSTRAINTS <= names, sorted(EXPECTED_CONSTRAINTS - names)
        for table in TABLES:
            secured = await connection.scalar(
                text(
                    "select relrowsecurity from pg_class where oid = cast(:t as regclass)"
                ),
                {"t": f"moodprint.{table}"},
            )
            assert secured, table
            public = await connection.scalar(
                text("select has_table_privilege('public', cast(:t as regclass), 'SELECT')"),
                {"t": f"moodprint.{table}"},
            )
            assert public is False, table
        due = await connection.scalar(
            text("select indexdef from pg_indexes where indexname = 'ix_ai_proactive_jobs_due'")
        )
        assert "WHERE" in due and "pending" in due
        # Offline review SQL is literal: '%' must never appear doubled.
        source = MIGRATION_PATH.read_text(encoding="utf-8")
        assert "format(" not in source and "%%" not in source
