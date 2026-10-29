BEGIN;

-- Running upgrade 0015_context_privacy -> 0016_guest_foundation

ALTER TABLE moodprint.users ADD COLUMN account_kind VARCHAR(10) DEFAULT 'registered' NOT NULL;

ALTER TABLE moodprint.users ADD COLUMN guest_started_at TIMESTAMP WITH TIME ZONE;

ALTER TABLE moodprint.users ADD COLUMN guest_expires_at TIMESTAMP WITH TIME ZONE;

ALTER TABLE moodprint.users ADD CONSTRAINT ck_users_account_kind CHECK (account_kind in ('registered','guest'));

ALTER TABLE moodprint.users ADD CONSTRAINT ck_users_guest_lifetime CHECK ((account_kind = 'registered' AND guest_started_at IS NULL AND guest_expires_at IS NULL) OR (account_kind = 'guest' AND guest_started_at IS NOT NULL AND guest_expires_at IS NOT NULL AND guest_expires_at = guest_started_at + interval '7200 seconds'));

CREATE INDEX ix_users_guest_expires_at ON moodprint.users (guest_expires_at) WHERE account_kind = 'guest';

ALTER TABLE moodprint.auth_sessions ADD COLUMN created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL;

ALTER TABLE moodprint.auth_sessions ALTER COLUMN created_at SET DEFAULT clock_timestamp();

CREATE OR REPLACE FUNCTION moodprint.guard_user_lifecycle()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = ''
AS $$
BEGIN
  IF NEW.account_kind IS DISTINCT FROM OLD.account_kind
     OR NEW.guest_started_at IS DISTINCT FROM OLD.guest_started_at
     OR NEW.guest_expires_at IS DISTINCT FROM OLD.guest_expires_at THEN
    RAISE EXCEPTION 'guest lifecycle is immutable' USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER users_lifecycle_immutable
BEFORE UPDATE OF account_kind, guest_started_at, guest_expires_at ON moodprint.users
FOR EACH ROW EXECUTE FUNCTION moodprint.guard_user_lifecycle();

CREATE OR REPLACE FUNCTION moodprint.guard_session_lifetime()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = ''
AS $$
DECLARE
  owner_kind text;
  owner_deadline timestamptz;
BEGIN
  SELECT u.account_kind, u.guest_expires_at INTO owner_kind, owner_deadline
  FROM moodprint.users AS u WHERE u.id = NEW.user_id;
  IF owner_kind = 'guest' AND NEW.expires_at > owner_deadline THEN
    RAISE EXCEPTION 'guest session cannot outlive the trial' USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER auth_sessions_lifetime_cap
BEFORE INSERT OR UPDATE OF expires_at, user_id ON moodprint.auth_sessions
FOR EACH ROW EXECUTE FUNCTION moodprint.guard_session_lifetime();

REVOKE ALL ON FUNCTION moodprint.guard_user_lifecycle() FROM PUBLIC;

DO $acl$
DECLARE r text;
BEGIN
 FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=r) THEN
   EXECUTE 'REVOKE ALL ON FUNCTION moodprint.guard_user_lifecycle() FROM ' || quote_ident(r);
  END IF;
 END LOOP;
END $acl$;

REVOKE ALL ON FUNCTION moodprint.guard_session_lifetime() FROM PUBLIC;

DO $acl$
DECLARE r text;
BEGIN
 FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=r) THEN
   EXECUTE 'REVOKE ALL ON FUNCTION moodprint.guard_session_lifetime() FROM ' || quote_ident(r);
  END IF;
 END LOOP;
END $acl$;

CREATE TABLE moodprint.guest_provisioning_attempts (
    id UUID NOT NULL, 
    intent_hash CHAR(64) NOT NULL, 
    idempotency_hash CHAR(64), 
    payload_digest CHAR(64), 
    provider_correlation CHAR(64) NOT NULL, 
    provider_subject UUID, 
    provider_session_id UUID, 
    user_id UUID, 
    state VARCHAR(24) DEFAULT 'intent' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
    intent_expires_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() + interval '600 seconds' NOT NULL, 
    signup_started_at TIMESTAMP WITH TIME ZONE, 
    reconcile_until TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() + interval '600 seconds' NOT NULL, 
    lease_token UUID, 
    lease_until TIMESTAMP WITH TIME ZONE, 
    attempts INTEGER DEFAULT '0' NOT NULL, 
    next_attempt_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
    last_error VARCHAR(40), 
    CONSTRAINT pk_guest_provisioning_attempts PRIMARY KEY (id), 
    CONSTRAINT fk_guest_provisioning_attempts_user_id_users FOREIGN KEY(user_id) REFERENCES moodprint.users (id) ON DELETE SET NULL, 
    CONSTRAINT uq_guest_provisioning_attempts_intent_hash UNIQUE (intent_hash), 
    CONSTRAINT uq_guest_provisioning_attempts_provider_correlation UNIQUE (provider_correlation), 
    CONSTRAINT uq_guest_provisioning_attempts_user_id UNIQUE (user_id), 
    CONSTRAINT ck_guest_provisioning_attempts_state CHECK (state in ('intent','signup_started','granted','ambiguous','orphan_pending','resolved','rejected','incident_required')), 
    CONSTRAINT ck_guest_provisioning_attempts_lease_pair CHECK ((lease_token IS NULL) = (lease_until IS NULL)), 
    CONSTRAINT ck_guest_provisioning_attempts_attempts CHECK (attempts >= 0), 
    CONSTRAINT ck_guest_provisioning_attempts_reconcile_window CHECK (signup_started_at IS NULL OR reconcile_until >= signup_started_at + interval '24 hours')
);

CREATE INDEX ix_guest_provisioning_attempts_state_next ON moodprint.guest_provisioning_attempts (state, next_attempt_at);

CREATE TABLE moodprint.guest_cleanup_jobs (
    user_id UUID NOT NULL, 
    due_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    state VARCHAR(20) DEFAULT 'pending' NOT NULL, 
    attempts INTEGER DEFAULT '0' NOT NULL, 
    next_attempt_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
    lease_token UUID, 
    lease_until TIMESTAMP WITH TIME ZONE, 
    last_error VARCHAR(40), 
    alerted_at TIMESTAMP WITH TIME ZONE, 
    CONSTRAINT pk_guest_cleanup_jobs PRIMARY KEY (user_id), 
    CONSTRAINT fk_guest_cleanup_jobs_user_id_users FOREIGN KEY(user_id) REFERENCES moodprint.users (id) ON DELETE CASCADE, 
    CONSTRAINT ck_guest_cleanup_jobs_state CHECK (state in ('pending','running','retry','incident_required')), 
    CONSTRAINT ck_guest_cleanup_jobs_lease_pair CHECK ((lease_token IS NULL) = (lease_until IS NULL)), 
    CONSTRAINT ck_guest_cleanup_jobs_attempts CHECK (attempts >= 0)
);

CREATE INDEX ix_guest_cleanup_jobs_state_next ON moodprint.guest_cleanup_jobs (state, next_attempt_at);

CREATE TABLE moodprint.guest_usage (
    user_id UUID NOT NULL, 
    ai_turns INTEGER DEFAULT '0' NOT NULL, 
    voice_clips INTEGER DEFAULT '0' NOT NULL, 
    voice_milliseconds BIGINT DEFAULT '0' NOT NULL, 
    semantic_memories INTEGER DEFAULT '0' NOT NULL, 
    CONSTRAINT pk_guest_usage PRIMARY KEY (user_id), 
    CONSTRAINT fk_guest_usage_user_id_users FOREIGN KEY(user_id) REFERENCES moodprint.users (id) ON DELETE CASCADE, 
    CONSTRAINT ck_guest_usage_ai_turns CHECK (ai_turns >= 0), 
    CONSTRAINT ck_guest_usage_voice_clips CHECK (voice_clips >= 0), 
    CONSTRAINT ck_guest_usage_voice_milliseconds CHECK (voice_milliseconds >= 0), 
    CONSTRAINT ck_guest_usage_semantic_memories CHECK (semantic_memories >= 0)
);

CREATE TABLE moodprint.guest_abuse_buckets (
    scope VARCHAR(24) NOT NULL, 
    key_hash CHAR(64) NOT NULL, 
    window_start TIMESTAMP WITH TIME ZONE NOT NULL, 
    count INTEGER DEFAULT '0' NOT NULL, 
    reserved INTEGER DEFAULT '0' NOT NULL, 
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_guest_abuse_buckets PRIMARY KEY (scope, key_hash, window_start), 
    CONSTRAINT ck_guest_abuse_buckets_scope CHECK (scope in ('intent','intent_global','creation_hour','creation_day','failed_signup','feedback','ai_minute','voice_minute')), 
    CONSTRAINT ck_guest_abuse_buckets_count CHECK (count >= 0), 
    CONSTRAINT ck_guest_abuse_buckets_reserved CHECK (reserved >= 0)
);

CREATE INDEX ix_guest_abuse_buckets_expires_at ON moodprint.guest_abuse_buckets (expires_at);

CREATE TABLE moodprint.guest_budget_days (
    day DATE NOT NULL, 
    limit_nano_usd BIGINT NOT NULL, 
    spent_nano_usd BIGINT DEFAULT '0' NOT NULL, 
    reserved_nano_usd BIGINT DEFAULT '0' NOT NULL, 
    halted_at TIMESTAMP WITH TIME ZONE, 
    CONSTRAINT pk_guest_budget_days PRIMARY KEY (day), 
    CONSTRAINT ck_guest_budget_days_limit CHECK (limit_nano_usd > 0), 
    CONSTRAINT ck_guest_budget_days_spent CHECK (spent_nano_usd >= 0), 
    CONSTRAINT ck_guest_budget_days_reserved CHECK (reserved_nano_usd >= 0)
);

CREATE TABLE moodprint.guest_cost_reservations (
    id UUID NOT NULL, 
    day DATE NOT NULL, 
    kind VARCHAR(8) NOT NULL, 
    upper_nano_usd BIGINT NOT NULL, 
    charged_nano_usd BIGINT DEFAULT '0' NOT NULL, 
    state VARCHAR(16) DEFAULT 'reserved' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
    lease_until TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() + interval '60 seconds' NOT NULL, 
    dispatched_at TIMESTAMP WITH TIME ZONE, 
    CONSTRAINT pk_guest_cost_reservations PRIMARY KEY (id), 
    CONSTRAINT fk_guest_cost_reservations_day_guest_budget_days FOREIGN KEY(day) REFERENCES moodprint.guest_budget_days (day) ON DELETE RESTRICT, 
    CONSTRAINT ck_guest_cost_reservations_kind CHECK (kind in ('ai','voice','embed')), 
    CONSTRAINT ck_guest_cost_reservations_state CHECK (state in ('reserved','dispatched','settled','uncertain','cancelled')), 
    CONSTRAINT ck_guest_cost_reservations_upper CHECK (upper_nano_usd >= 0), 
    CONSTRAINT ck_guest_cost_reservations_charged CHECK (charged_nano_usd >= 0)
);

CREATE INDEX ix_guest_cost_reservations_state_lease ON moodprint.guest_cost_reservations (state, lease_until);

CREATE TABLE moodprint.guest_operation_links (
    user_id UUID NOT NULL, 
    kind VARCHAR(8) NOT NULL, 
    operation_key_hash CHAR(64) NOT NULL, 
    payload_digest CHAR(64) NOT NULL, 
    reservation_id UUID, 
    state VARCHAR(16) DEFAULT 'claimed' NOT NULL, 
    worker_id UUID NOT NULL, 
    lease_token UUID NOT NULL, 
    lease_until TIMESTAMP WITH TIME ZONE NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
    CONSTRAINT pk_guest_operation_links PRIMARY KEY (user_id, kind, operation_key_hash), 
    CONSTRAINT fk_guest_operation_links_user_id_users FOREIGN KEY(user_id) REFERENCES moodprint.users (id) ON DELETE CASCADE, 
    CONSTRAINT fk_guest_operation_links_reservation_id_guest_cost_reservations FOREIGN KEY(reservation_id) REFERENCES moodprint.guest_cost_reservations (id) ON DELETE RESTRICT, 
    CONSTRAINT uq_guest_operation_links_reservation_id UNIQUE (reservation_id), 
    CONSTRAINT ck_guest_operation_links_kind CHECK (kind in ('ai','voice','embed')), 
    CONSTRAINT ck_guest_operation_links_state CHECK (state in ('claimed','dispatched','completed','interrupted')), 
    CONSTRAINT ck_guest_operation_links_dispatched CHECK (state <> 'dispatched' OR reservation_id IS NOT NULL)
);

CREATE INDEX ix_guest_operation_links_kind_state_lease ON moodprint.guest_operation_links (kind, state, lease_until);

ALTER TABLE moodprint.guest_provisioning_attempts ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON moodprint.guest_provisioning_attempts FROM PUBLIC;

DO $acl$
DECLARE r text;
BEGIN
 FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=r) THEN
   EXECUTE 'REVOKE ALL ON moodprint.guest_provisioning_attempts FROM ' || quote_ident(r);
  END IF;
 END LOOP;
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='moodprint_runtime') THEN
  GRANT SELECT,INSERT,UPDATE,DELETE ON moodprint.guest_provisioning_attempts TO moodprint_runtime;
  CREATE POLICY backend_access ON moodprint.guest_provisioning_attempts FOR ALL TO moodprint_runtime USING (true) WITH CHECK (true);
 END IF;
END $acl$;

ALTER TABLE moodprint.guest_cleanup_jobs ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON moodprint.guest_cleanup_jobs FROM PUBLIC;

DO $acl$
DECLARE r text;
BEGIN
 FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=r) THEN
   EXECUTE 'REVOKE ALL ON moodprint.guest_cleanup_jobs FROM ' || quote_ident(r);
  END IF;
 END LOOP;
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='moodprint_runtime') THEN
  GRANT SELECT,INSERT,UPDATE,DELETE ON moodprint.guest_cleanup_jobs TO moodprint_runtime;
  CREATE POLICY backend_access ON moodprint.guest_cleanup_jobs FOR ALL TO moodprint_runtime USING (true) WITH CHECK (true);
 END IF;
END $acl$;

ALTER TABLE moodprint.guest_usage ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON moodprint.guest_usage FROM PUBLIC;

DO $acl$
DECLARE r text;
BEGIN
 FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=r) THEN
   EXECUTE 'REVOKE ALL ON moodprint.guest_usage FROM ' || quote_ident(r);
  END IF;
 END LOOP;
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='moodprint_runtime') THEN
  GRANT SELECT,INSERT,UPDATE,DELETE ON moodprint.guest_usage TO moodprint_runtime;
  CREATE POLICY backend_access ON moodprint.guest_usage FOR ALL TO moodprint_runtime USING (true) WITH CHECK (true);
 END IF;
END $acl$;

ALTER TABLE moodprint.guest_abuse_buckets ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON moodprint.guest_abuse_buckets FROM PUBLIC;

DO $acl$
DECLARE r text;
BEGIN
 FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=r) THEN
   EXECUTE 'REVOKE ALL ON moodprint.guest_abuse_buckets FROM ' || quote_ident(r);
  END IF;
 END LOOP;
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='moodprint_runtime') THEN
  GRANT SELECT,INSERT,UPDATE,DELETE ON moodprint.guest_abuse_buckets TO moodprint_runtime;
  CREATE POLICY backend_access ON moodprint.guest_abuse_buckets FOR ALL TO moodprint_runtime USING (true) WITH CHECK (true);
 END IF;
END $acl$;

ALTER TABLE moodprint.guest_budget_days ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON moodprint.guest_budget_days FROM PUBLIC;

DO $acl$
DECLARE r text;
BEGIN
 FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=r) THEN
   EXECUTE 'REVOKE ALL ON moodprint.guest_budget_days FROM ' || quote_ident(r);
  END IF;
 END LOOP;
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='moodprint_runtime') THEN
  GRANT SELECT,INSERT,UPDATE,DELETE ON moodprint.guest_budget_days TO moodprint_runtime;
  CREATE POLICY backend_access ON moodprint.guest_budget_days FOR ALL TO moodprint_runtime USING (true) WITH CHECK (true);
 END IF;
END $acl$;

ALTER TABLE moodprint.guest_cost_reservations ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON moodprint.guest_cost_reservations FROM PUBLIC;

DO $acl$
DECLARE r text;
BEGIN
 FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=r) THEN
   EXECUTE 'REVOKE ALL ON moodprint.guest_cost_reservations FROM ' || quote_ident(r);
  END IF;
 END LOOP;
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='moodprint_runtime') THEN
  GRANT SELECT,INSERT,UPDATE,DELETE ON moodprint.guest_cost_reservations TO moodprint_runtime;
  CREATE POLICY backend_access ON moodprint.guest_cost_reservations FOR ALL TO moodprint_runtime USING (true) WITH CHECK (true);
 END IF;
END $acl$;

ALTER TABLE moodprint.guest_operation_links ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON moodprint.guest_operation_links FROM PUBLIC;

DO $acl$
DECLARE r text;
BEGIN
 FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=r) THEN
   EXECUTE 'REVOKE ALL ON moodprint.guest_operation_links FROM ' || quote_ident(r);
  END IF;
 END LOOP;
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='moodprint_runtime') THEN
  GRANT SELECT,INSERT,UPDATE,DELETE ON moodprint.guest_operation_links TO moodprint_runtime;
  CREATE POLICY backend_access ON moodprint.guest_operation_links FOR ALL TO moodprint_runtime USING (true) WITH CHECK (true);
 END IF;
END $acl$;

UPDATE moodprint.alembic_version SET version_num='0016_guest_foundation' WHERE moodprint.alembic_version.version_num = '0015_context_privacy';

-- Running upgrade 0016_guest_foundation -> 0017_guest_security

CREATE OR REPLACE FUNCTION moodprint.is_provider_session_active(app_session_id uuid, app_user_id uuid)
RETURNS boolean
LANGUAGE plpgsql
VOLATILE
STRICT
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
  checked_at timestamptz := pg_catalog.clock_timestamp();
BEGIN
  RETURN EXISTS (
    SELECT 1
    FROM moodprint.auth_sessions AS a
    JOIN moodprint.users AS u ON u.id = a.user_id
    JOIN auth.sessions AS s ON s.id = a.provider_session_id AND s.user_id = u.auth_subject
    JOIN auth.users AS p ON p.id = u.auth_subject
    WHERE a.id = app_session_id
      AND a.user_id = app_user_id
      AND NOT a.revoked
      AND a.expires_at > checked_at
      AND a.auth_version = u.auth_version
      AND u.status = 'active'
      AND (
        (u.account_kind = 'registered' AND p.is_anonymous IS FALSE)
        OR (u.account_kind = 'guest' AND p.is_anonymous IS TRUE AND checked_at < u.guest_expires_at)
      )
  );
END;
$$;

REVOKE ALL ON FUNCTION moodprint.is_provider_session_active(uuid,uuid) FROM PUBLIC;

DO $acl$
DECLARE role_name text;
BEGIN
  FOREACH role_name IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=role_name) THEN
      EXECUTE 'REVOKE ALL ON FUNCTION moodprint.is_provider_session_active(uuid,uuid) FROM ' || quote_ident(role_name);
    END IF;
  END LOOP;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='moodprint_runtime') THEN
    GRANT EXECUTE ON FUNCTION moodprint.is_provider_session_active(uuid,uuid) TO moodprint_runtime;
  END IF;
END $acl$;

CREATE OR REPLACE FUNCTION moodprint.delete_guest_provider_identity(app_user_id uuid)
RETURNS boolean
LANGUAGE plpgsql
VOLATILE
STRICT
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
  subject uuid;
  kind text;
  state text;
  deadline timestamptz;
  provider_anonymous boolean;
  mapped integer;
BEGIN
  SELECT u.auth_subject, u.account_kind, u.status, u.guest_expires_at
    INTO subject, kind, state, deadline
  FROM moodprint.users AS u WHERE u.id = app_user_id FOR UPDATE;
  IF NOT FOUND OR kind <> 'guest' THEN
    RAISE EXCEPTION 'not a guest identity' USING ERRCODE = 'check_violation';
  END IF;
  IF state = 'active' AND pg_catalog.clock_timestamp() < deadline THEN
    RAISE EXCEPTION 'guest trial still active' USING ERRCODE = 'check_violation';
  END IF;
  SELECT pg_catalog.count(*) INTO mapped FROM moodprint.users AS u WHERE u.auth_subject = subject;
  IF mapped <> 1 THEN
    RAISE EXCEPTION 'provider identity is not uniquely mapped' USING ERRCODE = 'check_violation';
  END IF;
  SELECT a.is_anonymous INTO provider_anonymous FROM auth.users AS a WHERE a.id = subject;
  IF NOT FOUND THEN
    RETURN true;
  END IF;
  IF provider_anonymous IS DISTINCT FROM true THEN
    RAISE EXCEPTION 'provider identity is permanent' USING ERRCODE = 'check_violation';
  END IF;
  DELETE FROM auth.users AS a WHERE a.id = subject;
  RETURN NOT EXISTS (SELECT 1 FROM auth.users AS a WHERE a.id = subject);
END;
$$;

REVOKE ALL ON FUNCTION moodprint.delete_guest_provider_identity(uuid) FROM PUBLIC;

DO $acl$
DECLARE role_name text;
BEGIN
  FOREACH role_name IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=role_name) THEN
      EXECUTE 'REVOKE ALL ON FUNCTION moodprint.delete_guest_provider_identity(uuid) FROM ' || quote_ident(role_name);
    END IF;
  END LOOP;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='moodprint_runtime') THEN
    GRANT EXECUTE ON FUNCTION moodprint.delete_guest_provider_identity(uuid) TO moodprint_runtime;
  END IF;
END $acl$;

CREATE OR REPLACE FUNCTION moodprint.find_guest_orphan_subjects(attempt_id uuid)
RETURNS TABLE(subject_id uuid)
LANGUAGE plpgsql
STABLE
STRICT
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
  target RECORD;
BEGIN
  SELECT t.provider_correlation, t.signup_started_at, t.state, t.lease_until INTO target
  FROM moodprint.guest_provisioning_attempts AS t WHERE t.id = attempt_id;
  IF NOT FOUND OR target.signup_started_at IS NULL
     OR target.state NOT IN ('signup_started', 'ambiguous', 'orphan_pending') THEN
    RETURN;
  END IF;
  IF target.state = 'signup_started' AND target.lease_until IS NOT NULL
     AND target.lease_until > pg_catalog.clock_timestamp() THEN
    RETURN;
  END IF;
  RETURN QUERY
  SELECT a.id
  FROM auth.users AS a
  WHERE a.is_anonymous IS TRUE
    AND a.raw_user_meta_data ->> 'moodprint_guest_attempt' = target.provider_correlation
    AND a.created_at BETWEEN target.signup_started_at - interval '5 seconds'
                         AND target.signup_started_at + interval '60 seconds'
    AND NOT EXISTS (SELECT 1 FROM moodprint.users AS u WHERE u.auth_subject = a.id);
END;
$$;

REVOKE ALL ON FUNCTION moodprint.find_guest_orphan_subjects(uuid) FROM PUBLIC;

DO $acl$
DECLARE role_name text;
BEGIN
  FOREACH role_name IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=role_name) THEN
      EXECUTE 'REVOKE ALL ON FUNCTION moodprint.find_guest_orphan_subjects(uuid) FROM ' || quote_ident(role_name);
    END IF;
  END LOOP;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='moodprint_runtime') THEN
    GRANT EXECUTE ON FUNCTION moodprint.find_guest_orphan_subjects(uuid) TO moodprint_runtime;
  END IF;
END $acl$;

CREATE OR REPLACE FUNCTION moodprint.delete_orphan_guest_identity(attempt_id uuid)
RETURNS text
LANGUAGE plpgsql
VOLATILE
STRICT
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
  target RECORD;
  matches uuid[];
BEGIN
  SELECT t.provider_correlation, t.signup_started_at, t.state, t.lease_until INTO target
  FROM moodprint.guest_provisioning_attempts AS t WHERE t.id = attempt_id FOR UPDATE;
  IF NOT FOUND OR target.signup_started_at IS NULL
     OR target.state NOT IN ('signup_started', 'ambiguous', 'orphan_pending') THEN
    RETURN 'not_found';
  END IF;
  IF target.state = 'signup_started' AND target.lease_until IS NOT NULL
     AND target.lease_until > pg_catalog.clock_timestamp() THEN
    RETURN 'not_found';
  END IF;
  SELECT pg_catalog.array_agg(a.id) INTO matches
  FROM auth.users AS a
  WHERE a.is_anonymous IS TRUE
    AND a.raw_user_meta_data ->> 'moodprint_guest_attempt' = target.provider_correlation
    AND a.created_at BETWEEN target.signup_started_at - interval '5 seconds'
                         AND target.signup_started_at + interval '60 seconds'
    AND NOT EXISTS (SELECT 1 FROM moodprint.users AS u WHERE u.auth_subject = a.id);
  IF matches IS NULL THEN
    RETURN 'not_found';
  END IF;
  IF pg_catalog.array_length(matches, 1) <> 1 THEN
    RETURN 'incident_required';
  END IF;
  DELETE FROM auth.users AS a
  WHERE a.id = matches[1] AND a.is_anonymous IS TRUE
    AND NOT EXISTS (SELECT 1 FROM moodprint.users AS u WHERE u.auth_subject = a.id);
  IF NOT FOUND THEN
    RETURN 'incident_required';
  END IF;
  RETURN 'deleted';
END;
$$;

REVOKE ALL ON FUNCTION moodprint.delete_orphan_guest_identity(uuid) FROM PUBLIC;

DO $acl$
DECLARE role_name text;
BEGIN
  FOREACH role_name IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=role_name) THEN
      EXECUTE 'REVOKE ALL ON FUNCTION moodprint.delete_orphan_guest_identity(uuid) FROM ' || quote_ident(role_name);
    END IF;
  END LOOP;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='moodprint_runtime') THEN
    GRANT EXECUTE ON FUNCTION moodprint.delete_orphan_guest_identity(uuid) TO moodprint_runtime;
  END IF;
END $acl$;

UPDATE moodprint.alembic_version SET version_num='0017_guest_security' WHERE moodprint.alembic_version.version_num = '0016_guest_foundation';

-- Running upgrade 0017_guest_security -> 0018_app_feedback

CREATE OR REPLACE FUNCTION moodprint.feedback_categories_valid(items text[])
RETURNS boolean
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
SET search_path = ''
AS $$
SELECT coalesce(
  items IS NOT NULL
  AND coalesce(cardinality(items), 0) <= 8
  AND array_position(items, NULL::text) IS NULL
  AND items <@ ARRAY['ease_of_use','ai_quality','interface','performance','bug','missing_feature','privacy_trust','other']::text[]
  AND coalesce(cardinality(items), 0) = (SELECT count(DISTINCT item) FROM unnest(items) AS item),
  false
)
$$;

REVOKE ALL ON FUNCTION moodprint.feedback_categories_valid(text[]) FROM PUBLIC;

DO $acl$
DECLARE r text;
BEGIN
 FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=r) THEN
   EXECUTE 'REVOKE ALL ON FUNCTION moodprint.feedback_categories_valid(text[]) FROM ' || quote_ident(r);
  END IF;
 END LOOP;
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='moodprint_runtime') THEN
  GRANT EXECUTE ON FUNCTION moodprint.feedback_categories_valid(text[]) TO moodprint_runtime;
 END IF;
END $acl$;

CREATE OR REPLACE FUNCTION moodprint.feedback_comment_valid(value text)
RETURNS boolean
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
SET search_path = ''
AS $$
SELECT value IS NULL OR (
  char_length(value) <= 1000
  AND value !~ '[\u0001-\u0008\u000b\u000c\u000e-\u001f\u007f-\u009f]'
)
$$;

REVOKE ALL ON FUNCTION moodprint.feedback_comment_valid(text) FROM PUBLIC;

DO $acl$
DECLARE r text;
BEGIN
 FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=r) THEN
   EXECUTE 'REVOKE ALL ON FUNCTION moodprint.feedback_comment_valid(text) FROM ' || quote_ident(r);
  END IF;
 END LOOP;
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='moodprint_runtime') THEN
  GRANT EXECUTE ON FUNCTION moodprint.feedback_comment_valid(text) TO moodprint_runtime;
 END IF;
END $acl$;

CREATE TABLE moodprint.app_feedback (
    id UUID NOT NULL, 
    rating SMALLINT NOT NULL, 
    categories TEXT[] DEFAULT '{}'::text[] NOT NULL, 
    comment TEXT, 
    app_version VARCHAR(64) NOT NULL, 
    context VARCHAR(16) DEFAULT 'general' NOT NULL, 
    account_kind VARCHAR(10) NOT NULL, 
    disclosure_version VARCHAR(32) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
    status VARCHAR(12) DEFAULT 'new' NOT NULL, 
    version INTEGER DEFAULT '1' NOT NULL, 
    reviewed_at TIMESTAMP WITH TIME ZONE, 
    CONSTRAINT pk_app_feedback PRIMARY KEY (id), 
    CONSTRAINT ck_app_feedback_rating CHECK (rating between 1 and 5), 
    CONSTRAINT ck_app_feedback_categories CHECK (moodprint.feedback_categories_valid(categories)), 
    CONSTRAINT ck_app_feedback_comment CHECK (moodprint.feedback_comment_valid(comment)), 
    CONSTRAINT ck_app_feedback_context CHECK (context in ('general','assistants','mood','memory','privacy','activities','trial_end')), 
    CONSTRAINT ck_app_feedback_account_kind CHECK (account_kind in ('guest','registered')), 
    CONSTRAINT ck_app_feedback_disclosure_version CHECK (disclosure_version ~ '^feedback-v[0-9]+$'), 
    CONSTRAINT ck_app_feedback_status CHECK (status in ('new','reviewed','planned','resolved','spam')), 
    CONSTRAINT ck_app_feedback_version CHECK (version > 0)
);

CREATE INDEX ix_app_feedback_created_at ON moodprint.app_feedback (created_at, id);

CREATE INDEX ix_app_feedback_status ON moodprint.app_feedback (status, created_at, id);

CREATE TABLE moodprint.feedback_submission_receipts (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    idempotency_key VARCHAR(128) NOT NULL, 
    payload_digest CHAR(64) NOT NULL, 
    feedback_id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
    CONSTRAINT pk_feedback_submission_receipts PRIMARY KEY (id), 
    CONSTRAINT fk_feedback_submission_receipts_user_id_users FOREIGN KEY(user_id) REFERENCES moodprint.users (id) ON DELETE CASCADE, 
    CONSTRAINT fk_feedback_submission_receipts_feedback_id_app_feedback FOREIGN KEY(feedback_id) REFERENCES moodprint.app_feedback (id) ON DELETE CASCADE, 
    CONSTRAINT uq_feedback_submission_receipts_user_id UNIQUE (user_id, idempotency_key)
);

CREATE INDEX ix_feedback_submission_receipts_user_created ON moodprint.feedback_submission_receipts (user_id, created_at);

CREATE INDEX ix_feedback_submission_receipts_feedback_id ON moodprint.feedback_submission_receipts (feedback_id);

CREATE TABLE moodprint.feedback_review_events (
    id UUID NOT NULL, 
    feedback_id UUID NOT NULL, 
    staff_id UUID NOT NULL, 
    action VARCHAR(8) NOT NULL, 
    from_status VARCHAR(12), 
    to_status VARCHAR(12), 
    resulting_version INTEGER NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
    CONSTRAINT pk_feedback_review_events PRIMARY KEY (id), 
    CONSTRAINT fk_feedback_review_events_feedback_id_app_feedback FOREIGN KEY(feedback_id) REFERENCES moodprint.app_feedback (id) ON DELETE CASCADE, 
    CONSTRAINT fk_feedback_review_events_staff_id_users FOREIGN KEY(staff_id) REFERENCES moodprint.users (id) ON DELETE RESTRICT, 
    CONSTRAINT ck_feedback_review_events_action CHECK (action in ('status','redact')), 
    CONSTRAINT ck_feedback_review_events_statuses CHECK ((from_status IS NULL OR from_status in ('new','reviewed','planned','resolved','spam')) AND (to_status IS NULL OR to_status in ('new','reviewed','planned','resolved','spam'))), 
    CONSTRAINT ck_feedback_review_events_status_pair CHECK (action <> 'status' OR (from_status IS NOT NULL AND to_status IS NOT NULL)), 
    CONSTRAINT ck_feedback_review_events_version CHECK (resulting_version > 0)
);

CREATE INDEX ix_feedback_review_events_feedback_created ON moodprint.feedback_review_events (feedback_id, created_at);

CREATE INDEX ix_feedback_review_events_staff_id ON moodprint.feedback_review_events (staff_id);

ALTER TABLE moodprint.guest_abuse_buckets DROP CONSTRAINT ck_guest_abuse_buckets_scope;

ALTER TABLE moodprint.guest_abuse_buckets ADD CONSTRAINT ck_guest_abuse_buckets_scope CHECK (scope in ('intent','intent_global','creation_hour','creation_day','failed_signup','feedback','ai_minute','voice_minute','feedback_attempt'));

ALTER TABLE moodprint.app_feedback ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON moodprint.app_feedback FROM PUBLIC;

DO $acl$
DECLARE r text;
BEGIN
 FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=r) THEN
   EXECUTE 'REVOKE ALL ON moodprint.app_feedback FROM ' || quote_ident(r);
  END IF;
 END LOOP;
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='moodprint_runtime') THEN
  GRANT SELECT,INSERT,UPDATE,DELETE ON moodprint.app_feedback TO moodprint_runtime;
  CREATE POLICY backend_access ON moodprint.app_feedback FOR ALL TO moodprint_runtime USING (true) WITH CHECK (true);
 END IF;
END $acl$;

ALTER TABLE moodprint.feedback_submission_receipts ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON moodprint.feedback_submission_receipts FROM PUBLIC;

DO $acl$
DECLARE r text;
BEGIN
 FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=r) THEN
   EXECUTE 'REVOKE ALL ON moodprint.feedback_submission_receipts FROM ' || quote_ident(r);
  END IF;
 END LOOP;
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='moodprint_runtime') THEN
  GRANT SELECT,INSERT,UPDATE,DELETE ON moodprint.feedback_submission_receipts TO moodprint_runtime;
  CREATE POLICY backend_access ON moodprint.feedback_submission_receipts FOR ALL TO moodprint_runtime USING (true) WITH CHECK (true);
 END IF;
END $acl$;

ALTER TABLE moodprint.feedback_review_events ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON moodprint.feedback_review_events FROM PUBLIC;

DO $acl$
DECLARE r text;
BEGIN
 FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=r) THEN
   EXECUTE 'REVOKE ALL ON moodprint.feedback_review_events FROM ' || quote_ident(r);
  END IF;
 END LOOP;
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='moodprint_runtime') THEN
  GRANT SELECT,INSERT,UPDATE,DELETE ON moodprint.feedback_review_events TO moodprint_runtime;
  CREATE POLICY backend_access ON moodprint.feedback_review_events FOR ALL TO moodprint_runtime USING (true) WITH CHECK (true);
 END IF;
END $acl$;

UPDATE moodprint.alembic_version SET version_num='0018_app_feedback' WHERE moodprint.alembic_version.version_num = '0017_guest_security';

COMMIT;

