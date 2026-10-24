-- Private backend-only bridge across Supabase-managed Auth RLS; bootstrap security DDL.
-- Runtime callers supply an app session/user pair, never an arbitrary Auth subject.
CREATE FUNCTION moodprint.is_provider_session_active(app_session_id uuid, app_user_id uuid)
RETURNS boolean
LANGUAGE plpgsql
STABLE
STRICT
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN
  RETURN EXISTS (
    SELECT 1
    FROM moodprint.auth_sessions AS a
    JOIN moodprint.users AS u ON u.id = a.user_id
    JOIN auth.sessions AS s ON s.id = a.provider_session_id AND s.user_id = u.auth_subject
    WHERE a.id = app_session_id
      AND a.user_id = app_user_id
      AND NOT a.revoked
      AND a.expires_at > pg_catalog.statement_timestamp()
      AND a.auth_version = u.auth_version
      AND u.status = 'active'
  );
END;
$$;
REVOKE ALL ON FUNCTION moodprint.is_provider_session_active(uuid,uuid) FROM PUBLIC;
