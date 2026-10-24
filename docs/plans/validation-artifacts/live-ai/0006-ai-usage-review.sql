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
      EXECUTE format('REVOKE ALL ON moodprint.ai_usage FROM %%I', role_name);
    END IF;
  END LOOP;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='moodprint_runtime') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE ON moodprint.ai_usage TO moodprint_runtime;
    CREATE POLICY backend_access ON moodprint.ai_usage FOR ALL TO moodprint_runtime USING (true) WITH CHECK (true);
  END IF;
END $acl$;

UPDATE moodprint.alembic_version SET version_num='0006_ai_usage' WHERE moodprint.alembic_version.version_num = '0005_export_scope';

COMMIT;

