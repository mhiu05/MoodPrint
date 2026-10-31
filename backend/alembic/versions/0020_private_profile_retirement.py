"""Remove private profile notes while preserving approved AI memories."""

from alembic import op

revision = "0020_private_profile_retirement"
down_revision = "0019_journal"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute(
        """
        UPDATE moodprint.users AS u
        SET data_version = u.data_version + 1
        WHERE EXISTS (
            SELECT 1 FROM moodprint.private_items AS item WHERE item.user_id = u.id
        ) OR EXISTS (
            SELECT 1 FROM moodprint.memory_proposals AS proposal
            WHERE proposal.user_id = u.id
              AND (
                  proposal.purpose = 'private_item'
              OR proposal.source_id IS NOT NULL
              )
        )
        """
    )
    op.execute(
        """
        UPDATE moodprint.memory_proposals
        SET status = 'expired', text = '', version = version + 1,
            decided_at = clock_timestamp()
        WHERE purpose = 'memory' AND status = 'pending' AND source_id IS NOT NULL
        """
    )
    op.execute(
        "DELETE FROM moodprint.memory_proposals WHERE purpose = 'private_item'"
    )
    op.execute(
        "UPDATE moodprint.memory_proposals SET source_id = NULL, source_version = NULL "
        "WHERE source_id IS NOT NULL"
    )
    op.execute(
        "UPDATE moodprint.memories SET source_id = NULL, source_version = NULL "
        "WHERE source_id IS NOT NULL"
    )

    op.drop_constraint(
        op.f("fk_memory_proposals_source_id_private_items"),
        "memory_proposals",
        schema="moodprint",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_memory_proposals_source_id", table_name="memory_proposals", schema="moodprint"
    )
    op.drop_constraint(
        op.f("ck_memory_proposals_purpose"),
        "memory_proposals",
        schema="moodprint",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_memory_proposals_source_pair"),
        "memory_proposals",
        schema="moodprint",
        type_="check",
    )
    op.drop_column("memory_proposals", "source_id", schema="moodprint")
    op.drop_column("memory_proposals", "source_version", schema="moodprint")
    op.drop_column("memory_proposals", "purpose", schema="moodprint")

    op.drop_constraint(
        op.f("fk_memories_source_id_private_items"),
        "memories",
        schema="moodprint",
        type_="foreignkey",
    )
    op.drop_index("ix_memories_source_id", table_name="memories", schema="moodprint")
    op.drop_column("memories", "source_id", schema="moodprint")
    op.drop_column("memories", "source_version", schema="moodprint")
    op.drop_table("private_items", schema="moodprint")


def downgrade():
    raise RuntimeError("Destructive rollback disabled; use a reviewed forward migration")
