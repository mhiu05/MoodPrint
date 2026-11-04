BEGIN;

-- Running upgrade 0028_collaboration_defaults -> 0029_journal_intelligence

CREATE TABLE moodprint.journal_ai_settings (
    user_id UUID NOT NULL, 
    embedding_enabled BOOLEAN DEFAULT true NOT NULL, 
    auto_memory_enabled BOOLEAN DEFAULT true NOT NULL, 
    notice_version VARCHAR(32) DEFAULT 'journal-ai-v1' NOT NULL, 
    version INTEGER DEFAULT '1' NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
    CONSTRAINT pk_journal_ai_settings PRIMARY KEY (user_id), 
    CONSTRAINT ck_journal_ai_settings_version CHECK (version >= 1), 
    CONSTRAINT fk_journal_ai_settings_user_id_users FOREIGN KEY(user_id) REFERENCES moodprint.users (id) ON DELETE CASCADE
);

CREATE TABLE moodprint.journal_entry_embeddings (
    id UUID NOT NULL, 
    entry_id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    entry_version INTEGER NOT NULL, 
    settings_version INTEGER NOT NULL, 
    content_sha256 CHAR(64) NOT NULL, 
    model VARCHAR(100) NOT NULL, 
    dimensions INTEGER NOT NULL, 
    embedding extensions.vector NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
    CONSTRAINT pk_journal_entry_embeddings PRIMARY KEY (id), 
    CONSTRAINT uq_journal_entry_embeddings_config UNIQUE (entry_id, model, dimensions), 
    CONSTRAINT ck_journal_entry_embeddings_dimensions CHECK (dimensions in (256,512,1024,2048) and extensions.vector_dims(embedding) = dimensions), 
    CONSTRAINT fk_journal_entry_embeddings_entry_id_journal_entries FOREIGN KEY(entry_id) REFERENCES moodprint.journal_entries (id) ON DELETE CASCADE, 
    CONSTRAINT fk_journal_entry_embeddings_user_id_users FOREIGN KEY(user_id) REFERENCES moodprint.users (id) ON DELETE CASCADE
);

CREATE INDEX ix_journal_entry_embeddings_scope ON moodprint.journal_entry_embeddings (user_id, model, dimensions);

CREATE TABLE moodprint.journal_ai_jobs (
    id UUID NOT NULL, 
    entry_id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    kind VARCHAR(16) NOT NULL, 
    entry_version INTEGER NOT NULL, 
    settings_version INTEGER NOT NULL, 
    model VARCHAR(100) NOT NULL, 
    dimensions INTEGER, 
    status VARCHAR(16) DEFAULT 'pending' NOT NULL, 
    attempts INTEGER DEFAULT '0' NOT NULL, 
    available_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    lease_until TIMESTAMP WITH TIME ZONE, 
    lease_token UUID, 
    last_error VARCHAR(48), 
    run_id UUID, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
    CONSTRAINT pk_journal_ai_jobs PRIMARY KEY (id), 
    CONSTRAINT uq_journal_ai_jobs_snapshot UNIQUE (entry_id, kind, entry_version, settings_version, model), 
    CONSTRAINT ck_journal_ai_jobs_kind CHECK (kind in ('embed','memories')), 
    CONSTRAINT ck_journal_ai_jobs_dimensions CHECK ((dimensions is null) = (kind = 'memories')), 
    CONSTRAINT ck_journal_ai_jobs_status CHECK (status in ('pending','running','retry','succeeded','cancelled','failed','skipped')), 
    CONSTRAINT ck_journal_ai_jobs_attempts CHECK (attempts between 0 and 8), 
    CONSTRAINT fk_journal_ai_jobs_entry_id_journal_entries FOREIGN KEY(entry_id) REFERENCES moodprint.journal_entries (id) ON DELETE CASCADE, 
    CONSTRAINT fk_journal_ai_jobs_user_id_users FOREIGN KEY(user_id) REFERENCES moodprint.users (id) ON DELETE CASCADE, 
    CONSTRAINT fk_journal_ai_jobs_run_id_ai_runs FOREIGN KEY(run_id) REFERENCES moodprint.ai_runs (id) ON DELETE SET NULL
);

CREATE INDEX ix_journal_ai_jobs_due ON moodprint.journal_ai_jobs (status, available_at, lease_until);

CREATE INDEX ix_journal_ai_jobs_owner ON moodprint.journal_ai_jobs (user_id, kind, created_at);

ALTER TABLE moodprint.journal_ai_settings ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON moodprint.journal_ai_settings FROM PUBLIC;

DO $acl$
DECLARE r text;
BEGIN
 FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=r) THEN
   EXECUTE 'REVOKE ALL ON moodprint.journal_ai_settings FROM ' || quote_ident(r);
  END IF;
 END LOOP;
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='moodprint_runtime') THEN
  GRANT SELECT,INSERT,UPDATE,DELETE ON moodprint.journal_ai_settings TO moodprint_runtime;
  CREATE POLICY backend_access ON moodprint.journal_ai_settings FOR ALL TO moodprint_runtime USING (true) WITH CHECK (true);
 END IF;
END $acl$;

ALTER TABLE moodprint.journal_entry_embeddings ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON moodprint.journal_entry_embeddings FROM PUBLIC;

DO $acl$
DECLARE r text;
BEGIN
 FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=r) THEN
   EXECUTE 'REVOKE ALL ON moodprint.journal_entry_embeddings FROM ' || quote_ident(r);
  END IF;
 END LOOP;
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='moodprint_runtime') THEN
  GRANT SELECT,INSERT,UPDATE,DELETE ON moodprint.journal_entry_embeddings TO moodprint_runtime;
  CREATE POLICY backend_access ON moodprint.journal_entry_embeddings FOR ALL TO moodprint_runtime USING (true) WITH CHECK (true);
 END IF;
END $acl$;

ALTER TABLE moodprint.journal_ai_jobs ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON moodprint.journal_ai_jobs FROM PUBLIC;

DO $acl$
DECLARE r text;
BEGIN
 FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=r) THEN
   EXECUTE 'REVOKE ALL ON moodprint.journal_ai_jobs FROM ' || quote_ident(r);
  END IF;
 END LOOP;
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='moodprint_runtime') THEN
  GRANT SELECT,INSERT,UPDATE,DELETE ON moodprint.journal_ai_jobs TO moodprint_runtime;
  CREATE POLICY backend_access ON moodprint.journal_ai_jobs FOR ALL TO moodprint_runtime USING (true) WITH CHECK (true);
 END IF;
END $acl$;

ALTER TABLE moodprint.memories ADD COLUMN origin VARCHAR(16) DEFAULT 'approved' NOT NULL;

ALTER TABLE moodprint.memories ADD COLUMN source_entry_id UUID;

ALTER TABLE moodprint.memories ADD CONSTRAINT fk_memories_source_entry_id_journal_entries FOREIGN KEY(source_entry_id) REFERENCES moodprint.journal_entries (id) ON DELETE CASCADE;

ALTER TABLE moodprint.memories ADD COLUMN source_entry_version INTEGER;

ALTER TABLE moodprint.memories ALTER COLUMN proposal_id DROP NOT NULL;

ALTER TABLE moodprint.memories ADD CONSTRAINT ck_memories_origin CHECK (
      (origin='approved' AND proposal_id IS NOT NULL AND source_entry_id IS NULL) OR
      (origin='journal_auto' AND proposal_id IS NULL AND source_entry_id IS NOT NULL
       AND source_entry_version IS NOT NULL AND source_entry_version >= 1)) NOT VALID;

ALTER TABLE moodprint.memories VALIDATE CONSTRAINT ck_memories_origin;

CREATE INDEX ix_memories_source_entry ON moodprint.memories (source_entry_id) WHERE source_entry_id IS NOT NULL;

CREATE UNIQUE INDEX uq_memories_auto_text ON moodprint.memories (source_entry_id,source_entry_version,md5(text)) WHERE origin='journal_auto' AND status='active';

ALTER TABLE moodprint.ai_runs DROP CONSTRAINT ck_ai_runs_origin;

ALTER TABLE moodprint.ai_runs ADD CONSTRAINT ck_ai_runs_origin CHECK (origin in ('user','proactive','collaboration','agent','journal')) NOT VALID;

ALTER TABLE moodprint.ai_runs VALIDATE CONSTRAINT ck_ai_runs_origin;

UPDATE moodprint.alembic_version SET version_num='0029_journal_intelligence' WHERE moodprint.alembic_version.version_num = '0028_collaboration_defaults';

COMMIT;

