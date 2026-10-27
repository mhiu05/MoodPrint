BEGIN;

-- Running upgrade 0005_export_scope -> 0006_ai_usage

CREATE TABLE moodprint.ai_usage (
    run_id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    worker_id UUID NOT NULL, 
    model VARCHAR(100) NOT NULL, 
    prompt_version VARCHAR(60) NOT NULL, 
    pricing_version VARCHAR(60) NOT NULL, 
    input_nano_rate BIGINT, 
    cached_nano_rate BIGINT, 
    output_nano_rate BIGINT, 
    estimated_nano_usd BIGINT, 
    state VARCHAR(16) NOT NULL, 
    sequence INTEGER NOT NULL, 
    requests_started INTEGER NOT NULL, 
    responses_received INTEGER NOT NULL, 
    input_tokens BIGINT NOT NULL, 
    cached_input_tokens BIGINT NOT NULL, 
    output_tokens BIGINT NOT NULL, 
    tool_calls INTEGER NOT NULL, 
    lease_until TIMESTAMP WITH TIME ZONE NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_ai_usage PRIMARY KEY (run_id), 
    CONSTRAINT ck_ai_usage_state CHECK (state in ('open','settled','uncertain')), 
    CONSTRAINT ck_ai_usage_counts CHECK (sequence >= 0 and requests_started >= responses_received and responses_received >= 0 and requests_started <= 3 and tool_calls between 0 and 2), 
    CONSTRAINT ck_ai_usage_tokens CHECK (input_tokens >= cached_input_tokens and cached_input_tokens >= 0 and output_tokens >= 0), 
    CONSTRAINT ck_ai_usage_cost CHECK (estimated_nano_usd is null or estimated_nano_usd >= 0), 
    CONSTRAINT fk_ai_usage_run_id_ai_runs FOREIGN KEY(run_id) REFERENCES moodprint.ai_runs (id) ON DELETE CASCADE, 
    CONSTRAINT fk_ai_usage_user_id_users FOREIGN KEY(user_id) REFERENCES moodprint.users (id)
);

CREATE INDEX ix_ai_usage_user_id ON moodprint.ai_usage (user_id);

CREATE INDEX ix_ai_usage_lease_until ON moodprint.ai_usage (lease_until);

ALTER TABLE moodprint.ai_usage ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON moodprint.ai_usage FROM PUBLIC;

DO $acl$
DECLARE role_name text;
BEGIN
  FOREACH role_name IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=role_name) THEN
      EXECUTE 'REVOKE ALL ON moodprint.ai_usage FROM ' || quote_ident(role_name);
    END IF;
  END LOOP;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='moodprint_runtime') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE ON moodprint.ai_usage TO moodprint_runtime;
    CREATE POLICY backend_access ON moodprint.ai_usage FOR ALL TO moodprint_runtime USING (true) WITH CHECK (true);
  END IF;
END $acl$;

UPDATE moodprint.alembic_version SET version_num='0006_ai_usage' WHERE moodprint.alembic_version.version_num = '0005_export_scope';

-- Running upgrade 0006_ai_usage -> 0007_chat_history

CREATE TABLE moodprint.ai_preferences (
    user_id UUID NOT NULL, 
    history_enabled BOOLEAN NOT NULL, 
    semantic_memory_enabled BOOLEAN NOT NULL, 
    version INTEGER NOT NULL, 
    policy_version VARCHAR(32) NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_ai_preferences PRIMARY KEY (user_id), 
    CONSTRAINT fk_ai_preferences_user_id_users FOREIGN KEY(user_id) REFERENCES moodprint.users (id) ON DELETE CASCADE
);

CREATE TABLE moodprint.ai_conversations (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    bot_id VARCHAR(16) NOT NULL, 
    title VARCHAR(100) NOT NULL, 
    version INTEGER NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_ai_conversations PRIMARY KEY (id), 
    CONSTRAINT ck_ai_conversations_bot CHECK (bot_id in ('may','guong','nhip','rure','caunoi')), 
    CONSTRAINT ck_ai_conversations_version CHECK (version >= 1), 
    CONSTRAINT fk_ai_conversations_user_id_users FOREIGN KEY(user_id) REFERENCES moodprint.users (id) ON DELETE CASCADE
);

CREATE INDEX ix_ai_conversations_owner_activity ON moodprint.ai_conversations (user_id, updated_at, id);

CREATE INDEX ix_ai_conversations_expiry ON moodprint.ai_conversations (expires_at);

CREATE TABLE moodprint.ai_messages (
    id UUID NOT NULL, 
    conversation_id UUID NOT NULL, 
    sequence INTEGER NOT NULL, 
    actor VARCHAR(8) NOT NULL, 
    text VARCHAR(6000) NOT NULL, 
    cards JSONB NOT NULL, 
    run_id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_ai_messages PRIMARY KEY (id), 
    CONSTRAINT uq_ai_messages_conversation_id UNIQUE (conversation_id, sequence), 
    CONSTRAINT uq_ai_messages_run_id UNIQUE (run_id, actor), 
    CONSTRAINT ck_ai_messages_actor CHECK (actor in ('self','bot')), 
    CONSTRAINT ck_ai_messages_sequence CHECK (sequence >= 1), 
    CONSTRAINT fk_ai_messages_conversation_id_ai_conversations FOREIGN KEY(conversation_id) REFERENCES moodprint.ai_conversations (id) ON DELETE CASCADE, 
    CONSTRAINT fk_ai_messages_run_id_ai_runs FOREIGN KEY(run_id) REFERENCES moodprint.ai_runs (id) ON DELETE CASCADE
);

CREATE INDEX ix_ai_messages_run_id ON moodprint.ai_messages (run_id);

CREATE TABLE moodprint.ai_turns (
    run_id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    scope_id UUID NOT NULL, 
    conversation_id UUID, 
    session_id UUID NOT NULL, 
    client_message_id UUID NOT NULL, 
    input_digest VARCHAR(64) NOT NULL, 
    data_version INTEGER NOT NULL, 
    worker_id UUID NOT NULL, 
    lease_until TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_ai_turns PRIMARY KEY (run_id), 
    CONSTRAINT uq_ai_turns_scope_id UNIQUE (scope_id, client_message_id), 
    CONSTRAINT fk_ai_turns_run_id_ai_runs FOREIGN KEY(run_id) REFERENCES moodprint.ai_runs (id) ON DELETE CASCADE, 
    CONSTRAINT fk_ai_turns_user_id_users FOREIGN KEY(user_id) REFERENCES moodprint.users (id) ON DELETE CASCADE, 
    CONSTRAINT fk_ai_turns_conversation_id_ai_conversations FOREIGN KEY(conversation_id) REFERENCES moodprint.ai_conversations (id) ON DELETE CASCADE
);

CREATE INDEX ix_ai_turns_user_id ON moodprint.ai_turns (user_id);

CREATE INDEX ix_ai_turns_conversation_id ON moodprint.ai_turns (conversation_id);

CREATE INDEX ix_ai_turns_lease_until ON moodprint.ai_turns (lease_until);

ALTER TABLE moodprint.ai_preferences ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON moodprint.ai_preferences FROM PUBLIC;

DO $acl$
DECLARE r text;
BEGIN
 FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=r) THEN
   EXECUTE 'REVOKE ALL ON moodprint.ai_preferences FROM ' || quote_ident(r);
  END IF;
 END LOOP;
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='moodprint_runtime') THEN
  GRANT SELECT,INSERT,UPDATE,DELETE ON moodprint.ai_preferences TO moodprint_runtime;
  CREATE POLICY backend_access ON moodprint.ai_preferences FOR ALL TO moodprint_runtime USING (true) WITH CHECK (true);
 END IF;
END $acl$;

ALTER TABLE moodprint.ai_conversations ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON moodprint.ai_conversations FROM PUBLIC;

DO $acl$
DECLARE r text;
BEGIN
 FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=r) THEN
   EXECUTE 'REVOKE ALL ON moodprint.ai_conversations FROM ' || quote_ident(r);
  END IF;
 END LOOP;
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='moodprint_runtime') THEN
  GRANT SELECT,INSERT,UPDATE,DELETE ON moodprint.ai_conversations TO moodprint_runtime;
  CREATE POLICY backend_access ON moodprint.ai_conversations FOR ALL TO moodprint_runtime USING (true) WITH CHECK (true);
 END IF;
END $acl$;

ALTER TABLE moodprint.ai_messages ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON moodprint.ai_messages FROM PUBLIC;

DO $acl$
DECLARE r text;
BEGIN
 FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=r) THEN
   EXECUTE 'REVOKE ALL ON moodprint.ai_messages FROM ' || quote_ident(r);
  END IF;
 END LOOP;
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='moodprint_runtime') THEN
  GRANT SELECT,INSERT,UPDATE,DELETE ON moodprint.ai_messages TO moodprint_runtime;
  CREATE POLICY backend_access ON moodprint.ai_messages FOR ALL TO moodprint_runtime USING (true) WITH CHECK (true);
 END IF;
END $acl$;

ALTER TABLE moodprint.ai_turns ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON moodprint.ai_turns FROM PUBLIC;

DO $acl$
DECLARE r text;
BEGIN
 FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=r) THEN
   EXECUTE 'REVOKE ALL ON moodprint.ai_turns FROM ' || quote_ident(r);
  END IF;
 END LOOP;
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='moodprint_runtime') THEN
  GRANT SELECT,INSERT,UPDATE,DELETE ON moodprint.ai_turns TO moodprint_runtime;
  CREATE POLICY backend_access ON moodprint.ai_turns FOR ALL TO moodprint_runtime USING (true) WITH CHECK (true);
 END IF;
END $acl$;

UPDATE moodprint.alembic_version SET version_num='0007_chat_history' WHERE moodprint.alembic_version.version_num = '0006_ai_usage';

-- Running upgrade 0007_chat_history -> 0008_memory_proposals

CREATE TABLE moodprint.memory_proposals (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    bot_id VARCHAR(16) NOT NULL, 
    text VARCHAR(120) NOT NULL, 
    purpose VARCHAR(16) NOT NULL, 
    data_version INTEGER NOT NULL, 
    ai_consent_version INTEGER NOT NULL, 
    mem_consent_version INTEGER NOT NULL, 
    version INTEGER NOT NULL, 
    status VARCHAR(16) NOT NULL, 
    source_id UUID, 
    source_version INTEGER, 
    decision_digest VARCHAR(64), 
    receipt JSONB, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    decided_at TIMESTAMP WITH TIME ZONE, 
    CONSTRAINT pk_memory_proposals PRIMARY KEY (id), 
    CONSTRAINT ck_memory_proposals_state CHECK (status in ('pending','approved','rejected','expired')), 
    CONSTRAINT ck_memory_proposals_purpose CHECK (purpose in ('memory','private_item')), 
    CONSTRAINT ck_memory_proposals_bot CHECK (bot_id in ('may','guong','nhip','rure')), 
    CONSTRAINT ck_memory_proposals_versions CHECK (version >= 1 and data_version >= 1), 
    CONSTRAINT ck_memory_proposals_text_length CHECK (char_length(text) <= 120), 
    CONSTRAINT ck_memory_proposals_source_pair CHECK ((source_id is null) = (source_version is null)), 
    CONSTRAINT fk_memory_proposals_user_id_users FOREIGN KEY(user_id) REFERENCES moodprint.users (id), 
    CONSTRAINT fk_memory_proposals_source_id_private_items FOREIGN KEY(source_id) REFERENCES moodprint.private_items (id)
);

CREATE INDEX ix_memory_proposals_owner_status ON moodprint.memory_proposals (user_id, status, created_at);

CREATE INDEX ix_memory_proposals_source_id ON moodprint.memory_proposals (source_id);

CREATE INDEX ix_memory_proposals_expires_at ON moodprint.memory_proposals (expires_at);

ALTER TABLE moodprint.memory_proposals ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON moodprint.memory_proposals FROM PUBLIC;

DO $acl$
DECLARE role_name text;
BEGIN
  FOREACH role_name IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=role_name) THEN
      EXECUTE 'REVOKE ALL ON moodprint.memory_proposals FROM ' || quote_ident(role_name);
    END IF;
  END LOOP;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='moodprint_runtime') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE ON moodprint.memory_proposals TO moodprint_runtime;
    CREATE POLICY backend_access ON moodprint.memory_proposals FOR ALL TO moodprint_runtime USING (true) WITH CHECK (true);
  END IF;
END $acl$;

UPDATE moodprint.alembic_version SET version_num='0008_memory_proposals' WHERE moodprint.alembic_version.version_num = '0007_chat_history';

-- Running upgrade 0008_memory_proposals -> 0009_memory_embeddings

CREATE SCHEMA IF NOT EXISTS extensions;

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions;

DO $vector$ BEGIN
      IF NOT EXISTS (SELECT 1 FROM pg_extension e JOIN pg_namespace n ON n.oid=e.extnamespace WHERE e.extname='vector' AND n.nspname='extensions') THEN
        RAISE EXCEPTION 'vector extension must be installed in extensions schema';
      END IF;
    END $vector$;

CREATE TABLE moodprint.memory_embedding_jobs (
    id UUID NOT NULL, 
    memory_id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    bot_id VARCHAR(16) NOT NULL, 
    memory_version INTEGER NOT NULL, 
    data_version INTEGER NOT NULL, 
    preference_version INTEGER NOT NULL, 
    ai_consent_version INTEGER NOT NULL, 
    mem_consent_version INTEGER NOT NULL, 
    model VARCHAR(100) NOT NULL, 
    dimensions INTEGER NOT NULL, 
    status VARCHAR(16) NOT NULL, 
    attempts INTEGER NOT NULL, 
    available_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    lease_until TIMESTAMP WITH TIME ZONE, 
    lease_token UUID, 
    last_error VARCHAR(48), 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_memory_embedding_jobs PRIMARY KEY (id), 
    CONSTRAINT uq_memory_embedding_jobs_snapshot UNIQUE (memory_id, memory_version, preference_version, ai_consent_version, mem_consent_version, model, dimensions), 
    CONSTRAINT ck_memory_embedding_jobs_status CHECK (status in ('pending','running','retry','succeeded','cancelled','failed')), 
    CONSTRAINT ck_memory_embedding_jobs_attempts CHECK (attempts between 0 and 8), 
    CONSTRAINT ck_memory_embedding_jobs_dimensions CHECK (dimensions in (256,512,1024,2048)), 
    CONSTRAINT ck_memory_embedding_jobs_bot CHECK (bot_id in ('may','guong','nhip','rure')), 
    CONSTRAINT fk_memory_embedding_jobs_memory_id_memories FOREIGN KEY(memory_id) REFERENCES moodprint.memories (id) ON DELETE CASCADE, 
    CONSTRAINT fk_memory_embedding_jobs_user_id_users FOREIGN KEY(user_id) REFERENCES moodprint.users (id) ON DELETE CASCADE
);

CREATE INDEX ix_memory_embedding_jobs_due ON moodprint.memory_embedding_jobs (status, available_at, lease_until);

CREATE INDEX ix_memory_embedding_jobs_owner ON moodprint.memory_embedding_jobs (user_id, memory_id);

CREATE TABLE moodprint.memory_embeddings (
    id UUID NOT NULL, 
    memory_id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    bot_id VARCHAR(16) NOT NULL, 
    memory_version INTEGER NOT NULL, 
    data_version INTEGER NOT NULL, 
    preference_version INTEGER NOT NULL, 
    ai_consent_version INTEGER NOT NULL, 
    mem_consent_version INTEGER NOT NULL, 
    model VARCHAR(100) NOT NULL, 
    dimensions INTEGER NOT NULL, 
    embedding extensions.vector NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_memory_embeddings PRIMARY KEY (id), 
    CONSTRAINT uq_memory_embeddings_config UNIQUE (memory_id, model, dimensions), 
    CONSTRAINT ck_memory_embeddings_dimensions CHECK (dimensions in (256,512,1024,2048) and extensions.vector_dims(embedding) = dimensions), 
    CONSTRAINT ck_memory_embeddings_bot CHECK (bot_id in ('may','guong','nhip','rure')), 
    CONSTRAINT fk_memory_embeddings_memory_id_memories FOREIGN KEY(memory_id) REFERENCES moodprint.memories (id) ON DELETE CASCADE, 
    CONSTRAINT fk_memory_embeddings_user_id_users FOREIGN KEY(user_id) REFERENCES moodprint.users (id) ON DELETE CASCADE
);

CREATE INDEX ix_memory_embeddings_scope ON moodprint.memory_embeddings (user_id, bot_id, model, dimensions);

ALTER TABLE moodprint.memory_embedding_jobs ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON moodprint.memory_embedding_jobs FROM PUBLIC;

DO $acl$
DECLARE role_name text;
BEGIN
  FOREACH role_name IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=role_name) THEN
      EXECUTE 'REVOKE ALL ON moodprint.memory_embedding_jobs FROM ' || quote_ident(role_name);
    END IF;
  END LOOP;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='moodprint_runtime') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE ON moodprint.memory_embedding_jobs TO moodprint_runtime;
    CREATE POLICY backend_access ON moodprint.memory_embedding_jobs FOR ALL TO moodprint_runtime USING (true) WITH CHECK (true);
    GRANT USAGE ON SCHEMA extensions TO moodprint_runtime;
  END IF;
END $acl$;

ALTER TABLE moodprint.memory_embeddings ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON moodprint.memory_embeddings FROM PUBLIC;

DO $acl$
DECLARE role_name text;
BEGIN
  FOREACH role_name IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=role_name) THEN
      EXECUTE 'REVOKE ALL ON moodprint.memory_embeddings FROM ' || quote_ident(role_name);
    END IF;
  END LOOP;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='moodprint_runtime') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE ON moodprint.memory_embeddings TO moodprint_runtime;
    CREATE POLICY backend_access ON moodprint.memory_embeddings FOR ALL TO moodprint_runtime USING (true) WITH CHECK (true);
    GRANT USAGE ON SCHEMA extensions TO moodprint_runtime;
  END IF;
END $acl$;

UPDATE moodprint.alembic_version SET version_num='0009_memory_embeddings' WHERE moodprint.alembic_version.version_num = '0008_memory_proposals';

COMMIT;

