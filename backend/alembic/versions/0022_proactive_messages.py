"""Proactive check-in schedules, durable jobs, read markers and content-free provenance.

Expand only: five new private tables, no change to existing rows. RLS is enabled with the
single backend_access policy for moodprint_runtime (as 0007/0019); client roles get nothing.
Ownership is enforced by the backend owner predicate. Forward-only.
"""

import sqlalchemy as sa

from alembic import op

revision = "0022_proactive_messages"
down_revision = "0021_multi_message"
branch_labels = None
depends_on = None

SCHEMA = "moodprint"
TABLES = (
    "ai_proactive_settings",
    "ai_proactive_schedules",
    "ai_proactive_jobs",
    "ai_conversation_reads",
    "ai_message_sources",
)
BOT_CHECK = "bot_id in ('may','guong','nhip','rure','caunoi')"
SLOT_CHECK = "slot in ('morning','evening')"


def protect(table):
    op.execute(f"ALTER TABLE moodprint.{table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"REVOKE ALL ON moodprint.{table} FROM PUBLIC")
    op.execute(f"""DO $acl$
DECLARE r text;
BEGIN
 FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=r) THEN
   EXECUTE 'REVOKE ALL ON moodprint.{table} FROM ' || quote_ident(r);
  END IF;
 END LOOP;
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='moodprint_runtime') THEN
  GRANT SELECT,INSERT,UPDATE,DELETE ON moodprint.{table} TO moodprint_runtime;
  CREATE POLICY backend_access ON moodprint.{table} FOR ALL TO moodprint_runtime USING (true) WITH CHECK (true);
 END IF;
END $acl$""")


def _timestamps():
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
    )


def upgrade():
    op.create_table(
        "ai_proactive_settings",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("quiet_start", sa.Time(), nullable=False, server_default=sa.text("'22:00'")),
        sa.Column("quiet_end", sa.Time(), nullable=False, server_default=sa.text("'07:00'")),
        sa.Column("badges_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("journal_context_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("journal_context_version", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("policy_version", sa.String(32), nullable=False, server_default=sa.text("'proactive-v1'")),
        *_timestamps(),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.CheckConstraint("version >= 1 and journal_context_version >= 0", name=op.f("ck_ai_proactive_settings_version")),
        sa.CheckConstraint("policy_version in ('proactive-v1')", name=op.f("ck_ai_proactive_settings_policy")),
        sa.ForeignKeyConstraint(["user_id"], ["moodprint.users.id"], ondelete="CASCADE",
                                name=op.f("fk_ai_proactive_settings_user_id_users")),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_ai_proactive_settings")),
        schema=SCHEMA,
    )

    op.create_table(
        "ai_proactive_schedules",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("bot_id", sa.String(16), nullable=False),
        sa.Column("slot", sa.String(16), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("local_time", sa.Time(), nullable=False),
        sa.Column("weekdays", sa.SmallInteger(), nullable=False, server_default=sa.text("127")),
        sa.Column("paused_until", sa.Date(), nullable=True),
        sa.Column("auto_paused_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        *_timestamps(),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.CheckConstraint(BOT_CHECK, name=op.f("ck_ai_proactive_schedules_bot")),
        sa.CheckConstraint(SLOT_CHECK, name=op.f("ck_ai_proactive_schedules_slot")),
        sa.CheckConstraint(
            "(slot = 'morning' and local_time between '05:00' and '11:30') "
            "or (slot = 'evening' and local_time between '17:00' and '22:30')",
            name=op.f("ck_ai_proactive_schedules_window"),
        ),
        sa.CheckConstraint(
            "mod(extract(minute from local_time)::int, 15) = 0 and extract(second from local_time) = 0",
            name=op.f("ck_ai_proactive_schedules_step"),
        ),
        sa.CheckConstraint("weekdays between 1 and 127", name=op.f("ck_ai_proactive_schedules_weekdays")),
        sa.CheckConstraint("version >= 1", name=op.f("ck_ai_proactive_schedules_version")),
        sa.ForeignKeyConstraint(["user_id"], ["moodprint.users.id"], ondelete="CASCADE",
                                name=op.f("fk_ai_proactive_schedules_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_proactive_schedules")),
        sa.UniqueConstraint("user_id", "bot_id", "slot", name=op.f("uq_ai_proactive_schedules_user_id")),
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_ai_proactive_schedules_due"), "ai_proactive_schedules", ["next_due_at"],
        schema=SCHEMA, postgresql_where=sa.text("enabled and next_due_at is not null"),
    )

    op.create_table(
        "ai_proactive_jobs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("schedule_id", sa.UUID(), nullable=True),
        sa.Column("bot_id", sa.String(16), nullable=False),
        sa.Column("slot", sa.String(16), nullable=False),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("skip_reason", sa.String(32), nullable=True),
        sa.Column("attempts", sa.SmallInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_token", sa.UUID(), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("worker_id", sa.UUID(), nullable=True),
        sa.Column("schedule_version", sa.Integer(), nullable=False),
        sa.Column("settings_version", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=True),
        sa.Column("conversation_id", sa.UUID(), nullable=True),
        sa.Column("challenge_kind", sa.String(24), nullable=True),
        sa.Column("last_error", sa.String(48), nullable=True),
        *_timestamps(),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status in ('pending', 'running', 'retry', 'delivered', 'skipped', 'cancelled', 'failed')",
            name=op.f("ck_ai_proactive_jobs_status"),
        ),
        sa.CheckConstraint("attempts between 0 and 5", name=op.f("ck_ai_proactive_jobs_attempts")),
        sa.CheckConstraint("expires_at > due_at", name=op.f("ck_ai_proactive_jobs_window")),
        sa.CheckConstraint("(status = 'skipped') = (skip_reason is not null)", name=op.f("ck_ai_proactive_jobs_skip")),
        sa.CheckConstraint("status <> 'delivered' or run_id is not null", name=op.f("ck_ai_proactive_jobs_delivery")),
        sa.CheckConstraint(
            "status <> 'running' or (lease_token is not null and lease_until is not null)",
            name=op.f("ck_ai_proactive_jobs_lease"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["moodprint.users.id"], ondelete="CASCADE",
                                name=op.f("fk_ai_proactive_jobs_user_id_users")),
        sa.ForeignKeyConstraint(["schedule_id"], ["moodprint.ai_proactive_schedules.id"], ondelete="SET NULL",
                                name=op.f("fk_ai_proactive_jobs_schedule_id_ai_proactive_schedules")),
        sa.ForeignKeyConstraint(["run_id"], ["moodprint.ai_runs.id"], ondelete="SET NULL",
                                name=op.f("fk_ai_proactive_jobs_run_id_ai_runs")),
        sa.ForeignKeyConstraint(["conversation_id"], ["moodprint.ai_conversations.id"], ondelete="SET NULL",
                                name=op.f("fk_ai_proactive_jobs_conversation_id_ai_conversations")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_proactive_jobs")),
        sa.UniqueConstraint("user_id", "bot_id", "slot", "local_date", name=op.f("uq_ai_proactive_jobs_user_id")),
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_ai_proactive_jobs_due"), "ai_proactive_jobs", ["status", "available_at"],
        schema=SCHEMA, postgresql_where=sa.text("status in ('pending','retry','running')"),
    )
    op.create_index(op.f("ix_ai_proactive_jobs_owner"), "ai_proactive_jobs", ["user_id", "local_date"], schema=SCHEMA)
    op.create_index(op.f("ix_ai_proactive_jobs_run_id"), "ai_proactive_jobs", ["run_id"], schema=SCHEMA)

    op.create_table(
        "ai_conversation_reads",
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("last_read_sequence", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.CheckConstraint("last_read_sequence >= 0", name=op.f("ck_ai_conversation_reads_sequence")),
        sa.ForeignKeyConstraint(["conversation_id"], ["moodprint.ai_conversations.id"], ondelete="CASCADE",
                                name=op.f("fk_ai_conversation_reads_conversation_id_ai_conversations")),
        sa.ForeignKeyConstraint(["user_id"], ["moodprint.users.id"], ondelete="CASCADE",
                                name=op.f("fk_ai_conversation_reads_user_id_users")),
        sa.PrimaryKeyConstraint("conversation_id", name=op.f("pk_ai_conversation_reads")),
        schema=SCHEMA,
    )
    op.create_index(op.f("ix_ai_conversation_reads_user_id"), "ai_conversation_reads", ["user_id"], schema=SCHEMA)

    op.create_table(
        "ai_message_sources",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("source_kind", sa.String(24), nullable=False),
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column("source_revision", sa.Integer(), nullable=False),
        sa.Column("source_local_date", sa.Date(), nullable=True),
        sa.Column("policy", sa.String(32), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("source_kind in ('journal_entry')", name=op.f("ck_ai_message_sources_kind")),
        sa.CheckConstraint("source_revision >= 1", name=op.f("ck_ai_message_sources_revision")),
        sa.ForeignKeyConstraint(["run_id"], ["moodprint.ai_runs.id"], ondelete="CASCADE",
                                name=op.f("fk_ai_message_sources_run_id_ai_runs")),
        sa.ForeignKeyConstraint(["user_id"], ["moodprint.users.id"], ondelete="CASCADE",
                                name=op.f("fk_ai_message_sources_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_message_sources")),
        sa.UniqueConstraint("run_id", "source_kind", "source_id", name=op.f("uq_ai_message_sources_run_id")),
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_ai_message_sources_user_id"), "ai_message_sources", ["user_id", "source_id"], schema=SCHEMA
    )

    for table in TABLES:
        protect(table)


def downgrade():
    raise RuntimeError("Destructive rollback disabled; use a reviewed forward migration")
