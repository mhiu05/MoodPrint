"""Guest trial foundation: immutable 7200s lifecycle, provisioning/cleanup/usage, detached budget.

Expand only. Every existing user stays ``registered`` with a sliding session. The trial deadline
is an immutable database fact (check constraint plus triggers), so no request, retry, refresh or
restart can renew it. Budget days and cost reservations deliberately hold no identity.
Never roll this back with live guests; keep the guest-aware application and cleanup deployed.
"""

import sqlalchemy as sa

from alembic import op

revision = "0016_guest_foundation"
down_revision = "0015_context_privacy"
branch_labels = None
depends_on = None

GUEST_TABLES = (
    "guest_provisioning_attempts",
    "guest_cleanup_jobs",
    "guest_usage",
    "guest_abuse_buckets",
    "guest_budget_days",
    "guest_cost_reservations",
    "guest_operation_links",
)
GUARD_FUNCTIONS = (
    "moodprint.guard_user_lifecycle()",
    "moodprint.guard_session_lifetime()",
)

USER_GUARD_SQL = """CREATE OR REPLACE FUNCTION moodprint.guard_user_lifecycle()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = ''
AS $$
BEGIN
  IF NEW.account_kind IS DISTINCT FROM OLD.account_kind
     OR NEW.guest_started_at IS DISTINCT FROM OLD.guest_started_at
     OR NEW.guest_expires_at IS DISTINCT FROM OLD.guest_expires_at THEN
    RAISE EXCEPTION 'guest lifecycle is immutable' USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END;
$$"""

USER_GUARD_TRIGGER_SQL = """CREATE TRIGGER users_lifecycle_immutable
BEFORE UPDATE OF account_kind, guest_started_at, guest_expires_at ON moodprint.users
FOR EACH ROW EXECUTE FUNCTION moodprint.guard_user_lifecycle()"""

SESSION_GUARD_SQL = """CREATE OR REPLACE FUNCTION moodprint.guard_session_lifetime()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = ''
AS $$
DECLARE
  owner_kind text;
  owner_deadline timestamptz;
BEGIN
  SELECT u.account_kind, u.guest_expires_at INTO owner_kind, owner_deadline
  FROM moodprint.users AS u WHERE u.id = NEW.user_id;
  IF owner_kind = 'guest' AND NEW.expires_at > owner_deadline THEN
    RAISE EXCEPTION 'guest session cannot outlive the trial' USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END;
$$"""

SESSION_GUARD_TRIGGER_SQL = """CREATE TRIGGER auth_sessions_lifetime_cap
BEFORE INSERT OR UPDATE OF expires_at, user_id ON moodprint.auth_sessions
FOR EACH ROW EXECUTE FUNCTION moodprint.guard_session_lifetime()"""


def protection_statements(table: str) -> list[str]:
    """RLS on, no PUBLIC or Supabase API role access; only the backend runtime role."""
    return [
        f"ALTER TABLE moodprint.{table} ENABLE ROW LEVEL SECURITY",
        f"REVOKE ALL ON moodprint.{table} FROM PUBLIC",
        f"""DO $acl$
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
END $acl$""",
    ]


def function_protection_statements(function: str) -> list[str]:
    return [
        f"REVOKE ALL ON FUNCTION {function} FROM PUBLIC",
        f"""DO $acl$
DECLARE r text;
BEGIN
 FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=r) THEN
   EXECUTE 'REVOKE ALL ON FUNCTION {function} FROM ' || quote_ident(r);
  END IF;
 END LOOP;
END $acl$""",
    ]


def timestamp(name: str, *, nullable: bool = False, default: str | None = None) -> sa.Column:
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        nullable=nullable,
        server_default=sa.text(default) if default else None,
    )


def upgrade():
    # users: server-owned lifecycle. Existing rows take the registered default (metadata-only).
    op.add_column(
        "users",
        sa.Column("account_kind", sa.String(10), nullable=False, server_default="registered"),
        schema="moodprint",
    )
    op.add_column(
        "users", sa.Column("guest_started_at", sa.DateTime(timezone=True)), schema="moodprint"
    )
    op.add_column(
        "users", sa.Column("guest_expires_at", sa.DateTime(timezone=True)), schema="moodprint"
    )
    op.create_check_constraint(
        op.f("ck_users_account_kind"),
        "users",
        "account_kind in ('registered','guest')",
        schema="moodprint",
    )
    op.create_check_constraint(
        op.f("ck_users_guest_lifetime"),
        "users",
        "(account_kind = 'registered' AND guest_started_at IS NULL AND guest_expires_at IS NULL)"
        " OR (account_kind = 'guest' AND guest_started_at IS NOT NULL"
        " AND guest_expires_at IS NOT NULL"
        " AND guest_expires_at = guest_started_at + interval '7200 seconds')",
        schema="moodprint",
    )
    op.create_index(
        "ix_users_guest_expires_at",
        "users",
        ["guest_expires_at"],
        schema="moodprint",
        postgresql_where=sa.text("account_kind = 'guest'"),
    )
    # A constant-time default for existing rows, then the fresh clock for every new session.
    op.add_column(
        "auth_sessions",
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        schema="moodprint",
    )
    op.execute(
        "ALTER TABLE moodprint.auth_sessions ALTER COLUMN created_at SET DEFAULT clock_timestamp()"
    )
    for statement in (
        USER_GUARD_SQL,
        USER_GUARD_TRIGGER_SQL,
        SESSION_GUARD_SQL,
        SESSION_GUARD_TRIGGER_SQL,
    ):
        op.execute(statement)
    for function in GUARD_FUNCTIONS:
        for statement in function_protection_statements(function):
            op.execute(statement)

    op.create_table(
        "guest_provisioning_attempts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("intent_hash", sa.CHAR(64), nullable=False),
        sa.Column("idempotency_hash", sa.CHAR(64)),
        sa.Column("payload_digest", sa.CHAR(64)),
        sa.Column("provider_correlation", sa.CHAR(64), nullable=False),
        sa.Column("provider_subject", sa.UUID()),
        sa.Column("provider_session_id", sa.UUID()),
        sa.Column("user_id", sa.UUID()),
        sa.Column("state", sa.String(24), nullable=False, server_default="intent"),
        timestamp("created_at", default="clock_timestamp()"),
        timestamp("intent_expires_at", default="clock_timestamp() + interval '600 seconds'"),
        timestamp("signup_started_at", nullable=True),
        timestamp("reconcile_until", default="clock_timestamp() + interval '600 seconds'"),
        sa.Column("lease_token", sa.UUID()),
        timestamp("lease_until", nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        timestamp("next_attempt_at", default="clock_timestamp()"),
        sa.Column("last_error", sa.String(40)),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_guest_provisioning_attempts")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["moodprint.users.id"],
            name=op.f("fk_guest_provisioning_attempts_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("intent_hash", name=op.f("uq_guest_provisioning_attempts_intent_hash")),
        sa.UniqueConstraint(
            "provider_correlation",
            name=op.f("uq_guest_provisioning_attempts_provider_correlation"),
        ),
        sa.UniqueConstraint("user_id", name=op.f("uq_guest_provisioning_attempts_user_id")),
        sa.CheckConstraint(
            "state in ('intent','signup_started','granted','ambiguous','orphan_pending',"
            "'resolved','rejected','incident_required')",
            name=op.f("ck_guest_provisioning_attempts_state"),
        ),
        sa.CheckConstraint(
            "(lease_token IS NULL) = (lease_until IS NULL)",
            name=op.f("ck_guest_provisioning_attempts_lease_pair"),
        ),
        sa.CheckConstraint("attempts >= 0", name=op.f("ck_guest_provisioning_attempts_attempts")),
        sa.CheckConstraint(
            "signup_started_at IS NULL OR reconcile_until >= signup_started_at + interval '24 hours'",
            name=op.f("ck_guest_provisioning_attempts_reconcile_window"),
        ),
        schema="moodprint",
    )
    op.create_index(
        "ix_guest_provisioning_attempts_state_next",
        "guest_provisioning_attempts",
        ["state", "next_attempt_at"],
        schema="moodprint",
    )

    op.create_table(
        "guest_cleanup_jobs",
        sa.Column("user_id", sa.UUID(), nullable=False),
        timestamp("due_at"),
        sa.Column("state", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        timestamp("next_attempt_at", default="clock_timestamp()"),
        sa.Column("lease_token", sa.UUID()),
        timestamp("lease_until", nullable=True),
        sa.Column("last_error", sa.String(40)),
        timestamp("alerted_at", nullable=True),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_guest_cleanup_jobs")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["moodprint.users.id"],
            name=op.f("fk_guest_cleanup_jobs_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "state in ('pending','running','retry','incident_required')",
            name=op.f("ck_guest_cleanup_jobs_state"),
        ),
        sa.CheckConstraint(
            "(lease_token IS NULL) = (lease_until IS NULL)",
            name=op.f("ck_guest_cleanup_jobs_lease_pair"),
        ),
        sa.CheckConstraint("attempts >= 0", name=op.f("ck_guest_cleanup_jobs_attempts")),
        schema="moodprint",
    )
    op.create_index(
        "ix_guest_cleanup_jobs_state_next",
        "guest_cleanup_jobs",
        ["state", "next_attempt_at"],
        schema="moodprint",
    )

    op.create_table(
        "guest_usage",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("ai_turns", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("voice_clips", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("voice_milliseconds", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("semantic_memories", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_guest_usage")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["moodprint.users.id"],
            name=op.f("fk_guest_usage_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("ai_turns >= 0", name=op.f("ck_guest_usage_ai_turns")),
        sa.CheckConstraint("voice_clips >= 0", name=op.f("ck_guest_usage_voice_clips")),
        sa.CheckConstraint(
            "voice_milliseconds >= 0", name=op.f("ck_guest_usage_voice_milliseconds")
        ),
        sa.CheckConstraint(
            "semantic_memories >= 0", name=op.f("ck_guest_usage_semantic_memories")
        ),
        schema="moodprint",
    )

    op.create_table(
        "guest_abuse_buckets",
        sa.Column("scope", sa.String(24), nullable=False),
        sa.Column("key_hash", sa.CHAR(64), nullable=False),
        timestamp("window_start"),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reserved", sa.Integer(), nullable=False, server_default="0"),
        timestamp("expires_at"),
        sa.PrimaryKeyConstraint(
            "scope", "key_hash", "window_start", name=op.f("pk_guest_abuse_buckets")
        ),
        sa.CheckConstraint(
            "scope in ('intent','intent_global','creation_hour','creation_day','failed_signup',"
            "'feedback','ai_minute','voice_minute')",
            name=op.f("ck_guest_abuse_buckets_scope"),
        ),
        sa.CheckConstraint("count >= 0", name=op.f("ck_guest_abuse_buckets_count")),
        sa.CheckConstraint("reserved >= 0", name=op.f("ck_guest_abuse_buckets_reserved")),
        schema="moodprint",
    )
    op.create_index(
        "ix_guest_abuse_buckets_expires_at",
        "guest_abuse_buckets",
        ["expires_at"],
        schema="moodprint",
    )

    op.create_table(
        "guest_budget_days",
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("limit_nano_usd", sa.BigInteger(), nullable=False),
        sa.Column("spent_nano_usd", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("reserved_nano_usd", sa.BigInteger(), nullable=False, server_default="0"),
        timestamp("halted_at", nullable=True),
        sa.PrimaryKeyConstraint("day", name=op.f("pk_guest_budget_days")),
        sa.CheckConstraint("limit_nano_usd > 0", name=op.f("ck_guest_budget_days_limit")),
        sa.CheckConstraint("spent_nano_usd >= 0", name=op.f("ck_guest_budget_days_spent")),
        sa.CheckConstraint("reserved_nano_usd >= 0", name=op.f("ck_guest_budget_days_reserved")),
        schema="moodprint",
    )

    op.create_table(
        "guest_cost_reservations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("kind", sa.String(8), nullable=False),
        sa.Column("upper_nano_usd", sa.BigInteger(), nullable=False),
        sa.Column("charged_nano_usd", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("state", sa.String(16), nullable=False, server_default="reserved"),
        timestamp("created_at", default="clock_timestamp()"),
        timestamp("lease_until", default="clock_timestamp() + interval '60 seconds'"),
        timestamp("dispatched_at", nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_guest_cost_reservations")),
        sa.ForeignKeyConstraint(
            ["day"],
            ["moodprint.guest_budget_days.day"],
            name=op.f("fk_guest_cost_reservations_day_guest_budget_days"),
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "kind in ('ai','voice','embed')", name=op.f("ck_guest_cost_reservations_kind")
        ),
        sa.CheckConstraint(
            "state in ('reserved','dispatched','settled','uncertain','cancelled')",
            name=op.f("ck_guest_cost_reservations_state"),
        ),
        sa.CheckConstraint("upper_nano_usd >= 0", name=op.f("ck_guest_cost_reservations_upper")),
        sa.CheckConstraint(
            "charged_nano_usd >= 0", name=op.f("ck_guest_cost_reservations_charged")
        ),
        schema="moodprint",
    )
    op.create_index(
        "ix_guest_cost_reservations_state_lease",
        "guest_cost_reservations",
        ["state", "lease_until"],
        schema="moodprint",
    )

    op.create_table(
        "guest_operation_links",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(8), nullable=False),
        sa.Column("operation_key_hash", sa.CHAR(64), nullable=False),
        sa.Column("payload_digest", sa.CHAR(64), nullable=False),
        sa.Column("reservation_id", sa.UUID()),
        sa.Column("state", sa.String(16), nullable=False, server_default="claimed"),
        sa.Column("worker_id", sa.UUID(), nullable=False),
        sa.Column("lease_token", sa.UUID(), nullable=False),
        timestamp("lease_until"),
        timestamp("created_at", default="clock_timestamp()"),
        sa.PrimaryKeyConstraint(
            "user_id", "kind", "operation_key_hash", name=op.f("pk_guest_operation_links")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["moodprint.users.id"],
            name=op.f("fk_guest_operation_links_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["reservation_id"],
            ["moodprint.guest_cost_reservations.id"],
            name=op.f("fk_guest_operation_links_reservation_id_guest_cost_reservations"),
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "reservation_id", name=op.f("uq_guest_operation_links_reservation_id")
        ),
        sa.CheckConstraint(
            "kind in ('ai','voice','embed')", name=op.f("ck_guest_operation_links_kind")
        ),
        sa.CheckConstraint(
            "state in ('claimed','dispatched','completed','interrupted')",
            name=op.f("ck_guest_operation_links_state"),
        ),
        sa.CheckConstraint(
            "state <> 'dispatched' OR reservation_id IS NOT NULL",
            name=op.f("ck_guest_operation_links_dispatched"),
        ),
        schema="moodprint",
    )
    op.create_index(
        "ix_guest_operation_links_kind_state_lease",
        "guest_operation_links",
        ["kind", "state", "lease_until"],
        schema="moodprint",
    )

    for table in GUEST_TABLES:
        for statement in protection_statements(table):
            op.execute(statement)


def downgrade():
    raise RuntimeError(
        "Destructive rollback disabled; guest lifecycle columns, cleanup jobs and deadlines "
        "must stay until no guest or provisioning attempt remains"
    )
