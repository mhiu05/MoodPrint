-- Review the target project first. Never apply automatically to a hosted project.
-- Create a LOGIN role separately with a secret supplied by your secret manager.
-- The migration owner and application LOGIN must be different roles.
CREATE ROLE moodprint_runtime NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
GRANT USAGE ON SCHEMA moodprint TO moodprint_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA moodprint TO moodprint_runtime;
REVOKE ALL ON moodprint.alembic_version FROM moodprint_runtime;
GRANT SELECT ON moodprint.alembic_version TO moodprint_runtime;
-- Install the approved private helper first, without granting direct Auth access.
GRANT EXECUTE ON FUNCTION moodprint.is_provider_session_active(uuid,uuid) TO moodprint_runtime;
-- Then GRANT moodprint_runtime TO your_application_login;
-- Do not grant CREATE on moodprint/public, ownership, superuser or BYPASSRLS.
-- Keep moodprint outside the exposed Supabase Data API schemas. Domain reads/writes
-- go through FastAPI authorization. No anon/authenticated grants are required.
