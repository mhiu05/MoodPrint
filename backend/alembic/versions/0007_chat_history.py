"""Opt-in transcripts and cross-worker turn coordination. Additive migration."""

import sqlalchemy as sa

from alembic import op

revision = "0007_chat_history"
down_revision = "0006_ai_usage"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("ai_preferences",
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("moodprint.users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("history_enabled", sa.Boolean(), nullable=False),
        sa.Column("semantic_memory_enabled", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("policy_version", sa.String(32), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), schema="moodprint")
    op.create_table("ai_conversations",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("moodprint.users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("bot_id", sa.String(16), nullable=False),
        sa.Column("title", sa.String(100), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("bot_id in ('may','guong','nhip','rure','caunoi')", name="bot"),
        sa.CheckConstraint("version >= 1", name="version"), schema="moodprint")
    op.create_index("ix_ai_conversations_owner_activity", "ai_conversations", ["user_id", "updated_at", "id"], schema="moodprint")
    op.create_index("ix_ai_conversations_expiry", "ai_conversations", ["expires_at"], schema="moodprint")
    op.create_table("ai_messages",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("conversation_id", sa.UUID(), sa.ForeignKey("moodprint.ai_conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("actor", sa.String(8), nullable=False),
        sa.Column("text", sa.String(6000), nullable=False),
        sa.Column("cards", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("run_id", sa.UUID(), sa.ForeignKey("moodprint.ai_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("conversation_id", "sequence"),
        sa.UniqueConstraint("run_id", "actor"),
        sa.CheckConstraint("actor in ('self','bot')", name="actor"),
        sa.CheckConstraint("sequence >= 1", name="sequence"), schema="moodprint")
    op.create_index("ix_ai_messages_run_id", "ai_messages", ["run_id"], schema="moodprint")
    op.create_table("ai_turns",
        sa.Column("run_id", sa.UUID(), sa.ForeignKey("moodprint.ai_runs.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("moodprint.users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scope_id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), sa.ForeignKey("moodprint.ai_conversations.id", ondelete="CASCADE")),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("client_message_id", sa.UUID(), nullable=False),
        sa.Column("input_digest", sa.String(64), nullable=False),
        sa.Column("data_version", sa.Integer(), nullable=False),
        sa.Column("worker_id", sa.UUID(), nullable=False),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("scope_id", "client_message_id"), schema="moodprint")
    for col in ("user_id", "conversation_id", "lease_until"):
        op.create_index(f"ix_ai_turns_{col}", "ai_turns", [col], schema="moodprint")
    for table in ("ai_preferences", "ai_conversations", "ai_messages", "ai_turns"):
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


def downgrade():
    raise RuntimeError("Use a reviewed forward migration; transcript removal is destructive")
