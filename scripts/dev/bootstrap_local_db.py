"""Enable the local backend login and write a private test environment file.

Never reads the root .env. Database endpoints must be loopback before connecting.
Run again after every db reset. Load .local/test.env into the test process only.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import secrets
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

import asyncpg
from supabase_worktree import ROOT, cli, prepare


async def bootstrap(workdir: Path, output: Path) -> None:
    status = cli(workdir, "status", "-o", "json")
    if status.returncode:
        raise RuntimeError("Local Supabase is not ready; start it before bootstrapping")
    data = json.loads(status.stdout)
    admin_url = data.get("DB_URL") or data.get("db_url")
    api_url = data.get("API_URL") or data.get("api_url")
    parsed = urlsplit(admin_url or "")
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"} or urlsplit(
        api_url or ""
    ).hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Bootstrap accepts local loopback Supabase endpoints only")
    password = secrets.token_urlsafe(32)
    connection = await asyncpg.connect(admin_url)
    try:
        literal = await connection.fetchval("select quote_literal($1::text)", password)
        await connection.execute(f"alter role moodprint_api login password {literal}")
    finally:
        await connection.close()
    host = f"[{parsed.hostname}]" if parsed.hostname == "::1" else parsed.hostname
    api_db = urlunsplit(
        (
            "postgresql+asyncpg",
            f"moodprint_api:{quote(password, safe='')}@{host}:{parsed.port or 5432}",
            parsed.path,
            "",
            "",
        )
    )
    values = {
        "APP_ENV": "test",
        "SUPABASE_URL": api_url,
        "SUPABASE_PUBLISHABLE_KEY": data.get("PUBLISHABLE_KEY") or data.get("ANON_KEY"),
        "SUPABASE_SECRET_KEY": data.get("SECRET_KEY") or data.get("SERVICE_ROLE_KEY"),
        "TEST_DATABASE_URL": api_db,
        "DATABASE_URL": api_db,
        "TEST_ADMIN_DATABASE_URL": admin_url.replace("postgresql://", "postgresql+asyncpg://", 1),
    }
    if not all(values.values()):
        raise ValueError("Local status did not return the required API keys")
    output.parent.mkdir(parents=True, exist_ok=True)
    await asyncio.to_thread(
        output.write_text,
        "".join(f'{key}="{value}"\n' for key, value in values.items()),
        encoding="utf-8",
    )
    print("Local moodprint_api login ready; test environment saved without displaying credentials.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default=os.environ.get("MOODPRINT_STACK_NAME", "foundation"))
    parser.add_argument(
        "--offset", type=int, default=int(os.environ.get("MOODPRINT_PORT_OFFSET", "0"))
    )
    parser.add_argument("--workdir", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        workdir = args.workdir or prepare(args.name, args.offset)
        output = args.output or (
            ROOT / ".local/test.env" if workdir == ROOT else workdir / "test.env"
        )
        if not output.resolve().is_relative_to((ROOT / ".local").resolve()):
            raise ValueError("Bootstrap output must stay inside this worktree .local")
        asyncio.run(bootstrap(workdir, output))
    except (ValueError, RuntimeError) as exc:
        parser.exit(1, f"{exc}\n")
    except Exception:
        parser.exit(1, "Local bootstrap failed; connection details suppressed.\n")


if __name__ == "__main__":
    main()
