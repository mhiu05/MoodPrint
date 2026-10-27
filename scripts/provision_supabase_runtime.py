"""Review or provision the separately approved backend LOGIN; never print credentials."""

import argparse
import hashlib
import json
import re
import secrets
import sys
import time
from io import StringIO
from pathlib import Path

import psycopg
from dotenv import dotenv_values
from psycopg import sql
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "backend"))
from apply_supabase_review import PROJECT, validate_target  # noqa: E402

# Approved SQL lives in one tracked directory pinned by MANIFEST.json (scripts/check_reviewed_artifacts.py).
REVIEW = ROOT / "deploy/supabase/reviewed-sql/supabase-runtime-login-review.sql"
REPORTS = ROOT / "deploy/supabase/reports"
ROLE = "moodprint_backend"


def review(approved_hash=None):
    content = REVIEW.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    if approved_hash and digest != approved_hash.lower():
        raise ValueError("Approved runtime SQL hash does not match")
    template = content.decode("utf-8")
    if template.count("PASSWORD {runtime_password}") != 1:
        raise ValueError("Runtime SQL must contain exactly one password placeholder")
    return digest, template


def runtime_configuration(path: Path, password: str):
    content = path.read_text(encoding="utf-8")
    values = dotenv_values(stream=StringIO(content))
    owner = validate_target(
        values.get("DATABASE_MIGRATION_URL") or "", values.get("SUPABASE_URL") or ""
    )
    target = make_url(owner)
    username = f"{ROLE}.{PROJECT}" if target.host.endswith(".pooler.supabase.com") else ROLE
    runtime = target.set(username=username, password=password).render_as_string(hide_password=False)
    replacement = "DATABASE_URL='" + runtime.replace("'", "\\'") + "'"
    if re.search(r"^DATABASE_URL=", content, re.M):
        content = re.sub(r"^DATABASE_URL=.*$", lambda _: replacement, content, flags=re.M)
    else:
        content += "\n" + replacement + "\n"
    parsed = dotenv_values(stream=StringIO(content))
    if make_url(parsed["DATABASE_URL"]).password != password:
        raise ValueError("Runtime password encoding did not round-trip")
    return content


def runtime_checks(db):
    # Resolve private Auth relations through pg_catalog, without requiring Auth USAGE.
    row = db.execute("""SELECT current_user, NOT rolsuper AND NOT rolcreatedb
              AND NOT rolcreaterole AND NOT rolreplication AND NOT rolbypassrls,
              pg_has_role(current_user,'moodprint_app','USAGE'),
              NOT has_schema_privilege(current_user,'moodprint','CREATE')
                AND NOT has_schema_privilege(current_user,'public','CREATE'),
              NOT has_schema_privilege(current_user,'auth','USAGE')
                AND NOT has_column_privilege(current_user,(select c.oid from pg_class c
                    join pg_namespace n on n.oid=c.relnamespace where n.nspname='auth' and c.relname='sessions'),'id','SELECT')
                AND NOT has_column_privilege(current_user,(select c.oid from pg_class c
                    join pg_namespace n on n.oid=c.relnamespace where n.nspname='auth' and c.relname='sessions'),'user_id','SELECT'),
              has_function_privilege(current_user,'moodprint.is_provider_session_active(uuid,uuid)','EXECUTE'),
              NOT moodprint.is_provider_session_active('00000000-0000-0000-0000-000000000000'::uuid,
                '00000000-0000-0000-0000-000000000000'::uuid)
              FROM pg_roles WHERE rolname=current_user""").fetchone()
    keys = (
        "leastPrivilege", "inheritsApplicationGroup", "ddlDenied", "rawAuthDenied",
        "privateHelperExecutable", "privateHelperRejectsUnknownSession",
    )
    checks = dict(zip(keys, row[1:], strict=True))
    checks.update(roleMatches=row[0] == ROLE, tlsActive=bool(db.pgconn.ssl_in_use))
    return checks


def verify_runtime(raw):
    with psycopg.connect(raw, connect_timeout=5, prepare_threshold=None) as db:
        with db.transaction():
            db.execute("SET TRANSACTION READ ONLY")
            db.execute("SET LOCAL statement_timeout='5s'")
            return runtime_checks(db)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--verify-only", action="store_true", help="Read-only verification; never replay role DDL")
    parser.add_argument("--approved-sha256")
    args = parser.parse_args()
    if args.apply and args.verify_only:
        parser.error("Choose apply or read-only verification")
    if args.apply and not args.approved_sha256:
        parser.error("Separate explicit approval of the runtime SQL is required")
    digest, template = review(args.approved_sha256)
    if not args.apply and not args.verify_only:
        print(json.dumps({"mode": "review_only", "sha256": digest, "networkAccessPerformed": False}))
        return
    path = ROOT / "backend/.env"
    original = path.read_bytes()
    values = dotenv_values(stream=StringIO(original.decode("utf-8")))
    owner = validate_target(
        values.get("DATABASE_MIGRATION_URL") or "", values.get("SUPABASE_URL") or ""
    )
    if args.verify_only:
        runtime = make_url(values.get("DATABASE_URL") or "")
        target = make_url(owner)
        expected_user = f"{ROLE}.{PROJECT}" if target.host.endswith(".pooler.supabase.com") else ROLE
        if runtime.host != target.host or runtime.username != expected_user or runtime.query.get("sslmode") not in ("require", "verify-ca", "verify-full"):
            raise ValueError("Runtime target does not match the provisioned project/role/TLS")
        checks = verify_runtime(runtime.render_as_string(hide_password=False))
        report = {"projectId": PROJECT, "readOnly": True, "ddlSubmitted": False, "checks": checks,
                  "status": "PASS" if all(checks.values()) else "FAIL"}
        REPORTS.mkdir(parents=True, exist_ok=True)
        (REPORTS / "supabase-runtime-verification.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(report, indent=2))
        if report["status"] != "PASS":
            sys.exit(1)
        return
    report = {
        "projectId": PROJECT, "sqlSha256": digest, "ddlSubmitted": False,
        "transactionOutcome": "not_submitted", "updatedVariables": [],
        "managedAuthChanged": False,
    }
    try:
        password = secrets.token_urlsafe(48)
        content = runtime_configuration(path, password)
        with psycopg.connect(owner, autocommit=True, connect_timeout=5, prepare_threshold=None) as db:
            if not db.pgconn.ssl_in_use:
                raise ValueError("TLS is required")
            with db.transaction():
                db.execute("SET TRANSACTION READ ONLY")
                db.execute("SET LOCAL statement_timeout='5s'")
                identity = db.execute("select current_database(),current_user").fetchone()
                head = db.execute("select version_num from moodprint.alembic_version").fetchall()
                groups = db.execute("""select count(*)=2 and bool_and(not rolcanlogin
                    and not rolsuper and not rolbypassrls) from pg_roles
                    where rolname in ('moodprint_app','moodprint_runtime')""").fetchone()[0]
                exists = db.execute("select exists(select 1 from pg_roles where rolname=%s)", (ROLE,)).fetchone()[0]
                if identity != ("postgres", "postgres") or head != [("0005_export_scope",)] or not groups or exists:
                    raise ValueError("Runtime preflight conflict; do not replay role creation")
            verifier = db.pgconn.encrypt_password(password.encode(), ROLE.encode(), b"scram-sha-256").decode()
            if not verifier.startswith("SCRAM-SHA-256$"):
                raise ValueError("Only a SCRAM verifier may be submitted as SQL")
            if path.read_bytes() != original:
                raise ValueError("Local configuration changed concurrently; no DDL submitted")
            report.update(ddlSubmitted=True, transactionOutcome="unknown_until_inspected")
            db.execute(sql.SQL(template).format(runtime_password=sql.Literal(verifier)), prepare=False)
            report["transactionOutcome"] = "committed"
        # No temporary plaintext files; preserve the migration owner and all other values.
        if path.read_bytes() != original:
            raise ValueError("Local configuration changed concurrently after role commit")
        path.write_text(content, encoding="utf-8")
        report["updatedVariables"] = ["DATABASE_URL"]
        runtime = dotenv_values(stream=StringIO(content))["DATABASE_URL"]
        for attempt in range(3):
            try:
                report["checks"] = verify_runtime(runtime)
                break
            except psycopg.OperationalError:
                if attempt == 2:
                    raise
                time.sleep(2 * (attempt + 1))
        report["status"] = "PASS" if all(report["checks"].values()) else "FAIL"
    except Exception as error:
        report.update(status="FAILED_REQUIRES_READ_ONLY_INSPECTION", errorType=type(error).__name__)
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "supabase-runtime-provision.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))
    if report["status"] != "PASS":
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except (Exception, KeyboardInterrupt) as error:
        print(json.dumps({"status": "rejected", "errorType": type(error).__name__}))
        sys.exit(1)
