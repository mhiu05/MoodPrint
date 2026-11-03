"""Add policy identity to collaboration receipts, preserving legacy preference values."""

import sqlalchemy as sa

from alembic import op

revision = "0028_collaboration_defaults"
down_revision = "0027_maps_jobs"
branch_labels = None
depends_on = None


def upgrade():
    for table in ("ai_collaborations", "ai_orchestration_steps"):
        op.add_column(table, sa.Column("permission_policy", sa.String(32), nullable=False,
                                      server_default=sa.text("'sharing-v1'")), schema="moodprint")


def downgrade():
    # Roll back to compatible code with the columns retained until these receipts expire.
    bind = op.get_bind()
    for table in ("ai_orchestration_steps", "ai_collaborations"):
        if bind.scalar(sa.text(f"select exists (select 1 from moodprint.{table} "
                               "where permission_policy <> 'sharing-v1')")):
            raise RuntimeError("Cannot remove policy identity while non-legacy receipts remain")
    for table in ("ai_orchestration_steps", "ai_collaborations"):
        op.drop_column(table, "permission_policy", schema="moodprint")
