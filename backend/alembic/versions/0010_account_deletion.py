"""Private helper that removes the Supabase Auth identity of an already-deleted account.

Expand only. The runtime role may call it, but it can only act on an app user whose
status is already 'deleted', so it cannot remove a live account's identity.
"""

from alembic import op

revision = "0010_account_deletion"
down_revision = "0009_memory_embeddings"
branch_labels = None
depends_on = None

FUNCTION_SQL = """CREATE OR REPLACE FUNCTION moodprint.delete_provider_identity(app_user_id uuid)
RETURNS boolean
LANGUAGE plpgsql
VOLATILE
STRICT
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
  subject uuid;
BEGIN
  SELECT u.auth_subject INTO subject
  FROM moodprint.users AS u
  WHERE u.id = app_user_id AND u.status = 'deleted';
  IF subject IS NULL THEN
    RETURN false;
  END IF;
  -- Auth child rows (identities, sessions, refresh tokens, MFA) cascade from auth.users.
  DELETE FROM auth.users AS a WHERE a.id = subject;
  RETURN true;
END;
$$"""


def upgrade():
    op.execute(FUNCTION_SQL)
    op.execute("REVOKE ALL ON FUNCTION moodprint.delete_provider_identity(uuid) FROM PUBLIC")
    op.execute("""DO $acl$
DECLARE role_name text;
BEGIN
  FOREACH role_name IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=role_name) THEN
      EXECUTE 'REVOKE ALL ON FUNCTION moodprint.delete_provider_identity(uuid) FROM ' || quote_ident(role_name);
    END IF;
  END LOOP;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='moodprint_runtime') THEN
    GRANT EXECUTE ON FUNCTION moodprint.delete_provider_identity(uuid) TO moodprint_runtime;
  END IF;
END $acl$""")


def downgrade():
    raise RuntimeError("Expand-only migration; keep the helper and roll back the app instead")
