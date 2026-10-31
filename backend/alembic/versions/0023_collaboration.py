"""Bounded companion collaboration: child runs, per-edge sharing opt-in, content-free receipts.

Expand only (M-P2-A, phase-2/05 §1): one nullable column and two CHECKs on ai_runs, two new
private tables. Existing rows are unchanged (every legacy run has origin 'user'/'proactive' and
a NULL parent, which satisfies the new CHECKs). RLS is enabled with the single backend_access
policy for moodprint_runtime (as 0007/0019/0022); client roles get nothing. Forward-only.
"""

import sqlalchemy as sa

from alembic import op

revision = "0023_collaboration"
down_revision = "0022_proactive_messages"
branch_labels = None
depends_on = None

SCHEMA = "moodprint"
TABLES = ("ai_sharing_permissions", "ai_collaborations")
EDGE_IN = "edge in ('nhip_energy_for_rure', 'nhip_habit_for_may', 'rure_activity_for_guong')"


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


def upgrade():
    op.add_column("ai_runs", sa.Column("parent_run_id", sa.UUID(), nullable=True), schema=SCHEMA)
    op.create_foreign_key(
        op.f("fk_ai_runs_parent_run_id_ai_runs"), "ai_runs", "ai_runs", ["parent_run_id"], ["id"],
        source_schema=SCHEMA, referent_schema=SCHEMA, ondelete="CASCADE",
    )
    op.drop_constraint(op.f("ck_ai_runs_origin"), "ai_runs", type_="check", schema=SCHEMA)
    op.create_check_constraint(
        op.f("ck_ai_runs_origin"), "ai_runs", "origin in ('user', 'proactive', 'collaboration')", schema=SCHEMA
    )
    op.create_check_constraint(
        op.f("ck_ai_runs_parent"), "ai_runs", "(origin = 'collaboration') = (parent_run_id is not null)",
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_ai_runs_parent_run_id"), "ai_runs", ["parent_run_id"], schema=SCHEMA,
        postgresql_where=sa.text("parent_run_id IS NOT NULL"),
    )

    op.create_table(
        "ai_sharing_permissions",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("edge", sa.String(48), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("policy_version", sa.String(32), nullable=False, server_default=sa.text("'sharing-v1'")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("clock_timestamp()")),
        sa.CheckConstraint(EDGE_IN, name=op.f("ck_ai_sharing_permissions_edge")),
        sa.CheckConstraint("version >= 1", name=op.f("ck_ai_sharing_permissions_version")),
        sa.CheckConstraint("policy_version in ('sharing-v1')", name=op.f("ck_ai_sharing_permissions_policy")),
        sa.ForeignKeyConstraint(["user_id"], ["moodprint.users.id"], ondelete="CASCADE",
                                name=op.f("fk_ai_sharing_permissions_user_id_users")),
        sa.PrimaryKeyConstraint("user_id", "edge", name=op.f("pk_ai_sharing_permissions")),
        schema=SCHEMA,
    )

    op.create_table(
        "ai_collaborations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("primary_run_id", sa.UUID(), nullable=False),
        sa.Column("specialist_run_id", sa.UUID(), nullable=True),
        sa.Column("edge", sa.String(48), nullable=False),
        sa.Column("rule_id", sa.String(8), nullable=False),
        sa.Column("requester_bot", sa.String(16), nullable=False),
        sa.Column("specialist_bot", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("deny_reason", sa.String(32), nullable=True),
        sa.Column("failure_code", sa.String(32), nullable=True),
        sa.Column("permission_version", sa.Integer(), nullable=False),
        sa.Column("data_version", sa.Integer(), nullable=False),
        sa.Column("input_schema", sa.String(32), nullable=False),
        sa.Column("input_digest", sa.String(64), nullable=False),
        sa.Column("output_digest", sa.String(64), nullable=True),
        sa.Column("used_in_reply", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("clock_timestamp()")),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status in ('authorized', 'denied', 'completed', 'failed', 'timeout', 'cancelled', 'discarded')",
            name=op.f("ck_ai_collaborations_status"),
        ),
        sa.CheckConstraint(
            "(edge = 'nhip_energy_for_rure' and requester_bot = 'rure' and specialist_bot = 'nhip') "
            "or (edge = 'nhip_habit_for_may' and requester_bot = 'may' and specialist_bot = 'nhip') "
            "or (edge = 'rure_activity_for_guong' and requester_bot = 'guong' and specialist_bot = 'rure')",
            name=op.f("ck_ai_collaborations_edge"),
        ),
        sa.CheckConstraint("rule_id in ('R1', 'R2', 'R3', 'R4')", name=op.f("ck_ai_collaborations_rule")),
        sa.CheckConstraint("(status = 'denied') = (deny_reason is not null)",
                           name=op.f("ck_ai_collaborations_deny")),
        # Only operational reasons are recorded. A distress match or a never-enabled edge is never
        # written anywhere (phase-1/07 §8), and the database refuses such a row.
        sa.CheckConstraint(
            "deny_reason is null or deny_reason in ('journal_consent_off', 'no_data', 'daily_cap', 'budget', 'time_budget', 'capacity')",
            name=op.f("ck_ai_collaborations_deny_reason"),
        ),
        sa.CheckConstraint(
            "failure_code is null or status in ('failed', 'timeout', 'cancelled', 'discarded')",
            name=op.f("ck_ai_collaborations_failure"),
        ),
        sa.CheckConstraint("not used_in_reply or status = 'completed'", name=op.f("ck_ai_collaborations_used")),
        sa.CheckConstraint(
            "input_digest ~ '^[0-9a-f]{64}$' and (output_digest is null or output_digest ~ '^[0-9a-f]{64}$')",
            name=op.f("ck_ai_collaborations_digest"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["moodprint.users.id"], ondelete="CASCADE",
                                name=op.f("fk_ai_collaborations_user_id_users")),
        sa.ForeignKeyConstraint(["primary_run_id"], ["moodprint.ai_runs.id"], ondelete="CASCADE",
                                name=op.f("fk_ai_collaborations_primary_run_id_ai_runs")),
        sa.ForeignKeyConstraint(["specialist_run_id"], ["moodprint.ai_runs.id"], ondelete="SET NULL",
                                name=op.f("fk_ai_collaborations_specialist_run_id_ai_runs")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_collaborations")),
        sa.UniqueConstraint("primary_run_id", "specialist_bot", "edge",
                            name=op.f("uq_ai_collaborations_primary_run_id")),
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_ai_collaborations_user_started"), "ai_collaborations", ["user_id", "started_at"],
        schema=SCHEMA,
    )

    for table in TABLES:
        protect(table)


def downgrade():
    raise RuntimeError("Destructive rollback disabled; use a reviewed forward migration")
