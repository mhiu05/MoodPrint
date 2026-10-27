BEGIN;

-- Running upgrade 0009_memory_embeddings -> 0010_account_deletion

CREATE OR REPLACE FUNCTION moodprint.delete_provider_identity(app_user_id uuid)
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
$$;

REVOKE ALL ON FUNCTION moodprint.delete_provider_identity(uuid) FROM PUBLIC;

DO $acl$
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
END $acl$;

UPDATE moodprint.alembic_version SET version_num='0010_account_deletion' WHERE moodprint.alembic_version.version_num = '0009_memory_embeddings';

COMMIT;

