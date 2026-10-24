"""Enter a database password locally; never accept it as a command-line argument."""

import argparse
import getpass
import json
import re
import sys
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy.engine import URL

ROOT = Path(__file__).resolve().parents[1]


def configure(path: Path, host: str, username: str, password: str, migration_mode: str):
    values = dotenv_values(path)
    project_url = values.get("SUPABASE_URL", "") or ""
    match = re.fullmatch(r"https://([a-z0-9]+)\.supabase\.co/?", project_url)
    if not match or not username.endswith("." + match[1]):
        raise ValueError("Connect username must match the configured Supabase project")
    if not re.fullmatch(r"[a-z0-9.-]+\.pooler\.supabase\.com", host):
        raise ValueError("Copy the shared pooler hostname from Supabase Connect")
    if not password or any(c in password for c in ("\n", "\r", "\x00")):
        raise ValueError("A nonempty, single-line database password is required")
    session = URL.create(
        "postgresql",
        username=username,
        password=password,
        host=host,
        port=5432,
        database="postgres",
        query={"sslmode": "require"},
    )
    migration = (
        session
        if migration_mode == "session"
        else URL.create(
            "postgresql",
            username="postgres",
            password=password,
            host=f"db.{match[1]}.supabase.co",
            port=5432,
            database="postgres",
            query={"sslmode": "require"},
        )
    )
    updates = {
        "DATABASE_URL": session.render_as_string(hide_password=False),
        "DATABASE_MIGRATION_URL": migration.render_as_string(hide_password=False),
        "DATABASE_POOL_MODE": "session",
    }
    content = path.read_text(encoding="utf-8")
    for name, value in updates.items():
        # Single-quote dotenv values so percent-encoded credentials round-trip safely.
        replacement = name + "='" + value.replace("'", "\\'") + "'"
        if re.search(r"^" + name + r"=", content, re.M):
            content = re.sub(
                r"^" + name + r"=.*$", lambda _, value=replacement: value, content, flags=re.M
            )
        else:
            content += "\n" + replacement + "\n"
    path.write_text(content, encoding="utf-8")
    return list(updates)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True, help="Session pooler host copied from Connect")
    parser.add_argument("--username", required=True, help="Session pooler user copied from Connect")
    parser.add_argument("--migration-mode", choices=("direct", "session"), default="session")
    args = parser.parse_args()
    if not sys.stdin.isatty():
        parser.error("Run in your local interactive terminal; password input is hidden")
    password = getpass.getpass("PostgreSQL password (hidden, local only): ")
    if password != getpass.getpass("Confirm PostgreSQL password: "):
        raise ValueError("Passwords do not match; no file changed")
    updated = configure(
        ROOT / "backend/.env", args.host, args.username, password, args.migration_mode
    )
    print(json.dumps({"updatedVariables": updated, "networkAccessPerformed": False}))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, EOFError, KeyboardInterrupt):
        print("Configuration not updated. Check local input; no credentials are printed.")
        sys.exit(1)
