"""Approved-memory derived vectors and leased, version-fenced jobs. Expand only."""

import sqlalchemy as sa
from sqlalchemy.types import UserDefinedType

from alembic import op

revision = "0009_memory_embeddings"
down_revision = "0008_memory_proposals"
branch_labels = None
depends_on = None


class Vector(UserDefinedType):
    def get_col_spec(self, **kw):
        return "extensions.vector"


def snapshot_columns():
    return [
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "memory_id",
            sa.UUID(),
            sa.ForeignKey("moodprint.memories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.UUID(),
            sa.ForeignKey("moodprint.users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("bot_id", sa.String(16), nullable=False),
        sa.Column("memory_version", sa.Integer(), nullable=False),
        sa.Column("data_version", sa.Integer(), nullable=False),
        sa.Column("preference_version", sa.Integer(), nullable=False),
        sa.Column("ai_consent_version", sa.Integer(), nullable=False),
        sa.Column("mem_consent_version", sa.Integer(), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
    ]


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS extensions")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions")
    # Do not move an already installed extension implicitly: deployment must review
    # this incompatibility rather than changing another application's search_path.
    op.execute("""DO $vector$ BEGIN
      IF NOT EXISTS (SELECT 1 FROM pg_extension e JOIN pg_namespace n ON n.oid=e.extnamespace WHERE e.extname='vector' AND n.nspname='extensions') THEN
        RAISE EXCEPTION 'vector extension must be installed in extensions schema';
      END IF;
    END $vector$""")
    op.create_table(
        "memory_embedding_jobs",
        *snapshot_columns(),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("lease_token", sa.UUID()),
        sa.Column("last_error", sa.String(48)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "memory_id",
            "memory_version",
            "preference_version",
            "ai_consent_version",
            "mem_consent_version",
            "model",
            "dimensions",
            name="uq_memory_embedding_jobs_snapshot",
        ),
        sa.CheckConstraint(
            "status in ('pending','running','retry','succeeded','cancelled','failed')",
            name="status",
        ),
        sa.CheckConstraint("attempts between 0 and 8", name="attempts"),
        sa.CheckConstraint("dimensions in (256,512,1024,2048)", name="dimensions"),
        sa.CheckConstraint("bot_id in ('may','guong','nhip','rure')", name="bot"),
        schema="moodprint",
    )
    op.create_index(
        "ix_memory_embedding_jobs_due",
        "memory_embedding_jobs",
        ["status", "available_at", "lease_until"],
        schema="moodprint",
    )
    op.create_index(
        "ix_memory_embedding_jobs_owner",
        "memory_embedding_jobs",
        ["user_id", "memory_id"],
        schema="moodprint",
    )
    op.create_table(
        "memory_embeddings",
        *snapshot_columns(),
        sa.Column("embedding", Vector(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("memory_id", "model", "dimensions", name="uq_memory_embeddings_config"),
        sa.CheckConstraint(
            "dimensions in (256,512,1024,2048) and extensions.vector_dims(embedding) = dimensions",
            name="dimensions",
        ),
        sa.CheckConstraint("bot_id in ('may','guong','nhip','rure')", name="bot"),
        schema="moodprint",
    )
    op.create_index(
        "ix_memory_embeddings_scope",
        "memory_embeddings",
        ["user_id", "bot_id", "model", "dimensions"],
        schema="moodprint",
    )
    for table in ("memory_embedding_jobs", "memory_embeddings"):
        op.execute(f"ALTER TABLE moodprint.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"REVOKE ALL ON moodprint.{table} FROM PUBLIC")
        op.execute(f"""DO $acl$
DECLARE role_name text;
BEGIN
  FOREACH role_name IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=role_name) THEN
      EXECUTE 'REVOKE ALL ON moodprint.{table} FROM ' || quote_ident(role_name);
    END IF;
  END LOOP;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='moodprint_runtime') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE ON moodprint.{table} TO moodprint_runtime;
    CREATE POLICY backend_access ON moodprint.{table} FOR ALL TO moodprint_runtime USING (true) WITH CHECK (true);
    GRANT USAGE ON SCHEMA extensions TO moodprint_runtime;
  END IF;
END $acl$""")


def downgrade():
    raise RuntimeError(
        "Destructive rollback disabled; disable semantic memory and use a reviewed forward migration"
    )
