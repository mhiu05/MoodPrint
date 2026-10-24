"""Fit all explicit export scopes, including owner-private age declaration."""

import sqlalchemy as sa

from alembic import op

revision = "0005_export_scope"
down_revision = "0004_eligibility"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "data_jobs",
        "scope",
        existing_type=sa.String(32),
        type_=sa.String(64),
        existing_nullable=False,
        schema="moodprint",
    )


def downgrade():
    raise RuntimeError("Destructive rollback disabled; use a reviewed forward migration")
