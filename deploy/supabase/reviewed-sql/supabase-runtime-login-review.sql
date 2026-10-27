-- Additional scope: one dedicated backend LOGIN; the two existing groups stay NOLOGIN.
-- The password placeholder is replaced only by a locally generated SCRAM-SHA-256 verifier.
-- No plaintext password is sent as SQL or printed. No managed Auth changes.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '10s';
CREATE ROLE moodprint_backend LOGIN INHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
  NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 10 PASSWORD {runtime_password};
GRANT moodprint_app TO moodprint_backend;
COMMIT;
