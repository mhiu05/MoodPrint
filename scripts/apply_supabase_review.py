"""Apply exactly one approved Alembic-generated SQL artifact; no implicit approval."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import psycopg
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.core.config import Settings  # noqa: E402

PROJECT = "roznanxbiyqybjpvtilq"
REVIEW = ROOT / "docs/plans/validation-artifacts/supabase-initialization-review.sql"
AUTH_REVIEW = ROOT / "docs/plans/validation-artifacts/supabase-initialization-auth-review.sql"
POOLER_HOST = "aws-0-ap-northeast-1.pooler.supabase.com"  # Verified in Connect, not derived.


def validate_target(raw: str, supabase_url: str):
    target = make_url(raw)
    session = target.host == POOLER_HOST and target.username == f"postgres.{PROJECT}"
    direct = target.host == f"db.{PROJECT}.supabase.co" and target.username == "postgres"
    if (
        supabase_url != f"https://{PROJECT}.supabase.co"
        or not (session or direct)
        or target.database != "postgres"
        or target.port != 5432
        or target.query.get("sslmode") not in ("require", "verify-ca", "verify-full")
    ):
        raise ValueError(
            "Migration target must match the reviewed project, endpoint, owner and TLS mode"
        )
    return target.set(drivername="postgresql").render_as_string(hide_password=False)


def review_artifact(approved_sha256: str | None, path: Path | None = None):
    content = (path or REVIEW).read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    if approved_sha256 and digest != approved_sha256.lower():
        raise ValueError("Approved SQL hash does not match the current artifact")
    env = {
        **os.environ,
        "DATABASE_URL": "postgresql+psycopg://localhost/moodprint_review_test",
        "DATABASE_MIGRATION_URL": "",
        "AI_ENABLED": "false",
        "STT_ENABLED": "false",
    }
    export = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head", "--sql"],
        cwd=ROOT / "backend",
        env=env,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    body = re.sub(r"^BEGIN;\s*|^COMMIT;\s*", "", export, flags=re.M)
    sql = content.decode("utf-8").replace("\r\n", "\n")
    if sql.count(body) != 1 or len(re.findall(r"CREATE TABLE moodprint\.", sql)) != 24:
        raise ValueError("Reviewed SQL no longer matches the Alembic 0001-0005 export")
    if path == AUTH_REVIEW:
        helper = (ROOT / "backend/app/infrastructure/database/provider_session.sql").read_text(
            encoding="utf-8"
        )
        if sql.count(helper) != 1:
            raise ValueError(
                "Reviewed private Auth helper no longer matches the application source"
            )
    if re.search(r"\b(?:DROP|TRUNCATE)\b", sql, re.I):
        raise ValueError("Destructive SQL is not supported by this initializer")
    return digest, sql


def auth_fingerprint(db):
    # Catalog structure only; never inspect Auth row contents or credentials.
    return db.execute("""select md5(jsonb_build_object(
        'columns',(select jsonb_agg(jsonb_build_array(c.relname,a.attname,a.atttypid,a.atttypmod,a.attnotnull,pg_get_expr(d.adbin,d.adrelid)) order by c.relname,a.attnum)
          from pg_class c join pg_namespace n on n.oid=c.relnamespace join pg_attribute a on a.attrelid=c.oid
          left join pg_attrdef d on d.adrelid=c.oid and d.adnum=a.attnum
          where n.nspname='auth' and c.relkind in ('r','p') and a.attnum>0 and not a.attisdropped),
        'constraints',(select jsonb_agg(jsonb_build_array(c.relname,k.conname,pg_get_constraintdef(k.oid)) order by c.relname,k.conname)
          from pg_constraint k join pg_class c on c.oid=k.conrelid join pg_namespace n on n.oid=c.relnamespace where n.nspname='auth'),
        'rls',(select jsonb_agg(jsonb_build_array(c.relname,c.relrowsecurity,c.relforcerowsecurity) order by c.relname) from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname='auth' and c.relkind in ('r','p')),
        'policies',(select jsonb_agg(jsonb_build_array(tablename,policyname,roles,cmd,qual,with_check) order by tablename,policyname) from pg_policies where schemaname='auth'))::text)""").fetchone()[
        0
    ]


def catalog_checks(db, *, auth_bridge=False):
    rows = db.execute("""select
      (select array_agg(version_num order by version_num) from moodprint.alembic_version),
      (select count(*) from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname='moodprint' and c.relkind='r'),
      (select count(*) from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname='moodprint' and c.relkind='r' and c.relrowsecurity),
      (select count(*) from pg_constraint k join pg_namespace n on n.oid=k.connamespace where n.nspname='moodprint' and k.contype='f'),
      (select count(*) from pg_constraint k join pg_namespace n on n.oid=k.connamespace where n.nspname='moodprint' and k.contype='c'),
      (select count(*) from pg_constraint k join pg_namespace n on n.oid=k.connamespace where n.nspname='moodprint' and k.contype='u'),
      (select count(*) from pg_index i join pg_class c on c.oid=i.indrelid join pg_namespace n on n.oid=c.relnamespace where n.nspname='moodprint' and i.indisunique and i.indpred is not null)""").fetchone()
    role_ok = db.execute("""select count(*)=2 and bool_and(not rolcanlogin and not rolsuper and not rolcreatedb and not rolcreaterole and not rolreplication and not rolbypassrls)
      from pg_roles where rolname in ('moodprint_runtime','moodprint_app')""").fetchone()[0]
    access_ok = db.execute("""select
      not has_schema_privilege('moodprint_app','moodprint','CREATE')
      and not has_schema_privilege('moodprint_app','public','CREATE')
      and (select bool_and(has_table_privilege('moodprint_app',c.oid,p.privilege))
           from pg_class c join pg_namespace n on n.oid=c.relnamespace
           cross join (values ('SELECT'),('INSERT'),('UPDATE'),('DELETE')) p(privilege)
           where n.nspname='moodprint' and c.relkind='r' and c.relname <> 'alembic_version')
      and not has_table_privilege('moodprint_app','moodprint.alembic_version','UPDATE')""").fetchone()[
        0
    ]
    if auth_bridge:
        auth_ok = db.execute("""select
          not has_schema_privilege('moodprint_app','auth','USAGE')
          and has_function_privilege('moodprint_app','moodprint.is_provider_session_active(uuid,uuid)','EXECUTE')
          and not has_function_privilege('anon','moodprint.is_provider_session_active(uuid,uuid)','EXECUTE')
          and not has_function_privilege('authenticated','moodprint.is_provider_session_active(uuid,uuid)','EXECUTE')
          and not has_table_privilege('moodprint_app','auth.sessions','SELECT')
          and not has_table_privilege('moodprint_app','auth.sessions','UPDATE')
          and exists(select 1 from pg_proc p where p.oid='moodprint.is_provider_session_active(uuid,uuid)'::regprocedure
             and p.prosecdef and pg_get_userbyid(p.proowner)='postgres' and array_to_string(p.proconfig,',')='search_path=""')""").fetchone()[
            0
        ]
    else:
        auth_ok = db.execute("""select
      has_schema_privilege('moodprint_app','auth','USAGE')
      and has_column_privilege('moodprint_app','auth.sessions','id','SELECT')
      and has_column_privilege('moodprint_app','auth.sessions','user_id','SELECT')
      and not has_table_privilege('moodprint_app','auth.sessions','SELECT')
      and not has_table_privilege('moodprint_app','auth.sessions','UPDATE')""").fetchone()[0]
    checks = {
        "revision": rows[0] == ["0005_export_scope"],
        "tables24": rows[1] == 24,
        "rls24": rows[2] == 24,
        "foreignKeys34": rows[3] == 34,
        "checks14": rows[4] == 14,
        "uniqueConstraints9": rows[5] == 9,
        "partialUniqueIndexes5": rows[6] == 5,
        "rolesNologinLeastPrivilege": bool(role_ok),
        "runtimePrivileges": bool(access_ok),
        "privateAuthBridge" if auth_bridge else "legacyAuthColumnGrants": bool(auth_ok),
    }
    return {key: "PASS" if value else "FAIL" for key, value in checks.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Execute only after the user has explicitly approved this SQL",
    )
    parser.add_argument(
        "--approved-sha256", help="SHA256 of the exact SQL approved by the user; not a credential"
    )
    parser.add_argument(
        "--auth-rls",
        action="store_true",
        help="Use the separately approved private Auth-session function artifact",
    )
    args = parser.parse_args()
    if args.apply and not args.approved_sha256:
        parser.error("Explicit SQL approval and its SHA256 are required before --apply")
    digest, sql = review_artifact(args.approved_sha256, AUTH_REVIEW if args.auth_rls else REVIEW)
    if not args.apply:
        print(
            json.dumps(
                {
                    "mode": "review_only",
                    "sha256": digest,
                    "alembicExportMatches": True,
                    "remoteExecuted": False,
                    "networkAccessPerformed": False,
                },
                indent=2,
            )
        )
        return
    settings = Settings(_env_file=ROOT / "backend/.env")
    if not settings.database_migration_url:
        raise ValueError("DATABASE_MIGRATION_URL is required")
    raw = validate_target(settings.database_migration_url.get_secret_value(), settings.supabase_url)
    report = {
        "projectId": PROJECT,
        "sqlSha256": digest,
        "ddlSubmitted": False,
        "transactionOutcome": "not_submitted",
        "executionMechanism": "Alembic offline export, one transaction; no stamp/online upgrade/MCP migration",
        "runtimeLoginReady": False,
        "authE2EExecuted": False,
    }
    try:
        with psycopg.connect(raw, autocommit=True, connect_timeout=5, prepare_threshold=None) as db:
            if not db.pgconn.ssl_in_use:
                raise ValueError("TLS is required")
            with db.transaction():
                db.execute("SET TRANSACTION READ ONLY")
                db.execute("SET LOCAL statement_timeout='5s'")
                identity = db.execute("select current_database(),current_user").fetchone()
                if identity != ("postgres", "postgres"):
                    raise ValueError("Unexpected migration identity")
                exists = db.execute(
                    "select exists(select 1 from pg_namespace where nspname='moodprint')"
                ).fetchone()[0]
                if exists:
                    raise ValueError(
                        "Schema already exists: inspect revision/drift; never replay initialization DDL"
                    )
                auth_rls = db.execute(
                    "select relrowsecurity from pg_class where oid='auth.sessions'::regclass"
                ).fetchone()[0]
                if auth_rls and not args.auth_rls:
                    raise ValueError(
                        "Auth RLS blocks the legacy column-grant design; review the private bridge artifact"
                    )
                before_auth = auth_fingerprint(db)
            report["ddlSubmitted"] = True
            report["transactionOutcome"] = "unknown_until_verified"
            # Exact approved artifact includes BEGIN/COMMIT, revision updates and ACL/RLS.
            db.execute(sql, prepare=False)
            report["transactionOutcome"] = "committed"
            with db.transaction():
                db.execute("SET TRANSACTION READ ONLY")
                db.execute("SET LOCAL statement_timeout='5s'")
                report["checks"] = catalog_checks(db, auth_bridge=args.auth_rls)
                report["checks"]["authStructureUnchanged"] = (
                    "PASS" if before_auth == auth_fingerprint(db) else "FAIL"
                )
            report["status"] = (
                "PASS" if all(v == "PASS" for v in report["checks"].values()) else "FAIL"
            )
    except Exception as error:
        # A lost connection after submission is never treated as permission to retry DDL.
        report.update(
            {"status": "FAILED_REQUIRES_READ_ONLY_INSPECTION", "errorType": type(error).__name__}
        )
        if not report["ddlSubmitted"]:
            report["transactionOutcome"] = "not_submitted"
    path = ROOT / "docs/plans/validation-artifacts/supabase-migration-execution.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    if report["status"] != "PASS":
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except (Exception, KeyboardInterrupt) as error:
        print(
            json.dumps(
                {
                    "status": "rejected",
                    "errorType": type(error).__name__,
                    "credentialsPrinted": False,
                }
            )
        )
        sys.exit(1)
