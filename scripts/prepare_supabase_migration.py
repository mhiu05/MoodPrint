"""Generate review-only SQL offline. This script never connects to a database."""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Review SQL goes straight into the pinned directory, so it must be added to MANIFEST.json
# (and re-approved) before scripts/check_reviewed_artifacts.py accepts it.
REVIEWED_SQL = ROOT / "deploy/supabase/reviewed-sql"
REPORTS = ROOT / "deploy/supabase/reports"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--auth-rls",
        action="store_true",
        help="Generate a separately reviewed private Auth-session function variant",
    )
    args = parser.parse_args()
    env = {
        **os.environ,
        "DATABASE_URL": "postgresql+psycopg://localhost/moodprint_review_test",
        "DATABASE_MIGRATION_URL": "",
        "AI_ENABLED": "false",
        "STT_ENABLED": "false",
    }
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head", "--sql"],
        cwd=ROOT / "backend",
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    migration = result.stdout
    tables = re.findall(r"CREATE TABLE moodprint\.([a-z_]+)", migration)
    if len(tables) != 24 or re.search(r"\b(DROP|TRUNCATE)\b", migration, re.I):
        raise RuntimeError("Migration scope changed; review the generator before proceeding")
    if re.search(r"(?:CREATE|ALTER)\s+(?:TABLE|SCHEMA)\s+(?!moodprint[.\s])", migration, re.I):
        raise RuntimeError("Migration must touch only moodprint schema")
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "supabase-migrations-0001-0005.sql").write_text(migration, encoding="utf-8")
    prelude = """-- REVIEW ONLY. Target: roznanxbiyqybjpvtilq. Explicit user approval required.
-- Generated offline; not executed remotely. Application login stays disabled.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';
DO $$ BEGIN
  IF current_database() <> 'postgres' OR current_user <> 'postgres' THEN
    RAISE EXCEPTION 'Expected reviewed migration database and owner';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'moodprint') THEN
    RAISE EXCEPTION 'moodprint already exists: inspect drift before applying';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname IN ('moodprint_runtime', 'moodprint_app')) THEN
    RAISE EXCEPTION 'Application roles already exist: review privileges first';
  END IF;
END $$;
CREATE SCHEMA moodprint AUTHORIZATION postgres;
"""
    # Keep the entire initialization, ACLs, policies and revision in one transaction.
    body = re.sub(r"^BEGIN;\s*|^COMMIT;\s*", "", migration, flags=re.M)
    security = """
CREATE ROLE moodprint_runtime NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE ROLE moodprint_app NOLOGIN INHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
GRANT moodprint_runtime TO moodprint_app;
REVOKE ALL ON SCHEMA moodprint FROM PUBLIC, anon, authenticated, service_role;
REVOKE ALL ON ALL TABLES IN SCHEMA moodprint FROM PUBLIC, anon, authenticated, service_role;
GRANT USAGE ON SCHEMA moodprint TO moodprint_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA moodprint TO moodprint_runtime;
REVOKE ALL ON moodprint.alembic_version FROM moodprint_runtime;
GRANT SELECT ON moodprint.alembic_version TO moodprint_runtime;
-- Backend session revocation check needs these two columns only; no Auth DDL/DML.
GRANT USAGE ON SCHEMA auth TO moodprint_runtime;
GRANT SELECT (id, user_id) ON auth.sessions TO moodprint_runtime;
-- No default grants to future tables. Each forward migration must review ACL/RLS.
-- These policies trust the backend role; tenant authorization remains in FastAPI.
"""
    for table in tables:
        security += f"ALTER TABLE moodprint.{table} ENABLE ROW LEVEL SECURITY;\n"
        if table == "alembic_version":
            security += f"CREATE POLICY backend_revision_read ON moodprint.{table} FOR SELECT TO moodprint_runtime USING (true);\n"
        else:
            security += f"CREATE POLICY backend_access ON moodprint.{table} FOR ALL TO moodprint_runtime USING (true) WITH CHECK (true);\n"
    if args.auth_rls:
        security = security.replace(
            "-- Backend session revocation check needs these two columns only; no Auth DDL/DML.",
            "-- Runtime has no raw Auth privileges; the private boolean helper checks app-session ownership.",
        )
        security = security.replace(
            "GRANT USAGE ON SCHEMA auth TO moodprint_runtime;\n", ""
        ).replace("GRANT SELECT (id, user_id) ON auth.sessions TO moodprint_runtime;\n", "")
        security += (ROOT / "backend/app/infrastructure/database/provider_session.sql").read_text(
            encoding="utf-8"
        )
        security += "\nREVOKE ALL ON FUNCTION moodprint.is_provider_session_active(uuid,uuid) FROM anon, authenticated, service_role;\n"
        security += "GRANT EXECUTE ON FUNCTION moodprint.is_provider_session_active(uuid,uuid) TO moodprint_runtime;\n"
    sql = prelude + body + security + "COMMIT;\n"
    path = REVIEWED_SQL / (
        "supabase-initialization-auth-review.sql"
        if args.auth_rls
        else "supabase-initialization-review.sql"
    )
    path.write_text(sql, encoding="utf-8")
    print(
        json.dumps(
            {
                "reviewSql": path.relative_to(ROOT).as_posix(),
                "networkAccessPerformed": False,
                "tablesIncludingHistory": len(tables),
                "rolesCreatedDisabled": 2,
                "authSchemaDdl": False,
                "authDataWrites": False,
                "remoteExecuted": False,
            }
        )
    )


if __name__ == "__main__":
    main()
