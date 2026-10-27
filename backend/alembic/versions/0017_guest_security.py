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


def downgrade():
    raise RuntimeError(
        "Destructive rollback disabled; the guest-aware helper must stay while guests may exist"
    )
