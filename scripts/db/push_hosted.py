"""Deploy committed SQL migrations to the audited hosted project only.

Run --dry-run and inspect filenames first. --apply additionally requires a local
gate receipt for the same commit, emitted by scripts/verify_phase0.py.
No CLI stdout/stderr or database error strings are printed: they may hold URLs.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess

import asyncpg
from safety import CLI_VERSION, ROOT, check_history, committed_migrations, load_hosted_env


async def run(*, apply: bool) -> None:
    env = load_hosted_env()
    paths = committed_migrations()
    connection = await asyncpg.connect(
        env["SUPABASE_DB_URL"], ssl="require", statement_cache_size=0
    )
    try:
        exists = await connection.fetchval(
            "select to_regclass('supabase_migrations.schema_migrations') is not null"
        )
        history = (
            await connection.fetch(
                "select version,name from supabase_migrations.schema_migrations order by version"
            )
            if exists
            else []
        )
        pending = check_history(paths, [(row["version"], row["name"]) for row in history])
    finally:
        await connection.close()
    for path in pending:
        print(path.relative_to(ROOT).as_posix())
    if apply:
        git_result = await asyncio.to_thread(
            subprocess.run,
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        head = git_result.stdout.strip()
        receipt_path = ROOT / ".local/phase0-gate.json"
        receipt = json.loads(receipt_path.read_text()) if receipt_path.exists() else {}
        if receipt.get("commit") != head or receipt.get("passed") is not True:
            raise ValueError(
                "A passing local Phase 0 gate receipt for HEAD is required before hosted apply"
            )
    command = [
        "npx.cmd" if os.name == "nt" else "npx",
        "--yes",
        f"supabase@{CLI_VERSION}",
        "db",
        "push",
        "--db-url",
        env["SUPABASE_DB_URL"],
        "--skip-vault",
    ]
    command += ["--yes"] if apply else ["--dry-run"]
    result = await asyncio.to_thread(
        subprocess.run, command, cwd=ROOT, capture_output=True, text=True
    )
    if result.returncode:
        raise RuntimeError(
            "Supabase migration command failed; output suppressed to protect credentials"
        )
    print("Hosted migrations applied." if apply else "Dry run completed; no hosted changes made.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        asyncio.run(run(apply=args.apply))
    except (ValueError, RuntimeError) as exc:
        parser.exit(1, f"{exc}\n")
    except Exception:
        parser.exit(1, "Hosted connection failed; no connection details displayed.\n")


if __name__ == "__main__":
    main()
