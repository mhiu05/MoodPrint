"""Provision generated backend login credentials without disclosing secrets."""

from __future__ import annotations

import argparse
import asyncio
import secrets
from urllib.parse import quote, urlsplit, urlunsplit

import asyncpg
from safety import (
    PROJECT_REF,
    ROOT,
    is_generated_runtime_url,
    load_hosted_env,
    write_generated_database_url,
)


async def provision(*, rotate: bool) -> None:
    env = load_hosted_env()
    # Validate an existing owner value before changing a database credential.
    if env.get("DATABASE_URL") and not rotate:
        raise ValueError(
            "DATABASE_URL already exists; use --rotate to replace generated credentials"
        )
    if env.get("DATABASE_URL") and rotate and not is_generated_runtime_url(env["DATABASE_URL"]):
        raise ValueError("Existing DATABASE_URL is owner supplied; it cannot be overwritten")
    password = secrets.token_urlsafe(32)
    parsed = urlsplit(env["SUPABASE_DB_URL"])
    username = "moodprint_api" + (
        f".{PROJECT_REF}" if (parsed.hostname or "").endswith(".pooler.supabase.com") else ""
    )
    netloc = f"{username}:{quote(password, safe='')}@{parsed.hostname}:{parsed.port or 5432}"
    generated = urlunsplit(("postgresql+asyncpg", netloc, parsed.path, parsed.query, ""))
    connection = await asyncpg.connect(
        env["SUPABASE_DB_URL"], ssl="require", statement_cache_size=0
    )
    try:
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
    except ValueError as exc:
        parser.exit(1, f"{exc}\n")
    except Exception:
        parser.exit(1, "Credential provisioning failed; details suppressed to protect secrets.\n")


if __name__ == "__main__":
    main()
