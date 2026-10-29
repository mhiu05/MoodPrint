BEGIN;

-- Running upgrade 0018_app_feedback -> 0019_journal

CREATE TABLE moodprint.journal_entries (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    local_date DATE NOT NULL, 
    timezone VARCHAR(64) NOT NULL, 
    mood SMALLINT NOT NULL, 
    text TEXT DEFAULT '' NOT NULL, 
    emotions JSONB DEFAULT '[]'::jsonb NOT NULL, 
    factors JSONB DEFAULT '[]'::jsonb NOT NULL, 
    status VARCHAR(8) DEFAULT 'saved' NOT NULL, 
    version INTEGER DEFAULT '1' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
    CONSTRAINT pk_journal_entries PRIMARY KEY (id), 
    CONSTRAINT fk_journal_entries_user_id_users FOREIGN KEY(user_id) REFERENCES moodprint.users (id), 
    CONSTRAINT ck_journal_entries_mood CHECK (mood between 1 and 5), 
    CONSTRAINT ck_journal_entries_text_length CHECK (char_length(text) <= 10000), 
    CONSTRAINT ck_journal_entries_emotions CHECK (jsonb_typeof(emotions) = 'array' AND jsonb_array_length(emotions) <= 12), 
    CONSTRAINT ck_journal_entries_factors CHECK (jsonb_typeof(factors) = 'array' AND jsonb_array_length(factors) <= 12), 
    CONSTRAINT ck_journal_entries_status CHECK (status in ('draft','saved')), 
    CONSTRAINT ck_journal_entries_version CHECK (version >= 1)
);

CREATE INDEX ix_journal_entries_owner_date ON moodprint.journal_entries (user_id, local_date, created_at, id);

CREATE INDEX ix_journal_entries_owner_status_updated ON moodprint.journal_entries (user_id, status, updated_at);

CREATE TABLE moodprint.journal_media (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    entry_id UUID NOT NULL, 
    type VARCHAR(8) NOT NULL, 
    object_path VARCHAR(512) NOT NULL, 
    mime_type VARCHAR(127) NOT NULL, 
    size_bytes BIGINT NOT NULL, 
    duration_seconds FLOAT, 
    status VARCHAR(8) DEFAULT 'pending' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
    CONSTRAINT pk_journal_media PRIMARY KEY (id), 
    CONSTRAINT fk_journal_media_user_id_users FOREIGN KEY(user_id) REFERENCES moodprint.users (id), 
    CONSTRAINT fk_journal_media_entry_id_journal_entries FOREIGN KEY(entry_id) REFERENCES moodprint.journal_entries (id) ON DELETE CASCADE, 
    CONSTRAINT uq_journal_media_object_path UNIQUE (object_path), 
    CONSTRAINT ck_journal_media_type CHECK (type in ('image','audio','video')), 
    CONSTRAINT ck_journal_media_size CHECK (size_bytes > 0), 
    CONSTRAINT ck_journal_media_duration CHECK (duration_seconds is null or duration_seconds >= 0), 
    CONSTRAINT ck_journal_media_status CHECK (status in ('pending','ready'))
);

CREATE INDEX ix_journal_media_user_id ON moodprint.journal_media (user_id);

CREATE INDEX ix_journal_media_entry_id ON moodprint.journal_media (entry_id);

CREATE INDEX ix_journal_media_status_created ON moodprint.journal_media (status, created_at);

CREATE TABLE moodprint.journal_storage_deletions (
    id UUID NOT NULL, 
    object_path VARCHAR(512) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
    attempts INTEGER DEFAULT '0' NOT NULL, 
    CONSTRAINT pk_journal_storage_deletions PRIMARY KEY (id), 
    CONSTRAINT uq_journal_storage_deletions_object_path UNIQUE (object_path), 
    CONSTRAINT ck_journal_storage_deletions_attempts CHECK (attempts >= 0)
);

ALTER TABLE moodprint.journal_entries ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON moodprint.journal_entries FROM PUBLIC;

DO $acl$
DECLARE r text;
BEGIN
 FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=r) THEN
   EXECUTE 'REVOKE ALL ON moodprint.journal_entries FROM ' || quote_ident(r);
  END IF;
 END LOOP;
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='moodprint_runtime') THEN
  GRANT SELECT,INSERT,UPDATE,DELETE ON moodprint.journal_entries TO moodprint_runtime;
  CREATE POLICY backend_access ON moodprint.journal_entries FOR ALL TO moodprint_runtime USING (true) WITH CHECK (true);
 END IF;
END $acl$;

ALTER TABLE moodprint.journal_media ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON moodprint.journal_media FROM PUBLIC;

DO $acl$
DECLARE r text;
BEGIN
 FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=r) THEN
   EXECUTE 'REVOKE ALL ON moodprint.journal_media FROM ' || quote_ident(r);
  END IF;
 END LOOP;
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='moodprint_runtime') THEN
  GRANT SELECT,INSERT,UPDATE,DELETE ON moodprint.journal_media TO moodprint_runtime;
  CREATE POLICY backend_access ON moodprint.journal_media FOR ALL TO moodprint_runtime USING (true) WITH CHECK (true);
 END IF;
END $acl$;

ALTER TABLE moodprint.journal_storage_deletions ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON moodprint.journal_storage_deletions FROM PUBLIC;

DO $acl$
DECLARE r text;
BEGIN
 FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=r) THEN
   EXECUTE 'REVOKE ALL ON moodprint.journal_storage_deletions FROM ' || quote_ident(r);
  END IF;
 END LOOP;
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='moodprint_runtime') THEN
  GRANT SELECT,INSERT,UPDATE,DELETE ON moodprint.journal_storage_deletions TO moodprint_runtime;
  CREATE POLICY backend_access ON moodprint.journal_storage_deletions FOR ALL TO moodprint_runtime USING (true) WITH CHECK (true);
 END IF;
END $acl$;

UPDATE moodprint.alembic_version SET version_num='0019_journal' WHERE moodprint.alembic_version.version_num = '0018_app_feedback';

COMMIT;

