"""Apply exactly one approved Alembic-generated SQL artifact; no implicit approval."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import psycopg
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.core.config import Settings  # noqa: E402

PROJECT = "roznanxbiyqybjpvtilq"
# Approved SQL lives in one tracked directory pinned by MANIFEST.json (scripts/check_reviewed_artifacts.py).
REVIEWED_SQL = ROOT / "deploy/supabase/reviewed-sql"
REPORTS = ROOT / "deploy/supabase/reports"
REVIEW = REVIEWED_SQL / "supabase-initialization-review.sql"
AUTH_REVIEW = REVIEWED_SQL / "supabase-initialization-auth-review.sql"
INITIAL_REVISION = "0005_export_scope"  # What the initialization approvals were generated from.
POOLER_HOST = "aws-0-ap-northeast-1.pooler.supabase.com"  # Verified in Connect, not derived.


@dataclass(frozen=True)
class UpgradePlan:
    """One reviewed, expand-only hosted step executed from Alembic's offline export."""

    review: Path
    report: Path
    from_revision: str
    to_revision: str
    tables: tuple[str, ...] = ()
    functions: tuple[str, ...] = ()


UPGRADES = {
    "0009": UpgradePlan(
        REVIEWED_SQL / "supabase-0006-0009-review.sql",
        REPORTS / "supabase-0006-0009-execution.json",
        "0005_export_scope",
        "0009_memory_embeddings",
        tables=(
            "ai_usage",
            "ai_preferences",
            "ai_conversations",
            "ai_messages",
            "ai_turns",
            "memory_proposals",
            "memory_embedding_jobs",
            "memory_embeddings",
        ),
    ),
    "0010": UpgradePlan(
        REVIEWED_SQL / "supabase-0010-review.sql",
        REPORTS / "supabase-0010-execution.json",
        "0009_memory_embeddings",
        "0010_account_deletion",
        functions=("moodprint.delete_provider_identity(uuid)",),
    ),
    "0011": UpgradePlan(
        REVIEWED_SQL / "0011-review.sql",
        REPORTS / "0011-execution.json",
        "0010_account_deletion",
        "0011_social_stabilization",
        tables=("connection_reads",),
    ),
    "0012": UpgradePlan(
        REVIEWED_SQL / "0012-review.sql",
        REPORTS / "0012-execution.json",
        "0011_social_stabilization",
        "0012_matching_v2",
        tables=("matching_stats_daily",),
    ),
    "0013": UpgradePlan(
        REVIEWED_SQL / "0013-review.sql",
        REPORTS / "0013-execution.json",
        "0012_matching_v2",
        "0013_shared_activities",
        tables=("activity_sessions", "activity_participants", "activity_responses"),
    ),
    "0014": UpgradePlan(
        REVIEWED_SQL / "0014-review.sql",
        REPORTS / "0014-execution.json",
        "0013_shared_activities",
        "0014_moderation",
        tables=("staff_roles", "moderation_actions"),
    ),
    "0018": UpgradePlan(
        REVIEWED_SQL / "0018-review.sql",
        REPORTS / "0018-execution.json",
        "0015_context_privacy",
        "0018_app_feedback",
        tables=(
            "guest_provisioning_attempts",
            "guest_cleanup_jobs",
            "guest_usage",
            "guest_abuse_buckets",
            "guest_budget_days",
            "guest_cost_reservations",
            "guest_operation_links",
            "app_feedback",
            "feedback_submission_receipts",
            "feedback_review_events",
        ),
    ),
}
SUPABASE_API_ROLES = ("anon", "authenticated", "service_role")


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
        [sys.executable, "-m", "alembic", "upgrade", INITIAL_REVISION, "--sql"],
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


def alembic_export(revisions: str) -> str:
    env = {
        **os.environ,
        "DATABASE_URL": "postgresql+psycopg://localhost/moodprint_review_test",
        "DATABASE_MIGRATION_URL": "",
        "AI_ENABLED": "false",
        "STT_ENABLED": "false",
    }
    return subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", revisions, "--sql"],
        cwd=ROOT / "backend",
        env=env,
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def review_upgrade_artifact(plan: UpgradePlan, approved_sha256: str | None):
    content = plan.review.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    if approved_sha256 and digest != approved_sha256.lower():
        raise ValueError("Approved SQL hash does not match the current artifact")
    sql = content.decode("utf-8").replace("\r\n", "\n")
    expected = alembic_export(f"{plan.from_revision}:{plan.to_revision}")
    if sql != expected.replace("\r\n", "\n"):
        raise ValueError("Reviewed SQL no longer matches the Alembic offline export")
    # Constraint swaps on tables this same artifact creates are empty by construction.
    own_table_constraint_swap = re.compile(
        r"^ALTER TABLE moodprint\.(\w+) DROP CONSTRAINT \w+;$", re.M
    )
    checked = own_table_constraint_swap.sub(
        lambda match: "" if match.group(1) in plan.tables else match.group(0), sql
    )
    if re.search(r"\b(?:DROP|TRUNCATE)\b", checked, re.I):
        raise ValueError("Destructive SQL is not supported by this upgrade")
    # Executed verbatim: a driver-escaped percent sign would reach PL/pgSQL format().
    if "%%" in sql:
        raise ValueError("Offline SQL contains driver-escaped percent signs")
    return digest, sql


def existing_row_counts(db) -> dict[str, int]:
    tables = [
        row[0]
        for row in db.execute(
            """select c.relname from pg_class c join pg_namespace n on n.oid=c.relnamespace
            where n.nspname='moodprint' and c.relkind='r' order by c.relname"""
        ).fetchall()
    ]
    return {
        table: db.execute(f'select count(*) from moodprint."{table}"').fetchone()[0]
        for table in tables
    }


def upgrade_checks(db, plan: UpgradePlan, before_counts: dict[str, int]):
    revision = db.execute("select array_agg(version_num) from moodprint.alembic_version").fetchone()[
        0
    ]
    after_counts = existing_row_counts(db)
    tables = list(plan.tables)
    api_roles = [
        role
        for (role,) in db.execute(
            "select rolname from pg_roles where rolname = any(%s)", (list(SUPABASE_API_ROLES),)
        ).fetchall()
    ]
    checks = {
        "revision": revision == [plan.to_revision],
        "runtimeNoSchemaCreate": db.execute(
            "select not has_schema_privilege('moodprint_app','moodprint','CREATE')"
        ).fetchone()[0],
        "existingRowsPreserved": all(
            after_counts.get(table) == count for table, count in before_counts.items()
        ),
    }
    details: dict = {
        "existingTables": len(before_counts),
        "existingRows": sum(before_counts.values()),
        "supabaseApiRolesPresent": api_roles,
    }
    if tables:
        rls = db.execute(
            """select count(*) from pg_class c join pg_namespace n on n.oid=c.relnamespace
            where n.nspname='moodprint' and c.relkind='r' and c.relrowsecurity
              and c.relname = any(%s)""",
            (tables,),
        ).fetchone()[0]
        policies = db.execute(
            """select count(*) from pg_policies where schemaname='moodprint'
            and tablename = any(%s) and policyname='backend_access'
            and roles = '{moodprint_runtime}' and cmd='ALL'""",
            (tables,),
        ).fetchone()[0]
        checks["newTablesWithRls"] = rls == len(tables)
        checks["backendAccessPolicies"] = policies == len(tables)
        checks["runtimeDmlOnNewTables"] = db.execute(
            """select bool_and(has_table_privilege('moodprint_app', 'moodprint.'||t, p))
            from unnest(%s::text[]) t
            cross join (values ('SELECT'),('INSERT'),('UPDATE'),('DELETE')) v(p)""",
            (tables,),
        ).fetchone()[0]
        checks["supabaseApiRolesDeniedTables"] = all(
            not db.execute(
                """select bool_or(has_table_privilege(%s, 'moodprint.'||t, p))
                from unnest(%s::text[]) t
                cross join (values ('SELECT'),('INSERT'),('UPDATE'),('DELETE')) v(p)""",
                (role, tables),
            ).fetchone()[0]
            for role in api_roles
        )
    if "memory_embeddings" in tables:
        vector = db.execute(
            """select e.extversion from pg_extension e join pg_namespace n on n.oid=e.extnamespace
            where e.extname='vector' and n.nspname='extensions'"""
        ).fetchone()
        checks["vectorInExtensions"] = vector is not None
        checks["runtimeVectorTypeUsage"] = db.execute(
            "select has_schema_privilege('moodprint_app','extensions','USAGE')"
        ).fetchone()[0]
        details["vectorVersion"] = vector[0] if vector else None
    for function in plan.functions:
        definition = db.execute(
            """select p.prosecdef, pg_get_userbyid(p.proowner), array_to_string(p.proconfig, ',')
            from pg_proc p where p.oid = %s::regprocedure""",
            (function,),
        ).fetchone()
        checks[f"{function}:securityDefinerOwnedByPostgres"] = definition is not None and tuple(
            definition
        ) == (True, "postgres", 'search_path=""')
        checks[f"{function}:runtimeExecute"] = db.execute(
            "select has_function_privilege('moodprint_app', %s, 'EXECUTE')", (function,)
        ).fetchone()[0]
        checks[f"{function}:apiRolesDenied"] = all(
            not db.execute(
                "select has_function_privilege(%s, %s, 'EXECUTE')", (role, function)
            ).fetchone()[0]
            for role in api_roles
        )
    return {key: "PASS" if value else "FAIL" for key, value in checks.items()}, details


def run_upgrade(
    raw: str, plan: UpgradePlan, *, digest: str, sql: str, hosted: bool, write: bool
):
    """Pre-check read-only, execute the exact reviewed SQL once, then verify read-only."""
    report = {
        "target": "hosted:" + PROJECT if hosted else "local-rehearsal",
        "sqlSha256": digest,
        "fromRevision": plan.from_revision,
        "toRevision": plan.to_revision,
        "ddlSubmitted": False,
        "transactionOutcome": "not_submitted",
        "executionMechanism": "Alembic offline export executed verbatim in one transaction; no stamp/online upgrade/MCP migration",
    }
    try:
        with psycopg.connect(raw, autocommit=True, connect_timeout=10, prepare_threshold=None) as db:
            if hosted and not db.pgconn.ssl_in_use:
                raise ValueError("TLS is required")
            with db.transaction():
                db.execute("SET TRANSACTION READ ONLY")
                db.execute("SET LOCAL statement_timeout='15s'")
                if hosted and db.execute("select current_database(),current_user").fetchone() != (
                    "postgres",
                    "postgres",
                ):
                    raise ValueError("Unexpected migration identity")
                revision = db.execute(
                    "select array_agg(version_num) from moodprint.alembic_version"
                ).fetchone()[0]
                if revision != [plan.from_revision]:
                    raise ValueError(
                        "Revision is not the plan's starting point; inspect, never replay DDL"
                    )
                clash = db.execute(
                    """select count(*) from pg_class c join pg_namespace n on n.oid=c.relnamespace
                    where n.nspname='moodprint' and c.relname = any(%s)""",
                    (list(plan.tables),),
                ).fetchone()[0]
                if clash:
                    raise ValueError("Upgrade tables already exist; inspect drift")
                before_counts = existing_row_counts(db)
                before_auth = auth_fingerprint(db)
            report["ddlSubmitted"] = True
            report["transactionOutcome"] = "unknown_until_verified"
            db.execute(sql, prepare=False)
            report["transactionOutcome"] = "committed"
            with db.transaction():
                db.execute("SET TRANSACTION READ ONLY")
                db.execute("SET LOCAL statement_timeout='15s'")
                checks, details = upgrade_checks(db, plan, before_counts)
                checks["authStructureUnchanged"] = (
                    "PASS" if before_auth == auth_fingerprint(db) else "FAIL"
                )
            report["checks"] = checks
            report["details"] = details
            report["status"] = "PASS" if all(v == "PASS" for v in checks.values()) else "FAIL"
    except Exception as error:
        # A lost connection after submission is never treated as permission to retry DDL.
        report.update(
            {"status": "FAILED_REQUIRES_READ_ONLY_INSPECTION", "errorType": type(error).__name__}
        )
        if isinstance(error, psycopg.Error) and error.diag.message_primary:
            report["errorMessage"] = error.diag.message_primary[:200]
        if not report["ddlSubmitted"]:
            report["transactionOutcome"] = "not_submitted"
    if write:
        plan.report.parent.mkdir(parents=True, exist_ok=True)
        plan.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


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
    parser.add_argument(
        "--upgrade",
        choices=sorted(UPGRADES),
        help="Use a reviewed incremental upgrade artifact instead of the initialization one",
    )
    parser.add_argument(
        "--rehearse-url",
        help="Execute the upgrade on a local *_test DB restored from a hosted snapshot",
    )
    args = parser.parse_args()
    if args.apply and not args.approved_sha256:
        parser.error("Explicit SQL approval and its SHA256 are required before --apply")
    if args.upgrade:
        plan = UPGRADES[args.upgrade]
        digest, sql = review_upgrade_artifact(plan, args.approved_sha256)
        if args.rehearse_url:
            target = make_url(args.rehearse_url)
            if target.host not in ("localhost", "127.0.0.1", "::1") or not (
                target.database or ""
            ).endswith("_test"):
                raise ValueError("Rehearsal requires a local disposable *_test database")
            raw = target.set(drivername="postgresql").render_as_string(hide_password=False)
            report = run_upgrade(raw, plan, digest=digest, sql=sql, hosted=False, write=False)
        elif args.apply:
            settings = Settings(_env_file=ROOT / "backend/.env")
            if not settings.database_migration_url:
                raise ValueError("DATABASE_MIGRATION_URL is required")
            raw = validate_target(
                settings.database_migration_url.get_secret_value(), settings.supabase_url
            )
            report = run_upgrade(raw, plan, digest=digest, sql=sql, hosted=True, write=True)
        else:
            report = {"mode": "review_only", "sha256": digest, "alembicExportMatches": True}
        print(json.dumps(report, indent=2))
        if report.get("status", "PASS") != "PASS":
            sys.exit(1)
        return
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
    path = REPORTS / "supabase-migration-execution.json"
    path.parent.mkdir(parents=True, exist_ok=True)
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
