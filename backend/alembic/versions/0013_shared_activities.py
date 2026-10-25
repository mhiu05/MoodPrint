"""Shared activities: sessions, participants, responses and the connection activity watermark.

Expand only. One non-terminal session per connection is enforced by a partial unique index.
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0013_shared_activities"
down_revision = "0012_matching_v2"
branch_labels = None
depends_on = None

OPEN = "state IN ('invited','active','paused')"


def protect(table: str) -> None:
    """RLS on, no PUBLIC or Supabase API role access; only the backend runtime role."""
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
    op.add_column(
        "connections",
        sa.Column("activity_seq", sa.BigInteger(), server_default="0", nullable=False),
        schema="moodprint",
    )
    op.create_table(
        "activity_sessions",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "connection_id", sa.UUID(), sa.ForeignKey("moodprint.connections.id"), nullable=False
        ),
        sa.Column("pair_id", sa.UUID(), sa.ForeignKey("moodprint.pairs.id"), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("definition_version", sa.String(24), nullable=False),
        sa.Column("inviter_id", sa.UUID(), sa.ForeignKey("moodprint.users.id"), nullable=False),
        sa.Column("invitee_id", sa.UUID(), sa.ForeignKey("moodprint.users.id"), nullable=False),
        sa.Column("state", sa.String(12), nullable=False),
        sa.Column("end_reason", sa.String(24)),
        sa.Column("round", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("phase", sa.String(12), server_default="invited", nullable=False),
        sa.Column("content", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("timer", JSONB()),
        sa.Column("score", JSONB()),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("deadline_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("kind IN ('icebreaker','coop_quiz','focus')", name="kind"),
        sa.CheckConstraint(
            "state IN ('invited','active','paused','completed','ended','declined',"
            "'cancelled','expired','aborted')",
            name="state",
        ),
        sa.CheckConstraint("inviter_id <> invitee_id", name="distinct_participants"),
        schema="moodprint",
    )
    op.create_index(
        "uq_activity_open_per_connection",
        "activity_sessions",
        ["connection_id"],
        unique=True,
        postgresql_where=sa.text(OPEN),
        schema="moodprint",
    )
    op.create_index(
        "ix_activity_sessions_deadline",
        "activity_sessions",
        ["deadline_at"],
        postgresql_where=sa.text(OPEN),
        schema="moodprint",
    )
    op.create_index(
        "ix_activity_sessions_connection_created",
        "activity_sessions",
        ["connection_id", sa.text("created_at DESC")],
        schema="moodprint",
    )
    op.create_index(
        "ix_activity_sessions_inviter_created",
        "activity_sessions",
        ["inviter_id", "created_at"],
        schema="moodprint",
    )
    op.create_table(
        "activity_participants",
        sa.Column(
            "session_id",
            sa.UUID(),
            sa.ForeignKey("moodprint.activity_sessions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("moodprint.users.id"), primary_key=True),
        sa.Column("role", sa.String(8), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        sa.Column("ready_round", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("feedback", sa.String(12)),
        sa.Column("feedback_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("role IN ('inviter','invitee')", name="role"),
        sa.CheckConstraint(
            "feedback IS NULL OR feedback IN ('liked','neutral','not_for_me')", name="feedback"
        ),
        schema="moodprint",
    )
    op.create_index(
        "ix_activity_participants_user_id",
        "activity_participants",
        ["user_id"],
        schema="moodprint",
    )
    op.create_table(
        "activity_responses",
        sa.Column(
            "session_id",
            sa.UUID(),
            sa.ForeignKey("moodprint.activity_sessions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("moodprint.users.id"), primary_key=True),
        sa.Column("round", sa.SmallInteger(), primary_key=True),
        sa.Column("item_id", sa.String(32), nullable=False),
        sa.Column("choice", sa.SmallInteger()),
        sa.Column("text", sa.String(140)),
        sa.Column("skipped", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("round BETWEEN 1 AND 10", name="round"),
        sa.CheckConstraint("skipped OR choice IS NOT NULL OR text IS NOT NULL", name="answer"),
        schema="moodprint",
    )
    op.create_index(
        "ix_activity_responses_user_id", "activity_responses", ["user_id"], schema="moodprint"
    )
    for table in ("activity_sessions", "activity_participants", "activity_responses"):
        protect(table)


def downgrade():
    raise RuntimeError("Expand-only migration; use a reviewed forward migration instead")
