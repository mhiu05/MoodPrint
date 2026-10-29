"""Add private multiple-per-day journal entries and durable media cleanup; preserve Mood rows."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0019_journal"
down_revision = "0018_app_feedback"
branch_labels = None
depends_on = None

TABLES = ("journal_entries", "journal_media", "journal_storage_deletions")


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
        "journal_entries",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("mood", sa.SmallInteger(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "emotions", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column(
            "factors", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column("status", sa.String(8), nullable=False, server_default="saved"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("clock_timestamp()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("clock_timestamp()"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_journal_entries")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["moodprint.users.id"], name=op.f("fk_journal_entries_user_id_users")
        ),
        sa.CheckConstraint("mood between 1 and 5", name=op.f("ck_journal_entries_mood")),
        sa.CheckConstraint(
            "char_length(text) <= 10000", name=op.f("ck_journal_entries_text_length")
        ),
        sa.CheckConstraint(
            "jsonb_typeof(emotions) = 'array' AND jsonb_array_length(emotions) <= 12",
            name=op.f("ck_journal_entries_emotions"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(factors) = 'array' AND jsonb_array_length(factors) <= 12",
            name=op.f("ck_journal_entries_factors"),
        ),
        sa.CheckConstraint("status in ('draft','saved')", name=op.f("ck_journal_entries_status")),
        sa.CheckConstraint("version >= 1", name=op.f("ck_journal_entries_version")),
        schema="moodprint",
    )
    op.create_index(
        "ix_journal_entries_owner_date",
        "journal_entries",
        ["user_id", "local_date", "created_at", "id"],
        schema="moodprint",
    )
    op.create_index(
        "ix_journal_entries_owner_status_updated",
        "journal_entries",
        ["user_id", "status", "updated_at"],
        schema="moodprint",
    )
    op.create_table(
        "journal_media",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("entry_id", sa.UUID(), nullable=False),
        sa.Column("type", sa.String(8), nullable=False),
        sa.Column("object_path", sa.String(512), nullable=False),
        sa.Column("mime_type", sa.String(127), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("status", sa.String(8), nullable=False, server_default="pending"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("clock_timestamp()"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_journal_media")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["moodprint.users.id"], name=op.f("fk_journal_media_user_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["entry_id"],
            ["moodprint.journal_entries.id"],
            name=op.f("fk_journal_media_entry_id_journal_entries"),
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("object_path", name=op.f("uq_journal_media_object_path")),
        sa.CheckConstraint("type in ('image','audio','video')", name=op.f("ck_journal_media_type")),
        sa.CheckConstraint("size_bytes > 0", name=op.f("ck_journal_media_size")),
        sa.CheckConstraint(
            "duration_seconds is null or duration_seconds >= 0",
            name=op.f("ck_journal_media_duration"),
        ),
        sa.CheckConstraint("status in ('pending','ready')", name=op.f("ck_journal_media_status")),
        schema="moodprint",
    )
    op.create_index("ix_journal_media_user_id", "journal_media", ["user_id"], schema="moodprint")
    op.create_index("ix_journal_media_entry_id", "journal_media", ["entry_id"], schema="moodprint")
    op.create_index(
        "ix_journal_media_status_created",
        "journal_media",
        ["status", "created_at"],
        schema="moodprint",
    )
    op.create_table(
        "journal_storage_deletions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("object_path", sa.String(512), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("clock_timestamp()"),
        ),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_journal_storage_deletions")),
        sa.UniqueConstraint("object_path", name=op.f("uq_journal_storage_deletions_object_path")),
        sa.CheckConstraint("attempts >= 0", name=op.f("ck_journal_storage_deletions_attempts")),
        schema="moodprint",
    )
    for table in TABLES:
        protect(table)


def downgrade():
    # Local-only Alembic runner fences remote targets. Production rollback retains these tables.
    for table in reversed(TABLES):
        op.drop_table(table, schema="moodprint")
