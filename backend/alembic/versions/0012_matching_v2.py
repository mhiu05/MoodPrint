"""Matching v2: taxonomy/scorer versions per row and content-free daily counters. Expand only."""

import sqlalchemy as sa

from alembic import op

revision = "0012_matching_v2"
down_revision = "0011_social_stabilization"
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
    # Constant defaults are metadata-only in PostgreSQL 17 and label existing rows correctly.
    op.add_column(
        "published_profiles",
        sa.Column("taxonomy_version", sa.String(8), server_default="v1", nullable=False),
        schema="moodprint",
    )
    op.add_column(
        "candidate_references",
        sa.Column("scoring_version", sa.String(16), server_default="rules-v1", nullable=False),
        schema="moodprint",
    )
    op.add_column(
        "candidate_references", sa.Column("rank", sa.SmallInteger()), schema="moodprint"
    )
    op.create_table(
        "matching_stats_daily",
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("scoring_version", sa.String(16), nullable=False),
        sa.Column("impressions", sa.Integer(), server_default="0", nullable=False),
        sa.Column("requests", sa.Integer(), server_default="0", nullable=False),
        sa.Column("accepts", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("day", "scoring_version", name="pk_matching_stats_daily"),
        schema="moodprint",
    )
    protect("matching_stats_daily")


def downgrade():
    raise RuntimeError("Expand-only migration; use a reviewed forward migration instead")
