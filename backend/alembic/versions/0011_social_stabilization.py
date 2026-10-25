"""Read markers for unread counts, last-seen activity and three lookup indexes. Expand only."""

import sqlalchemy as sa

from alembic import op

revision = "0011_social_stabilization"
down_revision = "0010_account_deletion"
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
    # NULL = not seen since this release; retrieval treats it as active for a grace period.
    op.add_column(
        "users", sa.Column("last_seen_at", sa.DateTime(timezone=True)), schema="moodprint"
    )
    op.create_table(
        "connection_reads",
        sa.Column(
            "connection_id", sa.UUID(), sa.ForeignKey("moodprint.connections.id"), nullable=False
        ),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("moodprint.users.id"), nullable=False),
        sa.Column("last_read_seq", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("connection_id", "user_id", name="pk_connection_reads"),
        sa.CheckConstraint("last_read_seq >= 0", name="read_seq"),
        schema="moodprint",
    )
    op.create_index(
        "ix_connection_reads_user_id", "connection_reads", ["user_id"], schema="moodprint"
    )
    op.create_index("ix_blocks_blocked_id", "blocks", ["blocked_id"], schema="moodprint")
    op.create_index(
        "ix_candidate_references_peer_id", "candidate_references", ["peer_id"], schema="moodprint"
    )
    op.create_index(
        "ix_connection_requests_recipient_status",
        "connection_requests",
        ["recipient_id", "status"],
        schema="moodprint",
    )
    protect("connection_reads")


def downgrade():
    raise RuntimeError("Expand-only migration; use a reviewed forward migration instead")
