"""Reset/test both phase orders on an EXISTING isolated local stack.

Source migrations are read only. Only temporary copies receive new timestamps.
The real source chronology is restored and reset even after a failed command.
This command never starts/stops a stack and never accepts a database URL.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tomllib
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NAME = re.compile(r"^(\d{14})_(f0|f1|kb|ag)_([a-z0-9_]+)\.sql$")


def migrations(source: Path) -> list[tuple[str, bytes]]:
    versions = set()
    result = []
    for path in sorted(source.iterdir()):
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"Migration directory contains a non-regular file: {path.name}")
        match = NAME.fullmatch(path.name)
        if not match:
            raise ValueError(f"Invalid migration filename: {path.name}")
        version = match[1]
        try:
            datetime.strptime(version, "%Y%m%d%H%M%S")
        except ValueError:
            raise ValueError(f"Invalid migration timestamp: {path.name}") from None
        if version in versions:
            raise ValueError(f"Duplicate migration version: {version}")
        versions.add(version)
        result.append((path.name, path.read_bytes()))
    if not result:
        raise ValueError("No source migrations found")
    return result


def permutation(source: Path, first: str) -> list[tuple[str, bytes]]:
    if first not in {"kb", "ag"}:
        raise ValueError("Order must be kb or ag")
    files = migrations(source)
    baseline = [(name, content) for name, content in files if name.split("_")[1] in {"f0", "f1"}]
    if not baseline:
        raise ValueError("Baseline migrations are required")
    timestamp = datetime.strptime(baseline[-1][0][:14], "%Y%m%d%H%M%S")
    result = list(baseline)
    for phase in [first, "ag" if first == "kb" else "kb"]:
        for name, content in files:
            if name.split("_")[1] == phase:
                timestamp += timedelta(seconds=1)
                result.append((timestamp.strftime("%Y%m%d%H%M%S") + name[14:], content))
    return result


def current_stack(root: Path, environment: dict[str, str]) -> Path:
    name = environment.get("MOODPRINT_STACK_NAME", "")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,39}", name):
        raise ValueError("MOODPRINT_STACK_NAME must identify an existing isolated stack")
    try:
        offset = int(environment["MOODPRINT_PORT_OFFSET"])
    except (KeyError, ValueError):
        raise ValueError("MOODPRINT_PORT_OFFSET is required and must be an integer") from None
    if not 1 <= offset <= 9000:
        raise ValueError("An isolated stack requires a port offset between 1 and 9000")
    workdir = root / ".local/stacks" / name
    stack_parent = (root / ".local/stacks").resolve()
    if (
        not stack_parent.is_relative_to(root.resolve())
        or workdir.resolve().parent != stack_parent
        or workdir.is_symlink()
    ):
        raise ValueError("Stack path escapes the isolated stack directory")
    try:
        config = tomllib.loads((workdir / "supabase/config.toml").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise ValueError(
            "Prepare the current isolated stack before checking migration orders"
        ) from None
    if (
        config.get("project_id") != f"moodprint-{name}"
        or config.get("db", {}).get("port") != 54322 + offset
    ):
        raise ValueError("Stack config does not match the current stack name/offset")
    return workdir


def _replace(target: Path, files: list[tuple[str, bytes]]) -> None:
    current = list(target.iterdir())
    if any(not path.is_file() or path.is_symlink() for path in current):
        raise ValueError("Stack migration copies must be regular files")
    for path in current:
        path.unlink()
    for name, content in files:
        (target / name).write_bytes(content)


def run_orders(source: Path, workdir: Path, run, only_order: str | None = None) -> None:
    root = source.resolve().parents[1]
    expected_parent = (root / ".local/stacks").resolve()
    target = workdir / "supabase/migrations"
    if (
        not expected_parent.is_relative_to(root)
        or workdir.resolve().parent != expected_parent
        or workdir.is_symlink()
        or target.is_symlink()
        or not target.is_dir()
        or target.resolve() != workdir.resolve() / "supabase/migrations"
    ):
        raise ValueError("Refusing to modify migrations outside an existing isolated stack")
    original = migrations(source)
    plans = [
        (first, permutation(source, first))
        for first in ("kb", "ag")
        if only_order is None or first == only_order
    ]
    if not plans:
        raise ValueError("Invalid order selection")
    lock = workdir / ".migration-order.lock"
    try:
        lock.mkdir()
    except FileExistsError:
        raise ValueError("Another migration-order check owns this stack") from None

    def checked(*args: str) -> None:
        result = run(workdir, *args)
        if result.returncode:
            raise RuntimeError(
                f"Local migration-order {' '.join(args[:2])} failed (exit {result.returncode}); CLI output withheld"
            )

    failed = False
    try:
        for first, plan in plans:
            _replace(target, plan)
            checked("db", "reset", "--local", "--yes")
            checked("test", "db", "--local")
            print(f"VERIFIED order={first}-first")
    except BaseException:
        failed = True
        raise
    finally:
        try:
            _replace(target, original)
            checked("db", "reset", "--local", "--yes")
        except BaseException:
            if failed:
                print(
                    "RESTORE RESET FAILED: source migration copies restored where possible; local stack needs recovery",
                    file=sys.stderr,
                )
            else:
                raise
        finally:
            lock.rmdir()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--self-test", action="store_true", help="Run unit tests only; never contact Docker"
    )
    parser.add_argument("--only-order", choices=("A", "B"))
    args = parser.parse_args()
    if args.self_test:
        raise SystemExit(
            subprocess.call(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    str(ROOT / "scripts/tests/test_migration_order_check.py"),
                    "-q",
                ],
                cwd=ROOT,
            )
        )
    from supabase_worktree import cli

    try:
        run_orders(
            ROOT / "supabase/migrations",
            current_stack(ROOT, dict(os.environ)),
            cli,
            {"A": "kb", "B": "ag"}.get(args.only_order),
        )
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
