BEGIN;

-- Running upgrade 0019_journal -> 0020_private_profile_retirement

SET LOCAL lock_timeout = '5s';

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
        );

UPDATE moodprint.memory_proposals
        SET status = 'expired', text = '', version = version + 1,
            decided_at = clock_timestamp()
        WHERE purpose = 'memory' AND status = 'pending' AND source_id IS NOT NULL;

DELETE FROM moodprint.memory_proposals WHERE purpose = 'private_item';

UPDATE moodprint.memory_proposals SET source_id = NULL, source_version = NULL WHERE source_id IS NOT NULL;

UPDATE moodprint.memories SET source_id = NULL, source_version = NULL WHERE source_id IS NOT NULL;

ALTER TABLE moodprint.memory_proposals DROP CONSTRAINT fk_memory_proposals_source_id_private_items;

DROP INDEX moodprint.ix_memory_proposals_source_id;

ALTER TABLE moodprint.memory_proposals DROP CONSTRAINT ck_memory_proposals_purpose;

ALTER TABLE moodprint.memory_proposals DROP CONSTRAINT ck_memory_proposals_source_pair;

ALTER TABLE moodprint.memory_proposals DROP COLUMN source_id;

ALTER TABLE moodprint.memory_proposals DROP COLUMN source_version;

ALTER TABLE moodprint.memory_proposals DROP COLUMN purpose;

ALTER TABLE moodprint.memories DROP CONSTRAINT fk_memories_source_id_private_items;

DROP INDEX moodprint.ix_memories_source_id;

ALTER TABLE moodprint.memories DROP COLUMN source_id;

ALTER TABLE moodprint.memories DROP COLUMN source_version;

DROP TABLE moodprint.private_items;

UPDATE moodprint.alembic_version SET version_num='0020_private_profile_retirement' WHERE moodprint.alembic_version.version_num = '0019_journal';

COMMIT;

