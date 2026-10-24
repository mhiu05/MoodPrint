"""Durable pending proposals and user-only lifecycle decisions. Expand only."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0008_memory_proposals"
down_revision = "0007_chat_history"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "memory_proposals",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("moodprint.users.id"), nullable=False),
        sa.Column("bot_id", sa.String(16), nullable=False),
        sa.Column("text", sa.String(120), nullable=False),
        sa.Column("purpose", sa.String(16), nullable=False),
        sa.Column("data_version", sa.Integer(), nullable=False),
        sa.Column("ai_consent_version", sa.Integer(), nullable=False),
        sa.Column("mem_consent_version", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("source_id", sa.UUID(), sa.ForeignKey("moodprint.private_items.id")),
        sa.Column("source_version", sa.Integer()),
        sa.Column("decision_digest", sa.String(64)),
        sa.Column("receipt", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("status in ('pending','approved','rejected','expired')", name="state"),
        sa.CheckConstraint("purpose in ('memory','private_item')", name="purpose"),
        sa.CheckConstraint("bot_id in ('may','guong','nhip','rure')", name="bot"),
        sa.CheckConstraint("version >= 1 and data_version >= 1", name="versions"),
        sa.CheckConstraint("char_length(text) <= 120", name="text_length"),
        sa.CheckConstraint("(source_id is null) = (source_version is null)", name="source_pair"),
        schema="moodprint",
    )
    op.create_index(
        "ix_memory_proposals_owner_status",
        "memory_proposals",
        ["user_id", "status", "created_at"],
        schema="moodprint",
    )
    op.create_index(
        "ix_memory_proposals_source_id", "memory_proposals", ["source_id"], schema="moodprint"
    )
    op.create_index(
        "ix_memory_proposals_expires_at", "memory_proposals", ["expires_at"], schema="moodprint"
    )
    op.execute("ALTER TABLE moodprint.memory_proposals ENABLE ROW LEVEL SECURITY")
    op.execute("REVOKE ALL ON moodprint.memory_proposals FROM PUBLIC")
    op.execute("""DO $acl$
DECLARE role_name text;
BEGIN
  FOREACH role_name IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=role_name) THEN
      EXECUTE 'REVOKE ALL ON moodprint.memory_proposals FROM ' || quote_ident(role_name);
    END IF;
  END LOOP;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='moodprint_runtime') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE ON moodprint.memory_proposals TO moodprint_runtime;
    CREATE POLICY backend_access ON moodprint.memory_proposals FOR ALL TO moodprint_runtime USING (true) WITH CHECK (true);
  END IF;
END $acl$""")


def downgrade():
    raise RuntimeError("Destructive rollback disabled; use a reviewed forward migration")
