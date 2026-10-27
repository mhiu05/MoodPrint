"""Guest-aware provider-session helper: fresh database time and verified anonymous agreement.

Expand only. ``moodprint.is_provider_session_active(uuid,uuid)`` keeps its signature and private
grants but becomes VOLATILE and reads ``clock_timestamp()``, so a deadline is honoured inside a
single long statement too. A registered session still requires a permanent provider identity;
a guest session requires an anonymous one and ``clock < guest_expires_at``. Later guest helpers
(identity deletion, orphan lookup) extend this revision while it is unshipped.
"""

from alembic import op

revision = "0017_guest_security"
down_revision = "0016_guest_foundation"
branch_labels = None
depends_on = None

HELPER = "moodprint.is_provider_session_active(uuid,uuid)"
DELETE_GUEST_HELPER = "moodprint.delete_guest_provider_identity(uuid)"
FIND_ORPHAN_HELPER = "moodprint.find_guest_orphan_subjects(uuid)"
DELETE_ORPHAN_HELPER = "moodprint.delete_orphan_guest_identity(uuid)"

HELPER_SQL = """CREATE OR REPLACE FUNCTION moodprint.is_provider_session_active(app_session_id uuid, app_user_id uuid)
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
$$"""


DELETE_GUEST_SQL = """CREATE OR REPLACE FUNCTION moodprint.delete_guest_provider_identity(app_user_id uuid)
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
$$"""


# Narrow Auth bridges for an attempt whose provider signup may have created an identity the app
# never mapped. Only the stored random marker is looked up; the marker, window and all guards are
# repeated before any delete, and a multiple or unexpected match is an incident, never a cleanup.
FIND_ORPHAN_SQL = """CREATE OR REPLACE FUNCTION moodprint.find_guest_orphan_subjects(attempt_id uuid)
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
$$"""

DELETE_ORPHAN_SQL = """CREATE OR REPLACE FUNCTION moodprint.delete_orphan_guest_identity(attempt_id uuid)
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
$$"""


def acl_statements(function: str) -> list[str]:
    return [
        f"REVOKE ALL ON FUNCTION {function} FROM PUBLIC",
        f"""DO $acl$
DECLARE role_name text;
BEGIN
  FOREACH role_name IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=role_name) THEN
      EXECUTE 'REVOKE ALL ON FUNCTION {function} FROM ' || quote_ident(role_name);
    END IF;
  END LOOP;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='moodprint_runtime') THEN
    GRANT EXECUTE ON FUNCTION {function} TO moodprint_runtime;
  END IF;
END $acl$""",
    ]


def upgrade():
    op.execute(HELPER_SQL)
    for statement in acl_statements(HELPER):
        op.execute(statement)
    op.execute(DELETE_GUEST_SQL)
    for statement in acl_statements(DELETE_GUEST_HELPER):
        op.execute(statement)
    for sql, function in (
        (FIND_ORPHAN_SQL, FIND_ORPHAN_HELPER),
        (DELETE_ORPHAN_SQL, DELETE_ORPHAN_HELPER),
    ):
        op.execute(sql)
        for statement in acl_statements(function):
            op.execute(statement)


def downgrade():
    raise RuntimeError(
        "Destructive rollback disabled; the guest-aware helper must stay while guests may exist"
    )
