BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';
DO $$ BEGIN
 IF (SELECT version_num FROM moodprint.alembic_version) IS DISTINCT FROM '0024_three_agent_groups' THEN
  RAISE EXCEPTION 'Unexpected migration base';
 END IF;
END $$;


-- Running upgrade 0024_three_agent_groups -> 0025_search_citations

ALTER TABLE moodprint.ai_messages ADD COLUMN citations JSONB DEFAULT '[]'::jsonb NOT NULL;

ALTER TABLE moodprint.ai_messages ADD COLUMN source_backed BOOLEAN DEFAULT false NOT NULL;

ALTER TABLE moodprint.ai_messages ADD CONSTRAINT ck_ai_messages_citations CHECK (jsonb_typeof(citations) = 'array' and jsonb_array_length(citations) <= 8 and octet_length(citations::text) <= 24000);

UPDATE moodprint.alembic_version SET version_num='0025_search_citations' WHERE moodprint.alembic_version.version_num = '0024_three_agent_groups';

-- Running upgrade 0025_search_citations -> 0026_search_usage

CREATE TABLE moodprint.ai_search_usage (
        id uuid PRIMARY KEY,
        user_id uuid REFERENCES moodprint.users(id) ON DELETE SET NULL,
        parent_run_id uuid REFERENCES moodprint.ai_runs(id) ON DELETE SET NULL,
        child_run_id uuid REFERENCES moodprint.ai_runs(id) ON DELETE SET NULL,
        provider varchar(16) NOT NULL,
        ordinal integer NOT NULL,
        state varchar(16) NOT NULL,
        active boolean NOT NULL,
        reservation_nano_usd bigint NOT NULL,
        actual_nano_usd bigint,
        token_liability_nano_usd bigint NOT NULL,
        tokens_uncertain boolean NOT NULL,
        pricing_version varchar(100) NOT NULL,
        call_count integer NOT NULL,
        item_count integer NOT NULL,
        created_at timestamptz NOT NULL,
        updated_at timestamptz NOT NULL,
        CONSTRAINT uq_ai_search_usage_parent_run_id UNIQUE(parent_run_id, provider, ordinal),
        CONSTRAINT ck_ai_search_usage_provider CHECK(provider in ('openai_web','apify')),
        CONSTRAINT ck_ai_search_usage_state CHECK(state in ('reserved','dispatched','settled','uncertain')),
        CONSTRAINT ck_ai_search_usage_settlement CHECK((state = 'settled') = (actual_nano_usd is not null)),
        CONSTRAINT ck_ai_search_usage_money CHECK(reservation_nano_usd >= 0 and
            (actual_nano_usd is null or actual_nano_usd >= 0) and token_liability_nano_usd >= 0),
        CONSTRAINT ck_ai_search_usage_counts CHECK(ordinal = 1 and call_count between 0 and 1 and item_count between 0 and 5)
    );

CREATE INDEX ix_ai_search_usage_user_id ON moodprint.ai_search_usage(user_id);

CREATE INDEX ix_ai_search_usage_parent_run_id ON moodprint.ai_search_usage(parent_run_id);

CREATE INDEX ix_ai_search_usage_child_run_id ON moodprint.ai_search_usage(child_run_id);

CREATE INDEX ix_ai_search_usage_active ON moodprint.ai_search_usage(active, created_at);

ALTER TABLE moodprint.ai_search_usage ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON moodprint.ai_search_usage FROM PUBLIC;

DO $$ DECLARE r text; BEGIN
        FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
            IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=r) THEN
                EXECUTE 'REVOKE ALL ON moodprint.ai_search_usage FROM ' || quote_ident(r);
            END IF;
        END LOOP;
        IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='moodprint_runtime') THEN
            GRANT SELECT,INSERT,UPDATE,DELETE ON moodprint.ai_search_usage TO moodprint_runtime;
            CREATE POLICY backend_access ON moodprint.ai_search_usage TO moodprint_runtime USING(true) WITH CHECK(true);
        END IF;
    END $$;

UPDATE moodprint.alembic_version SET version_num='0026_search_usage' WHERE moodprint.alembic_version.version_num = '0025_search_citations';

-- Running upgrade 0026_search_usage -> 0027_maps_jobs

CREATE TABLE moodprint.ai_maps_searches (
        id uuid PRIMARY KEY,
        user_id uuid REFERENCES moodprint.users(id) ON DELETE SET NULL,
        parent_run_id uuid REFERENCES moodprint.ai_runs(id) ON DELETE SET NULL,
        operation_id uuid NOT NULL REFERENCES moodprint.ai_search_usage(id),
        scope_id uuid, conversation_id uuid, session_id uuid,
        auth_version integer NOT NULL, data_version integer NOT NULL,
        status varchar(16) NOT NULL, version integer NOT NULL, provider_ref jsonb,
        cancel_requested boolean NOT NULL, cleanup_done boolean NOT NULL,
        deadline timestamptz NOT NULL, expires_at timestamptz NOT NULL,
        next_poll_at timestamptz NOT NULL, lease_until timestamptz, fence uuid,
        attempts integer NOT NULL, created_at timestamptz NOT NULL,
        CONSTRAINT uq_ai_maps_searches_operation_id UNIQUE (operation_id),
        CONSTRAINT ck_ai_maps_searches_status CHECK(status in ('starting','pending','ready','empty','failed','timed_out','cancelled','expired')),
        CONSTRAINT ck_ai_maps_searches_version CHECK(version >= 1 and attempts >= 0)
    );

CREATE INDEX ix_ai_maps_searches_user_id ON moodprint.ai_maps_searches(user_id);

CREATE INDEX ix_ai_maps_searches_parent_run_id ON moodprint.ai_maps_searches(parent_run_id);

CREATE INDEX ix_ai_maps_searches_next_poll_at ON moodprint.ai_maps_searches(next_poll_at);

CREATE INDEX ix_ai_maps_searches_lease_until ON moodprint.ai_maps_searches(lease_until);

ALTER TABLE moodprint.ai_maps_searches ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON moodprint.ai_maps_searches FROM PUBLIC;

DO $$ DECLARE r text; BEGIN
        FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
            IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=r) THEN
                EXECUTE 'REVOKE ALL ON moodprint.ai_maps_searches FROM ' || quote_ident(r);
            END IF;
        END LOOP;
        IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='moodprint_runtime') THEN
            GRANT SELECT,INSERT,UPDATE,DELETE ON moodprint.ai_maps_searches TO moodprint_runtime;
            CREATE POLICY backend_access ON moodprint.ai_maps_searches TO moodprint_runtime USING(true) WITH CHECK(true);
        END IF;
    END $$;

UPDATE moodprint.alembic_version SET version_num='0027_maps_jobs' WHERE moodprint.alembic_version.version_num = '0026_search_usage';

-- Running upgrade 0027_maps_jobs -> 0028_collaboration_defaults

ALTER TABLE moodprint.ai_collaborations ADD COLUMN permission_policy VARCHAR(32) DEFAULT 'sharing-v1' NOT NULL;

ALTER TABLE moodprint.ai_orchestration_steps ADD COLUMN permission_policy VARCHAR(32) DEFAULT 'sharing-v1' NOT NULL;

UPDATE moodprint.alembic_version SET version_num='0028_collaboration_defaults' WHERE moodprint.alembic_version.version_num = '0027_maps_jobs';

COMMIT;

