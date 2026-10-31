BEGIN;

-- Running upgrade 0022_proactive_messages -> 0023_collaboration

ALTER TABLE moodprint.ai_runs ADD COLUMN parent_run_id UUID;

ALTER TABLE moodprint.ai_runs ADD CONSTRAINT fk_ai_runs_parent_run_id_ai_runs FOREIGN KEY(parent_run_id) REFERENCES moodprint.ai_runs (id) ON DELETE CASCADE;

ALTER TABLE moodprint.ai_runs DROP CONSTRAINT ck_ai_runs_origin;

ALTER TABLE moodprint.ai_runs ADD CONSTRAINT ck_ai_runs_origin CHECK (origin in ('user', 'proactive', 'collaboration'));

ALTER TABLE moodprint.ai_runs ADD CONSTRAINT ck_ai_runs_parent CHECK ((origin = 'collaboration') = (parent_run_id is not null));

CREATE INDEX ix_ai_runs_parent_run_id ON moodprint.ai_runs (parent_run_id) WHERE parent_run_id IS NOT NULL;

CREATE TABLE moodprint.ai_sharing_permissions (
    user_id UUID NOT NULL, 
    edge VARCHAR(48) NOT NULL, 
    enabled BOOLEAN DEFAULT false NOT NULL, 
    version INTEGER DEFAULT 1 NOT NULL, 
    policy_version VARCHAR(32) DEFAULT 'sharing-v1' NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
    CONSTRAINT pk_ai_sharing_permissions PRIMARY KEY (user_id, edge), 
    CONSTRAINT ck_ai_sharing_permissions_edge CHECK (edge in ('nhip_energy_for_rure', 'nhip_habit_for_may', 'rure_activity_for_guong')), 
    CONSTRAINT ck_ai_sharing_permissions_version CHECK (version >= 1), 
    CONSTRAINT ck_ai_sharing_permissions_policy CHECK (policy_version in ('sharing-v1')), 
    CONSTRAINT fk_ai_sharing_permissions_user_id_users FOREIGN KEY(user_id) REFERENCES moodprint.users (id) ON DELETE CASCADE
);

CREATE TABLE moodprint.ai_collaborations (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    primary_run_id UUID NOT NULL, 
    specialist_run_id UUID, 
    edge VARCHAR(48) NOT NULL, 
    rule_id VARCHAR(8) NOT NULL, 
    requester_bot VARCHAR(16) NOT NULL, 
    specialist_bot VARCHAR(16) NOT NULL, 
    status VARCHAR(16) NOT NULL, 
    deny_reason VARCHAR(32), 
    failure_code VARCHAR(32), 
    permission_version INTEGER NOT NULL, 
    data_version INTEGER NOT NULL, 
    input_schema VARCHAR(32) NOT NULL, 
    input_digest VARCHAR(64) NOT NULL, 
    output_digest VARCHAR(64), 
    used_in_reply BOOLEAN DEFAULT false NOT NULL, 
    started_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
    finished_at TIMESTAMP WITH TIME ZONE, 
    CONSTRAINT pk_ai_collaborations PRIMARY KEY (id), 
    CONSTRAINT ck_ai_collaborations_status CHECK (status in ('authorized', 'denied', 'completed', 'failed', 'timeout', 'cancelled', 'discarded')), 
    CONSTRAINT ck_ai_collaborations_edge CHECK ((edge = 'nhip_energy_for_rure' and requester_bot = 'rure' and specialist_bot = 'nhip') or (edge = 'nhip_habit_for_may' and requester_bot = 'may' and specialist_bot = 'nhip') or (edge = 'rure_activity_for_guong' and requester_bot = 'guong' and specialist_bot = 'rure')), 
    CONSTRAINT ck_ai_collaborations_rule CHECK (rule_id in ('R1', 'R2', 'R3', 'R4')), 
    CONSTRAINT ck_ai_collaborations_deny CHECK ((status = 'denied') = (deny_reason is not null)), 
    CONSTRAINT ck_ai_collaborations_deny_reason CHECK (deny_reason is null or deny_reason in ('journal_consent_off', 'no_data', 'daily_cap', 'budget', 'time_budget', 'capacity')), 
    CONSTRAINT ck_ai_collaborations_failure CHECK (failure_code is null or status in ('failed', 'timeout', 'cancelled', 'discarded')), 
    CONSTRAINT ck_ai_collaborations_used CHECK (not used_in_reply or status = 'completed'), 
    CONSTRAINT ck_ai_collaborations_digest CHECK (input_digest ~ '^[0-9a-f]{64}$' and (output_digest is null or output_digest ~ '^[0-9a-f]{64}$')), 
    CONSTRAINT fk_ai_collaborations_user_id_users FOREIGN KEY(user_id) REFERENCES moodprint.users (id) ON DELETE CASCADE, 
    CONSTRAINT fk_ai_collaborations_primary_run_id_ai_runs FOREIGN KEY(primary_run_id) REFERENCES moodprint.ai_runs (id) ON DELETE CASCADE, 
    CONSTRAINT fk_ai_collaborations_specialist_run_id_ai_runs FOREIGN KEY(specialist_run_id) REFERENCES moodprint.ai_runs (id) ON DELETE SET NULL, 
    CONSTRAINT uq_ai_collaborations_primary_run_id UNIQUE (primary_run_id, specialist_bot, edge)
);

CREATE INDEX ix_ai_collaborations_user_started ON moodprint.ai_collaborations (user_id, started_at);

ALTER TABLE moodprint.ai_sharing_permissions ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON moodprint.ai_sharing_permissions FROM PUBLIC;

DO $acl$
DECLARE r text;
BEGIN
 FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=r) THEN
   EXECUTE 'REVOKE ALL ON moodprint.ai_sharing_permissions FROM ' || quote_ident(r);
  END IF;
 END LOOP;
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='moodprint_runtime') THEN
  GRANT SELECT,INSERT,UPDATE,DELETE ON moodprint.ai_sharing_permissions TO moodprint_runtime;
  CREATE POLICY backend_access ON moodprint.ai_sharing_permissions FOR ALL TO moodprint_runtime USING (true) WITH CHECK (true);
 END IF;
END $acl$;

ALTER TABLE moodprint.ai_collaborations ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON moodprint.ai_collaborations FROM PUBLIC;

DO $acl$
DECLARE r text;
BEGIN
 FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=r) THEN
   EXECUTE 'REVOKE ALL ON moodprint.ai_collaborations FROM ' || quote_ident(r);
  END IF;
 END LOOP;
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='moodprint_runtime') THEN
  GRANT SELECT,INSERT,UPDATE,DELETE ON moodprint.ai_collaborations TO moodprint_runtime;
  CREATE POLICY backend_access ON moodprint.ai_collaborations FOR ALL TO moodprint_runtime USING (true) WITH CHECK (true);
 END IF;
END $acl$;

UPDATE moodprint.alembic_version SET version_num='0023_collaboration' WHERE moodprint.alembic_version.version_num = '0022_proactive_messages';

COMMIT;

