"""Owner-private birth-year declarations; no automatic permission backfill."""

import sqlalchemy as sa

from alembic import op

revision = "0004_eligibility"
down_revision = "0003_lifecycle"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "age_declarations",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("birth_year", sa.SmallInteger(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("policy_version", sa.String(32), nullable=False),
        sa.Column("declared_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("adult_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["moodprint.users.id"], name=op.f("fk_age_declarations_user_id_users")
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_age_declarations")),
        sa.CheckConstraint(
            "birth_year between 1900 and 9999", name=op.f("ck_age_declarations_birth_year_range")
        ),
        sa.CheckConstraint(
            "version >= 1", name=op.f("ck_age_declarations_age_declaration_version")
        ),
        schema="moodprint",
    )


def downgrade():
    raise RuntimeError("Destructive rollback disabled; use a reviewed forward migration")
