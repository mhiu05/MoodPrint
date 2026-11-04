"""Expand-only journal settings, revision-fenced jobs/vectors, and automatic memory provenance."""

import sqlalchemy as sa

from alembic import op

revision = "0029_journal_intelligence"
down_revision = "0028_collaboration_defaults"
branch_labels = None
depends_on = None
SCHEMA = "moodprint"
TABLES = ("journal_ai_settings", "journal_entry_embeddings", "journal_ai_jobs")


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
    op.create_table(
        "journal_ai_settings",
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("moodprint.users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("embedding_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("auto_memory_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notice_version", sa.String(32), nullable=False, server_default="journal-ai-v1"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.CheckConstraint("version >= 1", name="version"), schema=SCHEMA,
    )
    # Use the established PostgreSQL vector type without adding a dependency.
    from app.ai.embedding_models import Vector

    op.create_table(
        "journal_entry_embeddings",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("entry_id", sa.UUID(), sa.ForeignKey("moodprint.journal_entries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("moodprint.users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entry_version", sa.Integer(), nullable=False),
        sa.Column("settings_version", sa.Integer(), nullable=False),
        sa.Column("content_sha256", sa.CHAR(64), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("embedding", Vector(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.UniqueConstraint("entry_id", "model", "dimensions", name="uq_journal_entry_embeddings_config"),
        sa.CheckConstraint("dimensions in (256,512,1024,2048) and extensions.vector_dims(embedding) = dimensions", name="dimensions"),
        schema=SCHEMA,
    )
    op.create_index("ix_journal_entry_embeddings_scope", "journal_entry_embeddings", ["user_id", "model", "dimensions"], schema=SCHEMA)
    op.create_table(
        "journal_ai_jobs",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("entry_id", sa.UUID(), sa.ForeignKey("moodprint.journal_entries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("moodprint.users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("entry_version", sa.Integer(), nullable=False),
        sa.Column("settings_version", sa.Integer(), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("dimensions", sa.Integer()),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("lease_token", sa.UUID()),
        sa.Column("last_error", sa.String(48)),
        sa.Column("run_id", sa.UUID(), sa.ForeignKey("moodprint.ai_runs.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.UniqueConstraint("entry_id", "kind", "entry_version", "settings_version", "model", name="uq_journal_ai_jobs_snapshot"),
        sa.CheckConstraint("kind in ('embed','memories')", name="kind"),
        sa.CheckConstraint("(dimensions is null) = (kind = 'memories')", name="dimensions"),
        sa.CheckConstraint("status in ('pending','running','retry','succeeded','cancelled','failed','skipped')", name="status"),
        sa.CheckConstraint("attempts between 0 and 8", name="attempts"), schema=SCHEMA,
    )
    op.create_index("ix_journal_ai_jobs_due", "journal_ai_jobs", ["status", "available_at", "lease_until"], schema=SCHEMA)
    op.create_index("ix_journal_ai_jobs_owner", "journal_ai_jobs", ["user_id", "kind", "created_at"], schema=SCHEMA)
    for table in TABLES:
        protect(table)
    op.add_column("memories", sa.Column("origin", sa.String(16), nullable=False, server_default="approved"), schema=SCHEMA)
    op.add_column("memories", sa.Column("source_entry_id", sa.UUID(), sa.ForeignKey("moodprint.journal_entries.id", ondelete="CASCADE")), schema=SCHEMA)
    op.add_column("memories", sa.Column("source_entry_version", sa.Integer()), schema=SCHEMA)
    op.alter_column("memories", "proposal_id", nullable=True, schema=SCHEMA)
    op.execute("""ALTER TABLE moodprint.memories ADD CONSTRAINT ck_memories_origin CHECK (
      (origin='approved' AND proposal_id IS NOT NULL AND source_entry_id IS NULL) OR
      (origin='journal_auto' AND proposal_id IS NULL AND source_entry_id IS NOT NULL
       AND source_entry_version IS NOT NULL AND source_entry_version >= 1)) NOT VALID""")
    op.execute("ALTER TABLE moodprint.memories VALIDATE CONSTRAINT ck_memories_origin")
    op.create_index("ix_memories_source_entry", "memories", ["source_entry_id"], schema=SCHEMA, postgresql_where=sa.text("source_entry_id IS NOT NULL"))
    op.execute("CREATE UNIQUE INDEX uq_memories_auto_text ON moodprint.memories (source_entry_id,source_entry_version,md5(text)) WHERE origin='journal_auto' AND status='active'")
    op.drop_constraint(op.f("ck_ai_runs_origin"), "ai_runs", type_="check", schema=SCHEMA)
    op.execute("ALTER TABLE moodprint.ai_runs ADD CONSTRAINT ck_ai_runs_origin CHECK (origin in ('user','proactive','collaboration','agent','journal')) NOT VALID")
    op.execute("ALTER TABLE moodprint.ai_runs VALIDATE CONSTRAINT ck_ai_runs_origin")


def downgrade():
    op.execute("""DO $guard$ BEGIN
 IF EXISTS (SELECT 1 FROM moodprint.memories WHERE origin='journal_auto')
 OR EXISTS (SELECT 1 FROM moodprint.ai_runs WHERE origin='journal') THEN
  RAISE EXCEPTION 'journal intelligence data exists; use compatible image rollback';
 END IF;
END $guard$""")
    op.drop_constraint(op.f("ck_ai_runs_origin"), "ai_runs", type_="check", schema=SCHEMA)
    op.create_check_constraint(op.f("ck_ai_runs_origin"), "ai_runs", "origin in ('user','proactive','collaboration','agent')", schema=SCHEMA)
    op.drop_index("uq_memories_auto_text", table_name="memories", schema=SCHEMA)
    op.drop_index("ix_memories_source_entry", table_name="memories", schema=SCHEMA)
    op.drop_constraint(op.f("ck_memories_origin"), "memories", type_="check", schema=SCHEMA)
    op.alter_column("memories", "proposal_id", nullable=False, schema=SCHEMA)
    for column in ("source_entry_version", "source_entry_id", "origin"):
        op.drop_column("memories", column, schema=SCHEMA)
    for table in reversed(TABLES):
        op.drop_table(table, schema=SCHEMA)
