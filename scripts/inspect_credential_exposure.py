"""Read-only credential classification. Never emit values, DSNs, hashes, or errors."""

import argparse
import contextlib
import io
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import psycopg
from dotenv import dotenv_values
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
ROLES = {"postgres", "moodprint_backend", "moodprint_app", "moodprint_runtime"}


def values(text):
    with contextlib.redirect_stderr(io.StringIO()):
        return dotenv_values(stream=io.StringIO(text), interpolate=False)


def role_category(url):
    role = (url.username or "").split(".")[0]
    return role if role in ROLES else "other_redacted"


def inspect(check_active=False, compare_ssm=False):
    path = ROOT / "backend/runtime.txt"
    exposed = values(path.read_text(encoding="utf-8"))
    local = values((ROOT / "backend/.env").read_text(encoding="utf-8"))
    url = make_url(exposed.get("DATABASE_MIGRATION_URL") or "")
    password = url.password
    if not password or len(password) < 8 or not (url.host or "").endswith(".supabase.com"):
        raise ValueError("unsupported_target")
    report = {
        "observed_at_utc": datetime.now(UTC).isoformat(),
        "read_only": True,
        "secret_values_emitted": False,
        "exposure_file": "backend/runtime.txt",
        "exposure_file_tracked": subprocess.run(
            ["git", "ls-files", "--error-unmatch", "backend/runtime.txt"],
            cwd=ROOT, capture_output=True, check=False,
        ).returncode == 0,
        "category": "PostgreSQL password embedded in migration DSN",
        "role_category": role_category(url),
        "tls_requested": url.query.get("sslmode") in {"require", "verify-ca", "verify-full"},
        "local_configuration": {},
    }
    for key in ("DATABASE_URL", "DATABASE_MIGRATION_URL"):
        configured = make_url(local.get(key) or "")
        report["local_configuration"][key] = {
            "same_password": configured.password == password,
            "same_endpoint": configured.host == url.host,
            "role_category": role_category(configured),
        }
    files = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True)
    report["tracked_files_containing_exact_password"] = [
        name for name in files.stdout.decode().split("\0") if name
        and (ROOT / name).is_file() and password.encode() in (ROOT / name).read_bytes()
    ]
    if compare_ssm:
        response = subprocess.run([
            "aws", "ssm", "get-parameter", "--region", "ap-southeast-2",
            "--name", "/moodprint/staging/runtime", "--with-decryption", "--output", "json",
        ], capture_output=True, check=False)
        if response.returncode:
            report["ssm_comparison"] = {"status": "unavailable", "error_details_suppressed": True}
        else:
            parameter = json.loads(response.stdout)["Parameter"]
            settings = values(parameter["Value"])
            report["ssm_comparison"] = {"parameter_version": parameter["Version"], "variables": {}}
            for key in ("DATABASE_URL", "DATABASE_MIGRATION_URL"):
                raw = settings.get(key)
                if not raw:
                    report["ssm_comparison"]["variables"][key] = {"present": False}
                    continue
                configured = make_url(raw)
                report["ssm_comparison"]["variables"][key] = {
                    "present": True, "same_password": configured.password == password,
                    "same_endpoint": configured.host == url.host, "role_category": role_category(configured),
                }
    if check_active:
        try:
            raw = url.set(drivername="postgresql").render_as_string(hide_password=False)
            with psycopg.connect(raw, connect_timeout=5, options="-c default_transaction_read_only=on -c statement_timeout=5000") as db:
                db.execute("SET TRANSACTION READ ONLY")
                db.execute("SET LOCAL statement_timeout='5s'")
                row = db.execute("""SELECT current_user, rolsuper, rolcreaterole, rolcreatedb,
                    rolbypassrls, rolcanlogin, rolconnlimit FROM pg_roles WHERE rolname=current_user""").fetchone()
                role = row[0] if row[0] in ROLES else "other_redacted"
                report["active_check"] = {
                    "status": "authenticated", "role_category": role, "tls_active": bool(db.pgconn.ssl_in_use),
                    "superuser": row[1], "create_role": row[2], "create_database": row[3],
                    "bypass_rls": row[4], "can_login": row[5], "connection_limit": row[6],
                    "transaction_read_only": db.execute("SHOW transaction_read_only").fetchone()[0] == "on",
                }
                db.rollback()
        except Exception as error:  # noqa: BLE001 - DSN-bearing exceptions must never escape.
            report["active_check"] = {"status": "unavailable_or_rejected", "error_type": type(error).__name__}
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-active", action="store_true")
    parser.add_argument("--compare-ssm", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        report = inspect(args.check_active, args.compare_ssm)
    except Exception as error:  # noqa: BLE001 - fixed redacted top-level diagnostic only.
        print(json.dumps({"status": "failed", "error_type": type(error).__name__, "details_suppressed": True}))
        return 1
    rendered = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
