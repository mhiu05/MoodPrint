BEGIN;

-- Running upgrade 0020_private_profile_retirement -> 0021_multi_message

ALTER TABLE moodprint.ai_messages ADD COLUMN part_index SMALLINT DEFAULT 0 NOT NULL;

ALTER TABLE moodprint.ai_messages ADD COLUMN part_count SMALLINT DEFAULT 1 NOT NULL;

ALTER TABLE moodprint.ai_messages ADD CONSTRAINT ck_ai_messages_part CHECK (part_index >= 0 and part_count between 1 and 4 and part_index < part_count);

ALTER TABLE moodprint.ai_messages ADD CONSTRAINT ck_ai_messages_self_single CHECK (actor = 'bot' or (part_index = 0 and part_count = 1));

ALTER TABLE moodprint.ai_messages ADD CONSTRAINT uq_ai_messages_run_part UNIQUE (run_id, actor, part_index);

ALTER TABLE moodprint.ai_messages DROP CONSTRAINT uq_ai_messages_run_id;

ALTER TABLE moodprint.ai_runs ADD COLUMN origin VARCHAR(16) DEFAULT 'user' NOT NULL;

ALTER TABLE moodprint.ai_runs ADD COLUMN proactive_slot VARCHAR(16);

ALTER TABLE moodprint.ai_runs ALTER COLUMN conversation_id DROP NOT NULL;

ALTER TABLE moodprint.ai_runs ADD CONSTRAINT ck_ai_runs_origin CHECK (origin in ('user', 'proactive'));

ALTER TABLE moodprint.ai_runs ADD CONSTRAINT ck_ai_runs_slot CHECK ((origin = 'proactive') = (proactive_slot is not null) and (proactive_slot is null or proactive_slot in ('morning', 'evening')));

ALTER TABLE moodprint.ai_runs ADD CONSTRAINT ck_ai_runs_conversation CHECK (origin <> 'user' or conversation_id is not null);

CREATE INDEX ix_ai_runs_user_origin_created ON moodprint.ai_runs (user_id, origin, created_at);

ALTER TABLE moodprint.ai_turns ADD COLUMN origin VARCHAR(16) DEFAULT 'user' NOT NULL;

ALTER TABLE moodprint.ai_turns ALTER COLUMN session_id DROP NOT NULL;

ALTER TABLE moodprint.ai_turns ADD CONSTRAINT ck_ai_turns_origin CHECK (origin in ('user', 'proactive'));

ALTER TABLE moodprint.ai_turns ADD CONSTRAINT ck_ai_turns_session CHECK ((origin = 'user') = (session_id is not null));

UPDATE moodprint.alembic_version SET version_num='0021_multi_message' WHERE moodprint.alembic_version.version_num = '0020_private_profile_retirement';

-- Running upgrade 0021_multi_message -> 0022_proactive_messages

CREATE TABLE moodprint.ai_proactive_settings (
    user_id UUID NOT NULL, 
    timezone VARCHAR(64) NOT NULL, 
    quiet_start TIME WITHOUT TIME ZONE DEFAULT '22:00' NOT NULL, 
    quiet_end TIME WITHOUT TIME ZONE DEFAULT '07:00' NOT NULL, 
    badges_enabled BOOLEAN DEFAULT true NOT NULL, 
    journal_context_enabled BOOLEAN DEFAULT false NOT NULL, 
    journal_context_version INTEGER DEFAULT 0 NOT NULL, 
    version INTEGER DEFAULT 1 NOT NULL, 
    policy_version VARCHAR(32) DEFAULT 'proactive-v1' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
    CONSTRAINT pk_ai_proactive_settings PRIMARY KEY (user_id), 
    CONSTRAINT ck_ai_proactive_settings_version CHECK (version >= 1 and journal_context_version >= 0), 
    CONSTRAINT ck_ai_proactive_settings_policy CHECK (policy_version in ('proactive-v1')), 
    CONSTRAINT fk_ai_proactive_settings_user_id_users FOREIGN KEY(user_id) REFERENCES moodprint.users (id) ON DELETE CASCADE
);

CREATE TABLE moodprint.ai_proactive_schedules (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    bot_id VARCHAR(16) NOT NULL, 
    slot VARCHAR(16) NOT NULL, 
    enabled BOOLEAN DEFAULT false NOT NULL, 
    local_time TIME WITHOUT TIME ZONE NOT NULL, 
    weekdays SMALLINT DEFAULT 127 NOT NULL, 
    paused_until DATE, 
    auto_paused_at TIMESTAMP WITH TIME ZONE, 
    next_due_at TIMESTAMP WITH TIME ZONE, 
    version INTEGER DEFAULT 1 NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
    CONSTRAINT pk_ai_proactive_schedules PRIMARY KEY (id), 
    CONSTRAINT ck_ai_proactive_schedules_bot CHECK (bot_id in ('may','guong','nhip','rure','caunoi')), 
    CONSTRAINT ck_ai_proactive_schedules_slot CHECK (slot in ('morning','evening')), 
    CONSTRAINT ck_ai_proactive_schedules_window CHECK ((slot = 'morning' and local_time between '05:00' and '11:30') or (slot = 'evening' and local_time between '17:00' and '22:30')), 
    CONSTRAINT ck_ai_proactive_schedules_step CHECK (mod(extract(minute from local_time)::int, 15) = 0 and extract(second from local_time) = 0), 
    CONSTRAINT ck_ai_proactive_schedules_weekdays CHECK (weekdays between 1 and 127), 
    CONSTRAINT ck_ai_proactive_schedules_version CHECK (version >= 1), 
    CONSTRAINT fk_ai_proactive_schedules_user_id_users FOREIGN KEY(user_id) REFERENCES moodprint.users (id) ON DELETE CASCADE, 
    CONSTRAINT uq_ai_proactive_schedules_user_id UNIQUE (user_id, bot_id, slot)
);

CREATE INDEX ix_ai_proactive_schedules_due ON moodprint.ai_proactive_schedules (next_due_at) WHERE enabled and next_due_at is not null;

CREATE TABLE moodprint.ai_proactive_jobs (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    schedule_id UUID, 
    bot_id VARCHAR(16) NOT NULL, 
    slot VARCHAR(16) NOT NULL, 
    local_date DATE NOT NULL, 
    due_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    status VARCHAR(16) DEFAULT 'pending' NOT NULL, 
    skip_reason VARCHAR(32), 
    attempts SMALLINT DEFAULT 0 NOT NULL, 
    available_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    lease_token UUID, 
    lease_until TIMESTAMP WITH TIME ZONE, 
    worker_id UUID, 
    schedule_version INTEGER NOT NULL, 
    settings_version INTEGER NOT NULL, 
    run_id UUID, 
    conversation_id UUID, 
    challenge_kind VARCHAR(24), 
    last_error VARCHAR(48), 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
    finished_at TIMESTAMP WITH TIME ZONE, 
    CONSTRAINT pk_ai_proactive_jobs PRIMARY KEY (id), 
    CONSTRAINT ck_ai_proactive_jobs_status CHECK (status in ('pending', 'running', 'retry', 'delivered', 'skipped', 'cancelled', 'failed')), 
    CONSTRAINT ck_ai_proactive_jobs_attempts CHECK (attempts between 0 and 5), 
    CONSTRAINT ck_ai_proactive_jobs_window CHECK (expires_at > due_at), 
    CONSTRAINT ck_ai_proactive_jobs_skip CHECK ((status = 'skipped') = (skip_reason is not null)), 
    CONSTRAINT ck_ai_proactive_jobs_delivery CHECK (status <> 'delivered' or run_id is not null), 
    CONSTRAINT ck_ai_proactive_jobs_lease CHECK (status <> 'running' or (lease_token is not null and lease_until is not null)), 
    CONSTRAINT fk_ai_proactive_jobs_user_id_users FOREIGN KEY(user_id) REFERENCES moodprint.users (id) ON DELETE CASCADE, 
    CONSTRAINT fk_ai_proactive_jobs_schedule_id_ai_proactive_schedules FOREIGN KEY(schedule_id) REFERENCES moodprint.ai_proactive_schedules (id) ON DELETE SET NULL, 
    CONSTRAINT fk_ai_proactive_jobs_run_id_ai_runs FOREIGN KEY(run_id) REFERENCES moodprint.ai_runs (id) ON DELETE SET NULL, 
    CONSTRAINT fk_ai_proactive_jobs_conversation_id_ai_conversations FOREIGN KEY(conversation_id) REFERENCES moodprint.ai_conversations (id) ON DELETE SET NULL, 
    CONSTRAINT uq_ai_proactive_jobs_user_id UNIQUE (user_id, bot_id, slot, local_date)
);

CREATE INDEX ix_ai_proactive_jobs_due ON moodprint.ai_proactive_jobs (status, available_at) WHERE status in ('pending','retry','running');

CREATE INDEX ix_ai_proactive_jobs_owner ON moodprint.ai_proactive_jobs (user_id, local_date);

CREATE INDEX ix_ai_proactive_jobs_run_id ON moodprint.ai_proactive_jobs (run_id);

CREATE TABLE moodprint.ai_conversation_reads (
    conversation_id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    last_read_sequence INTEGER DEFAULT 0 NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
    CONSTRAINT pk_ai_conversation_reads PRIMARY KEY (conversation_id), 
    CONSTRAINT ck_ai_conversation_reads_sequence CHECK (last_read_sequence >= 0), 
    CONSTRAINT fk_ai_conversation_reads_conversation_id_ai_conversations FOREIGN KEY(conversation_id) REFERENCES moodprint.ai_conversations (id) ON DELETE CASCADE, 
    CONSTRAINT fk_ai_conversation_reads_user_id_users FOREIGN KEY(user_id) REFERENCES moodprint.users (id) ON DELETE CASCADE
);

CREATE INDEX ix_ai_conversation_reads_user_id ON moodprint.ai_conversation_reads (user_id);

CREATE TABLE moodprint.ai_message_sources (
    id UUID NOT NULL, 
    run_id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    source_kind VARCHAR(24) NOT NULL, 
    source_id UUID NOT NULL, 
    source_revision INTEGER NOT NULL, 
    source_local_date DATE, 
    policy VARCHAR(32) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
    CONSTRAINT pk_ai_message_sources PRIMARY KEY (id), 
    CONSTRAINT ck_ai_message_sources_kind CHECK (source_kind in ('journal_entry')), 
    CONSTRAINT ck_ai_message_sources_revision CHECK (source_revision >= 1), 
    CONSTRAINT fk_ai_message_sources_run_id_ai_runs FOREIGN KEY(run_id) REFERENCES moodprint.ai_runs (id) ON DELETE CASCADE, 
    CONSTRAINT fk_ai_message_sources_user_id_users FOREIGN KEY(user_id) REFERENCES moodprint.users (id) ON DELETE CASCADE, 
    CONSTRAINT uq_ai_message_sources_run_id UNIQUE (run_id, source_kind, source_id)
);

CREATE INDEX ix_ai_message_sources_user_id ON moodprint.ai_message_sources (user_id, source_id);

ALTER TABLE moodprint.ai_proactive_settings ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON moodprint.ai_proactive_settings FROM PUBLIC;

DO $acl$
DECLARE r text;
BEGIN
 FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=r) THEN
   EXECUTE 'REVOKE ALL ON moodprint.ai_proactive_settings FROM ' || quote_ident(r);
  END IF;
 END LOOP;
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='moodprint_runtime') THEN
  GRANT SELECT,INSERT,UPDATE,DELETE ON moodprint.ai_proactive_settings TO moodprint_runtime;
  CREATE POLICY backend_access ON moodprint.ai_proactive_settings FOR ALL TO moodprint_runtime USING (true) WITH CHECK (true);
 END IF;
END $acl$;

ALTER TABLE moodprint.ai_proactive_schedules ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON moodprint.ai_proactive_schedules FROM PUBLIC;

DO $acl$
DECLARE r text;
BEGIN
 FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=r) THEN
   EXECUTE 'REVOKE ALL ON moodprint.ai_proactive_schedules FROM ' || quote_ident(r);
  END IF;
 END LOOP;
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='moodprint_runtime') THEN
  GRANT SELECT,INSERT,UPDATE,DELETE ON moodprint.ai_proactive_schedules TO moodprint_runtime;
  CREATE POLICY backend_access ON moodprint.ai_proactive_schedules FOR ALL TO moodprint_runtime USING (true) WITH CHECK (true);
 END IF;
END $acl$;

ALTER TABLE moodprint.ai_proactive_jobs ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON moodprint.ai_proactive_jobs FROM PUBLIC;

DO $acl$
DECLARE r text;
BEGIN
 FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=r) THEN
   EXECUTE 'REVOKE ALL ON moodprint.ai_proactive_jobs FROM ' || quote_ident(r);
  END IF;
 END LOOP;
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='moodprint_runtime') THEN
  GRANT SELECT,INSERT,UPDATE,DELETE ON moodprint.ai_proactive_jobs TO moodprint_runtime;
  CREATE POLICY backend_access ON moodprint.ai_proactive_jobs FOR ALL TO moodprint_runtime USING (true) WITH CHECK (true);
 END IF;
END $acl$;

ALTER TABLE moodprint.ai_conversation_reads ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON moodprint.ai_conversation_reads FROM PUBLIC;

DO $acl$
DECLARE r text;
BEGIN
 FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=r) THEN
   EXECUTE 'REVOKE ALL ON moodprint.ai_conversation_reads FROM ' || quote_ident(r);
  END IF;
 END LOOP;
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='moodprint_runtime') THEN
  GRANT SELECT,INSERT,UPDATE,DELETE ON moodprint.ai_conversation_reads TO moodprint_runtime;
  CREATE POLICY backend_access ON moodprint.ai_conversation_reads FOR ALL TO moodprint_runtime USING (true) WITH CHECK (true);
 END IF;
END $acl$;

ALTER TABLE moodprint.ai_message_sources ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON moodprint.ai_message_sources FROM PUBLIC;

DO $acl$
DECLARE r text;
BEGIN
 FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=r) THEN
   EXECUTE 'REVOKE ALL ON moodprint.ai_message_sources FROM ' || quote_ident(r);
  END IF;
 END LOOP;
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='moodprint_runtime') THEN
  GRANT SELECT,INSERT,UPDATE,DELETE ON moodprint.ai_message_sources TO moodprint_runtime;
  CREATE POLICY backend_access ON moodprint.ai_message_sources FOR ALL TO moodprint_runtime USING (true) WITH CHECK (true);
 END IF;
END $acl$;

UPDATE moodprint.alembic_version SET version_num='0022_proactive_messages' WHERE moodprint.alembic_version.version_num = '0021_multi_message';

COMMIT;

