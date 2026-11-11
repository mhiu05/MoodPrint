"""Provision credentials for the existing restricted role without disclosing secrets.

Run: uv run --locked --package moodprint-backend python scripts/db/set_api_role_password.py
An existing real DATABASE_URL is preserved unless --rotate is explicitly requested.
"""

from __future__ import annotations

import argparse
import asyncio
import re
import secrets
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

import asyncpg
from safety import (
    PROJECT_REF,
    ROOT,
    RUNTIME_URL_PLACEHOLDER,
    is_generated_runtime_url,
    load_hosted_env,
    validate_hosted_target,
    write_generated_database_url,
)


async def provision(*, rotate: bool) -> None:
    env = load_hosted_env()
    admin_url = env["SUPABASE_DB_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    validate_hosted_target(env["SUPABASE_URL"], admin_url)
    parsed = urlsplit(admin_url)
    pooler = (
        parsed.hostname == "aws-0-ap-northeast-2.pooler.supabase.com"
        and parsed.username == f"postgres.{PROJECT_REF}"
    )
    direct = parsed.hostname == f"db.{PROJECT_REF}.supabase.co" and parsed.username == "postgres"
    if (
        not (pooler or direct)
        or (parsed.port or 5432) != 5432
        or parsed.path != "/postgres"
        or parsed.fragment
    ):
        raise ValueError(
            "Provisioning target must be the audited postgres database/session endpoint"
        )
    if not re.fullmatch(r"(?:[A-Za-z0-9_.~-]|%[0-9A-Fa-f]{2})+", parsed.password or ""):
        raise ValueError("SUPABASE_DB_URL password must be percent-encoded")
    options = parse_qsl(parsed.query, keep_blank_values=True)
    if len(options) > 1 or any(key != "sslmode" for key, _ in options):
        raise ValueError(
            "SUPABASE_DB_URL must not override connection targets through query options"
        )
    sslmode = dict(options).get("sslmode", "require")
    if sslmode not in {"require", "verify-ca", "verify-full"}:
        raise ValueError("SUPABASE_DB_URL must require TLS")
    # Validate an existing owner value before changing a database credential.
    current = env.get("DATABASE_URL", "")
    populated = current and current != RUNTIME_URL_PLACEHOLDER
    if populated and not rotate:
        raise ValueError(
            "DATABASE_URL already exists; use --rotate to replace generated credentials"
        )
    if populated and rotate and not is_generated_runtime_url(current):
        raise ValueError("Existing DATABASE_URL is owner supplied; it cannot be overwritten")
    password = secrets.token_urlsafe(32)
    username = "moodprint_api" + (f".{PROJECT_REF}" if pooler else "")
    netloc = f"{username}:{quote(password, safe='')}@{parsed.hostname}:{parsed.port or 5432}"
    generated = urlunsplit(
        ("postgresql+asyncpg", netloc, parsed.path, urlencode({"sslmode": sslmode}), "")
    )
    write_generated_database_url(ROOT / ".env", generated, rotate=rotate, dry_run=True)
    connection = await asyncpg.connect(
        admin_url, ssl=sslmode, statement_cache_size=0, timeout=15, command_timeout=15
    )
    try:
        async with connection.transaction():
            identity = await connection.fetchrow(
                "select current_database() as database, current_user as role, session_user as login"
            )
            if not identity or any(
                identity[key] != value
                for key, value in (
                    ("database", "postgres"),
                    ("role", "postgres"),
                    ("login", "postgres"),
                )
            ):
                raise ValueError(
                    "Connected database identity does not match the audited admin target"
                )
            role = await connection.fetchrow(
                "select rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls, rolinherit "
                "from pg_roles where rolname='moodprint_api'"
            )
            if role is None or any(role.values()):
                raise ValueError("Existing moodprint_api role must have restricted privileges")
            # token_urlsafe alphabet has no SQL quote; nevertheless use server quote_literal.
            literal = await connection.fetchval("select quote_literal($1::text)", password)
            await connection.execute(f"alter role moodprint_api login password {literal}")
            write_generated_database_url(ROOT / ".env", generated, rotate=rotate)
    finally:
        await connection.close()
    print("Backend login provisioned; generated DATABASE_URL saved without displaying credentials.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--rotate",
        action="store_true",
        help="Explicitly replace an existing generated DATABASE_URL",
    )
    args = parser.parse_args()
    try:
        asyncio.run(provision(rotate=args.rotate))
    except ValueError:
        parser.exit(
            1,
            "Credential provisioning refused; check the target, admin credentials and existing "
            "DATABASE_URL (--rotate only replaces generated runtime credentials).\n",
        )
    except Exception:
        parser.exit(1, "Credential provisioning failed; details suppressed to protect secrets.\n")


if __name__ == "__main__":
    main()
