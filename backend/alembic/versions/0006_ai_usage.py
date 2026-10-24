"""Content-free AI usage, immutable price snapshot and worker fencing. Expand only."""

import sqlalchemy as sa

from alembic import op

revision = "0006_ai_usage"
down_revision = "0005_export_scope"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ai_usage",
        sa.Column("run_id", sa.UUID(), sa.ForeignKey("moodprint.ai_runs.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("moodprint.users.id"), nullable=False),
        sa.Column("worker_id", sa.UUID(), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("prompt_version", sa.String(60), nullable=False),
        sa.Column("pricing_version", sa.String(60), nullable=False),
        sa.Column("input_nano_rate", sa.BigInteger()),
        sa.Column("cached_nano_rate", sa.BigInteger()),
        sa.Column("output_nano_rate", sa.BigInteger()),
        sa.Column("estimated_nano_usd", sa.BigInteger()),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("requests_started", sa.Integer(), nullable=False),
        sa.Column("responses_received", sa.Integer(), nullable=False),
        sa.Column("input_tokens", sa.BigInteger(), nullable=False),
        sa.Column("cached_input_tokens", sa.BigInteger(), nullable=False),
        sa.Column("output_tokens", sa.BigInteger(), nullable=False),
        sa.Column("tool_calls", sa.Integer(), nullable=False),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("state in ('open','settled','uncertain')", name="state"),
        sa.CheckConstraint("sequence >= 0 and requests_started >= responses_received and responses_received >= 0 and requests_started <= 3 and tool_calls between 0 and 2", name="counts"),
        sa.CheckConstraint("input_tokens >= cached_input_tokens and cached_input_tokens >= 0 and output_tokens >= 0", name="tokens"),
        sa.CheckConstraint("estimated_nano_usd is null or estimated_nano_usd >= 0", name="cost"),
        schema="moodprint",
    )
    op.create_index("ix_ai_usage_user_id", "ai_usage", ["user_id"], schema="moodprint")
    op.create_index("ix_ai_usage_lease_until", "ai_usage", ["lease_until"], schema="moodprint")
    op.execute("ALTER TABLE moodprint.ai_usage ENABLE ROW LEVEL SECURITY")
    op.execute("REVOKE ALL ON moodprint.ai_usage FROM PUBLIC")
    # Match the existing server-trusted role boundary, with no changes to Auth or
    # to policies on existing tables. Disposable local DBs need not have these roles.
    op.execute("""DO $acl$
DECLARE role_name text;
BEGIN
  FOREACH role_name IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=role_name) THEN
      EXECUTE 'REVOKE ALL ON moodprint.ai_usage FROM ' || quote_ident(role_name);
    END IF;
  END LOOP;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='moodprint_runtime') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE ON moodprint.ai_usage TO moodprint_runtime;
    CREATE POLICY backend_access ON moodprint.ai_usage FOR ALL TO moodprint_runtime USING (true) WITH CHECK (true);
  END IF;
END $acl$""")


def downgrade():
    raise RuntimeError("Destructive rollback disabled; disable accounting and use a reviewed forward migration")
