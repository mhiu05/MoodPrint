"""Deploy committed SQL migrations to the audited hosted project only.

Run --dry-run and inspect filenames first. --apply additionally requires a local
gate receipt for the same commit, emitted by scripts/verify_phase0.py.
No CLI stdout/stderr or database error strings are printed: they may hold URLs.

Apply re-reads schema_migrations immediately before the mutating CLI and
rejects the plan when that catalog no longer matches the reviewed history.
That check is not a lock and not an atomic apply: the Supabase CLI opens its
own connection, so a concurrent migration can still land after the
confirmation read. The post-apply history check detects that remaining race.
It does not replace the pre-mutation rejection.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import subprocess

import asyncpg
from safety import (
    CLI_VERSION,
    ROOT,
    check_history,
    committed_migrations,
    deployment_plan,
    dry_run_receipt_path,
    load_hosted_env,
    require_dry_run_receipt,
    require_local_gate,
    write_dry_run_receipt,
)


async def run(*, apply: bool, include_all: bool = False) -> None:
    if include_all and not apply:
        raise ValueError("--include-all is valid only with --apply")
    if not apply:
        dry_run_receipt_path(ROOT).unlink(missing_ok=True)
    env = load_hosted_env()
    paths = committed_migrations()
    git_result = await asyncio.to_thread(
        subprocess.run,
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    head = git_result.stdout.strip()

    async def read_history() -> list[tuple[str, str]]:
        connection = await asyncpg.connect(
            env["SUPABASE_DB_URL"], ssl="require", statement_cache_size=0
        )
        try:
            exists = await connection.fetchval(
                "select to_regclass('supabase_migrations.schema_migrations') is not null"
            )
            rows = (
                await connection.fetch(
                    "select version,name from supabase_migrations.schema_migrations order by version"
                )
                if exists
                else []
            )
            return [(row["version"], row["name"]) for row in rows]
        finally:
            await connection.close()

    history = await read_history()
    pending = check_history(paths, history)
    backfill = bool(history and any(path.name[:14] < history[-1][0] for path in pending))
    for path in pending:
        print(path.relative_to(ROOT).as_posix())
    plan = await asyncio.to_thread(deployment_plan, ROOT, head, pending, history)
    if apply:
        if backfill and not include_all:
            raise ValueError("Older pending migrations require explicit --apply --include-all")
        phase = (
            23
            if any("_kb_" in path.name or "_ag_" in path.name for path in paths)
            else (1 if any("_f1_" in path.name for path in paths) else 0)
        )
        require_local_gate(ROOT, head, phase=phase)
        require_dry_run_receipt(ROOT, plan, cli_dry_run=not backfill)
    elif backfill:
        # The CLI needs --include-all for old versions, but that flag is apply
        # only here. Record an honest catalog/commit audit, never a fake CLI pass.
        write_dry_run_receipt(ROOT, plan, cli_dry_run=False)
        print(
            "Read-only backfill audit saved (CLI dry-run not executed); review pending migrations before --apply --include-all."
        )
        return
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
    if include_all:
        command.append("--include-all")
    if apply:
        # Last local action before the external CLI. See the module docstring
        # for the race that remains after this comparison.
        confirmed = await read_history()
        if confirmed != history:
            raise ValueError(
                "Hosted migration history changed after the reviewed dry-run; repeat dry-run before apply"
            )
    result = await asyncio.to_thread(
        subprocess.run, command, cwd=ROOT, capture_output=True, text=True
    )
    if result.returncode:
        raise RuntimeError(
            "Supabase migration command failed; output suppressed to protect credentials"
        )
    if apply:
        after = await read_history()
        if check_history(paths, after) or after != [
            (path.name[:14], path.stem[15:]) for path in sorted(paths, key=lambda path: path.name)
        ]:
            raise ValueError(
                "Hosted migration history after apply does not exactly match the committed migrations"
            )
    else:
        write_dry_run_receipt(ROOT, plan, cli_dry_run=True)
    print("Hosted migrations applied." if apply else "Dry run completed; no hosted changes made.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--include-all",
        action="store_true",
        help="Explicitly apply older pending versions; apply only",
    )
    args = parser.parse_args()
    try:
        asyncio.run(run(apply=args.apply, include_all=args.include_all))
    except (ValueError, RuntimeError) as exc:
        parser.exit(1, f"{exc}\n")
    except Exception:
        parser.exit(1, "Hosted connection failed; no connection details displayed.\n")


if __name__ == "__main__":
    main()
