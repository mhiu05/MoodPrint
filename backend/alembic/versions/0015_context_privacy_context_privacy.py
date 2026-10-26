"""Content-free context policy stamps; legacy transcripts remain viewable.

Expand only: no backfill can prove that a legacy turn had filtered its context.
No new tables, grants, source data, or snapshot retention.
"""

import sqlalchemy as sa

from alembic import op

revision = "0015_context_privacy"
down_revision = "0014_moderation"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "ai_turns", sa.Column("context_policy", sa.String(32), nullable=True), schema="moodprint"
    )


def downgrade():
    raise RuntimeError("Destructive rollback disabled; use a reviewed forward migration")
