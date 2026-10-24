"""Rehearse the review SQL on an EMPTY local *_test DB; roll all DDL back."""

import argparse
import json
import os
from pathlib import Path
from uuid import uuid4

import psycopg
from apply_supabase_review import catalog_checks
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--auth-rls", action="store_true")
    args = parser.parse_args()
    raw = os.environ["TEST_DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://", 1)
    target = make_url(raw)
    if target.host not in ("localhost", "127.0.0.1", "::1") or not (target.database or "").endswith(
        "_test"
    ):
        raise RuntimeError("Only an explicitly named disposable local *_test DB is allowed")
    report = {"scope": "empty local disposable DB only", "remoteWrites": False}
    with psycopg.connect(raw, autocommit=True) as db:
        if db.execute(
            "select exists(select 1 from pg_namespace where nspname='moodprint')"
        ).fetchone()[0]:
            raise RuntimeError("Use an empty local review DB; existing data will not be reset")
        filename = (
            "supabase-initialization-auth-review.sql"
            if args.auth_rls
            else "supabase-initialization-review.sql"
        )
        sql = (ROOT / "docs/plans/validation-artifacts" / filename).read_text(encoding="utf-8")
        # The reviewed SQL expects hosted database 'postgres'. Only this local copy is adapted.
        sql = sql.replace(
            "current_database() <> 'postgres'",
            "current_database() <> " + "'" + target.database.replace("'", "''") + "'",
        )
        sql = sql.removesuffix("COMMIT;\n")
        sql = sql.replace(
            "BEGIN;",
            """BEGIN;
-- Synthetic Supabase fixtures, only in the guarded local transaction.
DO $$ DECLARE r text; BEGIN
  FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname=r) THEN
      EXECUTE format('CREATE ROLE %I NOLOGIN',r);
    END IF;
  END LOOP;
END $$;
CREATE SCHEMA IF NOT EXISTS auth;
CREATE TABLE IF NOT EXISTS auth.sessions (id uuid primary key, user_id uuid not null, created_at timestamptz);
ALTER TABLE auth.sessions ENABLE ROW LEVEL SECURITY;
""",
            1,
        )
        try:
            db.execute(sql, prepare=False)
            report["revision"] = db.execute(
                "select version_num from moodprint.alembic_version"
            ).fetchone()[0]
            report["tablesWithRls"] = db.execute(
                "select count(*) from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname='moodprint' and c.relkind='r' and c.relrowsecurity"
            ).fetchone()[0]
            report["catalogGroups"] = catalog_checks(db, auth_bridge=args.auth_rls)
            db.execute("SET LOCAL ROLE moodprint_app")
            identity = uuid4()
            db.execute(
                "insert into moodprint.users(id,auth_subject,alias,age_band,status,timezone,auth_version,data_version,profile_version) values (%s,%s,'Synthetic','unknown','active','Asia/Bangkok',1,1,1)",
                (identity, identity),
            )
            db.execute("update moodprint.users set alias='Updated' where id=%s", (identity,))
            report["runtimeDml"] = (
                db.execute("select alias from moodprint.users where id=%s", (identity,)).fetchone()[
                    0
                ]
                == "Updated"
            )
            if args.auth_rls:
                sid, provider_sid = uuid4(), uuid4()
                db.execute(
                    "insert into moodprint.auth_sessions(id,user_id,token_hash,csrf_hash,provider_session_id,expires_at,revoked,auth_version) values (%s,%s,%s,%s,%s,now()+interval '1 hour',false,1)",
                    (sid, identity, "a" * 64, "b" * 64, provider_sid),
                )
                db.execute("SET LOCAL ROLE postgres")
                db.execute(
                    "insert into auth.sessions(id,user_id) values (%s,%s)", (provider_sid, identity)
                )
                # Reproduce the old design with RLS actually enabled: grants still yield no rows.
                db.execute("GRANT USAGE ON SCHEMA auth TO moodprint_runtime")
                db.execute("GRANT SELECT(id,user_id) ON auth.sessions TO moodprint_runtime")
                db.execute("SET LOCAL ROLE moodprint_app")
                report["legacyGrantsCannotSeeAuthRowWithRls"] = (
                    db.execute(
                        "select count(id) from auth.sessions where id=%s", (provider_sid,)
                    ).fetchone()[0]
                    == 0
                )
                db.execute("SET LOCAL ROLE postgres")
                db.execute("REVOKE SELECT(id,user_id) ON auth.sessions FROM moodprint_runtime")
                db.execute("REVOKE USAGE ON SCHEMA auth FROM moodprint_runtime")
                db.execute("SET LOCAL ROLE moodprint_app")
                report["privateAuthBridgeValidSession"] = (
                    db.execute(
                        "select moodprint.is_provider_session_active(%s,%s)", (sid, identity)
                    ).fetchone()[0]
                    is True
                )
                report["privateAuthBridgeOwnerBound"] = (
                    db.execute(
                        "select moodprint.is_provider_session_active(%s,%s)", (sid, uuid4())
                    ).fetchone()[0]
                    is False
                )
                db.execute("update moodprint.auth_sessions set revoked=true where id=%s", (sid,))
                report["privateAuthBridgeLocalRevoke"] = (
                    db.execute(
                        "select moodprint.is_provider_session_active(%s,%s)", (sid, identity)
                    ).fetchone()[0]
                    is False
                )
                db.execute("update moodprint.auth_sessions set revoked=false where id=%s", (sid,))
                db.execute("SET LOCAL ROLE postgres")
                db.execute("delete from auth.sessions where id=%s", (provider_sid,))
                db.execute("SET LOCAL ROLE moodprint_app")
                report["privateAuthBridgeProviderRevoke"] = (
                    db.execute(
                        "select moodprint.is_provider_session_active(%s,%s)", (sid, identity)
                    ).fetchone()[0]
                    is False
                )
                db.execute("delete from moodprint.auth_sessions where id=%s", (sid,))
                report["authAccessVerified"] = all(
                    report[k]
                    for k in (
                        "legacyGrantsCannotSeeAuthRowWithRls",
                        "privateAuthBridgeValidSession",
                        "privateAuthBridgeOwnerBound",
                        "privateAuthBridgeLocalRevoke",
                        "privateAuthBridgeProviderRevoke",
                    )
                )
            else:
                db.execute("select id,user_id from auth.sessions limit 0")
                report["authAccessVerified"] = True
            report["runtimeCreateDenied"] = not db.execute(
                "select has_schema_privilege(current_user,'moodprint','CREATE')"
            ).fetchone()[0]
            for key, statement in {
                "domainDdlDenied": "create table moodprint.not_allowed(id int)",
                "publicDdlDenied": "create table public.not_allowed(id int)",
                "revisionWriteDenied": "update moodprint.alembic_version set version_num=version_num",
                "authExtraColumnsDenied": "select created_at from auth.sessions",
                "authWritesDenied": "update auth.sessions set user_id=user_id",
                **(
                    {"directAuthReadDenied": "select id,user_id from auth.sessions"}
                    if args.auth_rls
                    else {}
                ),
            }.items():
                db.execute("SAVEPOINT denied_operation")
                try:
                    db.execute(statement)
                    report[key] = False
                except psycopg.errors.InsufficientPrivilege:
                    report[key] = True
                finally:
                    db.execute("ROLLBACK TO SAVEPOINT denied_operation")
            db.execute("delete from moodprint.users where id=%s", (identity,))
        finally:
            db.execute("ROLLBACK")
        report["schemaRolledBack"] = not db.execute(
            "select exists(select 1 from pg_namespace where nspname='moodprint')"
        ).fetchone()[0]
        report["rolesRolledBack"] = not db.execute(
            "select exists(select 1 from pg_roles where rolname in ('moodprint_runtime','moodprint_app'))"
        ).fetchone()[0]
    report["status"] = (
        "PASS"
        if report["revision"] == "0005_export_scope"
        and report["tablesWithRls"] == 24
        and all(v == "PASS" for v in report["catalogGroups"].values())
        and all(
            report[k]
            for k in (
                "runtimeDml",
                "authAccessVerified",
                "runtimeCreateDenied",
                "domainDdlDenied",
                "publicDdlDenied",
                "revisionWriteDenied",
                "authExtraColumnsDenied",
                "authWritesDenied",
                "schemaRolledBack",
                "rolesRolledBack",
            )
        )
        else "FAILED"
    )
    path = (
        ROOT
        / "docs/plans/validation-artifacts"
        / (
            "supabase-auth-rls-rehearsal.json"
            if args.auth_rls
            else "supabase-migration-rehearsal.json"
        )
    )
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    if report["status"] != "PASS":
        raise RuntimeError("Local review rehearsal failed")


if __name__ == "__main__":
    main()
