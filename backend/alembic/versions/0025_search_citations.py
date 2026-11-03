"""Add source provenance to saved replies; preserve old transcripts unchanged."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0025_search_citations"
down_revision = "0024_three_agent_groups"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("ai_messages", sa.Column("citations", JSONB(), nullable=False,
                  server_default=sa.text("'[]'::jsonb")), schema="moodprint")
    op.add_column("ai_messages", sa.Column("source_backed", sa.Boolean(), nullable=False,
                  server_default=sa.text("false")), schema="moodprint")
    op.create_check_constraint(op.f("ck_ai_messages_citations"), "ai_messages",
        "jsonb_typeof(citations) = 'array' and jsonb_array_length(citations) <= 8 "
        "and octet_length(citations::text) <= 24000", schema="moodprint")


def downgrade():
    # A destructive downgrade would silently strip citations from historical facts.
    raise RuntimeError("Forward-only provenance migration; roll back flags/image, retain citations")
