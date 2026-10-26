BEGIN;

-- Running upgrade 0014_moderation -> 0015_context_privacy

ALTER TABLE moodprint.ai_turns ADD COLUMN context_policy VARCHAR(32);

UPDATE moodprint.alembic_version SET version_num='0015_context_privacy' WHERE moodprint.alembic_version.version_num = '0014_moderation';

COMMIT;
