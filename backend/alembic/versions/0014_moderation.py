"""Staff moderation: roles, audited actions, report workflow and account restrictions.

Expand only. Staff roles are granted by an operator (reviewed SQL or the local-only
scripts/grant_staff_role.py), never through the API.
"""

import sqlalchemy as sa

from alembic import op

revision = "0014_moderation"
down_revision = "0013_shared_activities"
branch_labels = None
depends_on = None


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
    op.create_table(
        "staff_roles",
        sa.Column(
            "user_id", sa.UUID(), sa.ForeignKey("moodprint.users.id"), primary_key=True
        ),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column(
            "granted_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("granted_by", sa.String(64), nullable=False),
        sa.CheckConstraint("role IN ('moderator','admin')", name="role"),
        schema="moodprint",
    )
    op.add_column(
        "reports",
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        schema="moodprint",
    )
    op.add_column(
        "reports",
        sa.Column("connection_id", sa.UUID(), sa.ForeignKey("moodprint.connections.id")),
        schema="moodprint",
    )
    op.add_column(
        "reports", sa.Column("reviewed_at", sa.DateTime(timezone=True)), schema="moodprint"
    )
    op.add_column("reports", sa.Column("resolution", sa.String(16)), schema="moodprint")
    op.create_check_constraint(
        "resolution",
        "reports",
        "resolution IS NULL OR resolution IN ('dismissed','warned','restricted','suspended')",
        schema="moodprint",
    )
    op.create_index(
        "ix_reports_status_created", "reports", ["status", "created_at"], schema="moodprint"
    )
    op.create_table(
        "moderation_actions",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("report_id", sa.UUID(), sa.ForeignKey("moodprint.reports.id")),
        sa.Column("subject_id", sa.UUID(), sa.ForeignKey("moodprint.users.id"), nullable=False),
        sa.Column("staff_id", sa.UUID(), sa.ForeignKey("moodprint.users.id"), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("until_at", sa.DateTime(timezone=True)),
        sa.Column("note", sa.String(500), server_default="", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.CheckConstraint(
            "action IN ('dismiss','warn','restrict','suspend','lift')", name="action"
        ),
        schema="moodprint",
    )
    op.create_index(
        "ix_moderation_actions_subject",
        "moderation_actions",
        ["subject_id", "created_at"],
        schema="moodprint",
    )
    op.add_column(
        "users",
        sa.Column("social_restricted_until", sa.DateTime(timezone=True)),
        schema="moodprint",
    )
    op.add_column(
        "users", sa.Column("suspended_until", sa.DateTime(timezone=True)), schema="moodprint"
    )
    for table in ("staff_roles", "moderation_actions"):
        protect(table)


def downgrade():
    raise RuntimeError("Expand-only migration; use a reviewed forward migration instead")
