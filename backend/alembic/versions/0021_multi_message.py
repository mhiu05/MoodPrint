"""Multi-bubble replies and server-originated (proactive) runs.

Expand only, no backfill: legacy messages become part 0 of 1 and legacy runs/turns become
origin='user' through constant server defaults (metadata-only on PostgreSQL >= 11). The
old image keeps inserting without these columns. ``uq_ai_messages_run_part`` replaces
``uq_ai_messages_run_id``; it is named explicitly because the naming convention would
otherwise reuse the old name. Forward-only: once a run stores several parts, the old
unique constraint can never be restored.
"""

import sqlalchemy as sa

from alembic import op

revision = "0021_multi_message"
down_revision = "0020_private_profile_retirement"
branch_labels = None
depends_on = None

SCHEMA = "moodprint"


def upgrade():
    op.add_column(
        "ai_messages",
        sa.Column("part_index", sa.SmallInteger(), nullable=False, server_default=sa.text("0")),
        schema=SCHEMA,
    )
    op.add_column(
        "ai_messages",
        sa.Column("part_count", sa.SmallInteger(), nullable=False, server_default=sa.text("1")),
        schema=SCHEMA,
    )
    op.create_check_constraint(
        op.f("ck_ai_messages_part"),
        "ai_messages",
        "part_index >= 0 and part_count between 1 and 4 and part_index < part_count",
        schema=SCHEMA,
    )
    op.create_check_constraint(
        op.f("ck_ai_messages_self_single"),
        "ai_messages",
        "actor = 'bot' or (part_index = 0 and part_count = 1)",
        schema=SCHEMA,
    )
    op.create_unique_constraint(
        op.f("uq_ai_messages_run_part"), "ai_messages", ["run_id", "actor", "part_index"], schema=SCHEMA
    )
    op.drop_constraint(op.f("uq_ai_messages_run_id"), "ai_messages", type_="unique", schema=SCHEMA)

    op.add_column(
        "ai_runs",
        sa.Column("origin", sa.String(16), nullable=False, server_default=sa.text("'user'")),
        schema=SCHEMA,
    )
    op.add_column("ai_runs", sa.Column("proactive_slot", sa.String(16), nullable=True), schema=SCHEMA)
    op.alter_column("ai_runs", "conversation_id", nullable=True, schema=SCHEMA)
    op.create_check_constraint(
        op.f("ck_ai_runs_origin"), "ai_runs", "origin in ('user', 'proactive')", schema=SCHEMA
    )
    op.create_check_constraint(
        op.f("ck_ai_runs_slot"),
        "ai_runs",
        "(origin = 'proactive') = (proactive_slot is not null) "
        "and (proactive_slot is null or proactive_slot in ('morning', 'evening'))",
        schema=SCHEMA,
    )
    op.create_check_constraint(
        op.f("ck_ai_runs_conversation"),
        "ai_runs",
        "origin <> 'user' or conversation_id is not null",
        schema=SCHEMA,
    )
    # Quota/rate/concurrency of a person count only origin='user' runs.
    op.create_index(
        op.f("ix_ai_runs_user_origin_created"),
        "ai_runs",
        ["user_id", "origin", "created_at"],
        schema=SCHEMA,
    )

    op.add_column(
        "ai_turns",
        sa.Column("origin", sa.String(16), nullable=False, server_default=sa.text("'user'")),
        schema=SCHEMA,
    )
    op.alter_column("ai_turns", "session_id", nullable=True, schema=SCHEMA)
    op.create_check_constraint(
        op.f("ck_ai_turns_origin"), "ai_turns", "origin in ('user', 'proactive')", schema=SCHEMA
    )
    op.create_check_constraint(
        op.f("ck_ai_turns_session"),
        "ai_turns",
        "(origin = 'user') = (session_id is not null)",
        schema=SCHEMA,
    )


def downgrade():
    raise RuntimeError("Destructive rollback disabled; use a reviewed forward migration")
