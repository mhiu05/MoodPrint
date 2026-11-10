"""Shared guardrails for the two explicit hosted-operation scripts."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

PROJECT_REF = "xhlshihobyxrgfqrdafh"
CLI_VERSION = "2.122.1"
ROOT = Path(__file__).resolve().parents[2]


def require_local_gate(root: Path, head: str, *, phase: int) -> None:
    """A deployment uses its own full local gate, never an earlier phase's receipt."""
    path = root / f".local/phase{phase}-gate.json"
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise ValueError(
            f"A passing local Phase {phase} gate receipt for HEAD is required"
        ) from None
    if phase not in {0, 1, 23}:
        raise ValueError("Unknown local gate phase")
    if not isinstance(receipt, dict):
        raise ValueError(f"A passing local Phase {phase} gate receipt for HEAD is required")
    expected_scope = {0: "local", 1: "local_phase1", 23: "local_phase23"}[phase]
    checks = receipt.get("checks", [])
    if (
        receipt.get("commit") != head
        or receipt.get("passed") is not True
        or receipt.get("scope") != expected_scope
        or not isinstance(checks, list)
        or len(checks) < (12 if phase == 23 else 8)
        or any(
            not isinstance(check, dict)
            or type(check.get("returncode")) is not int
            or check.get("returncode") != 0
            for check in checks
        )
    ):
        raise ValueError(f"A passing local Phase {phase} gate receipt for HEAD is required")
    if phase in {1, 23}:
        if phase == 23 and any(
            not isinstance(check.get("command"), list)
            or not check["command"]
            or not all(isinstance(arg, str) and arg for arg in check["command"])
            for check in checks
        ):
            raise ValueError("Phase 23 gate requires twelve real command results")
        commands = [check.get("command", []) for check in checks]

        def includes(script: str, option: str | None = None) -> bool:
            for command in commands:
                if not isinstance(command, list) or not all(
                    isinstance(arg, str) for arg in command
                ):
                    continue
                invocation = command
                if (
                    len(invocation) >= 2
                    and Path(invocation[0]).name in {"uv", "uv.exe"}
                    and invocation[1] == "run"
                ):
                    invocation = invocation[2:]
                if len(invocation) < 2 or not re.fullmatch(
                    r"python(?:\d+(?:\.\d+)*)?(?:\.exe)?",
                    invocation[0].replace("\\", "/").split("/")[-1],
                ):
                    continue
                target = invocation[1].replace("\\", "/")
                if target != script and not target.endswith("/" + script):
                    continue
                if option and option not in invocation[2:]:
                    continue
                if (
                    phase == 23
                    and script.endswith("migration_order_check.py")
                    and any(
                        arg == "--self-test" or arg.startswith("--only-order")
                        for arg in invocation[2:]
                    )
                ):
                    continue
                return True
            return False

        if phase == 1 and (
            not includes("scripts/e2e_stack.py", "--run")
            or not includes("scripts/verify_phase0.py", "--regression")
        ):
            raise ValueError("Phase 1 gate requires E2E and foundation regression evidence")
        if phase == 23 and (
            not includes("scripts/verify_phase1.py")
            or not includes("scripts/e2e_stack.py", "--run")
            or not includes("scripts/dev/migration_order_check.py")
        ):
            raise ValueError("Phase 23 gate requires Phase 1, E2E --run and both migration orders")
        if phase == 23:
            evidence_root = (root / ".local").resolve()
            if not evidence_root.is_relative_to(root.resolve()):
                raise ValueError("Phase 23 log evidence escapes the worktree")
            for check in checks:
                name, digest = check.get("log"), check.get("log_sha256")
                if not isinstance(name, str) or not isinstance(digest, str):
                    raise ValueError("Phase 23 requires recorded command log evidence")
                log = (root / name).resolve()
                if Path(name).is_absolute() or not log.is_relative_to(evidence_root):
                    raise ValueError("Phase 23 log evidence escapes the worktree")
                if (
                    not re.fullmatch(r"[0-9a-f]{64}", digest)
                    or not log.is_file()
                    or hashlib.sha256(log.read_bytes()).hexdigest() != digest
                ):
                    raise ValueError("Phase 23 command log evidence is missing or changed")


def is_generated_runtime_url(database_url: str) -> bool:
    return urlsplit(database_url).username in {"moodprint_api", f"moodprint_api.{PROJECT_REF}"}


def validate_hosted_target(supabase_url: str, database_url: str) -> None:
    """Require the exact audited project in both API and database endpoints."""
    api = urlsplit(supabase_url)
    db = urlsplit(database_url.replace("postgresql+asyncpg://", "postgresql://", 1))
    expected_api = f"{PROJECT_REF}.supabase.co"
    if api.scheme != "https" or api.hostname != expected_api or api.path not in {"", "/"}:
        raise ValueError("Hosted API target does not match the audited project")
    direct = db.hostname == f"db.{PROJECT_REF}.supabase.co"
    pooler = (db.hostname or "").endswith(
        ".pooler.supabase.com"
    ) and db.username == f"postgres.{PROJECT_REF}"
    if db.scheme not in {"postgres", "postgresql"} or not (direct or pooler):
        raise ValueError("Hosted database target does not match the audited project")
    if db.username not in {"postgres", f"postgres.{PROJECT_REF}"}:
        raise ValueError("Hosted migration connection must use the privileged postgres role")
    if not db.password:
        raise ValueError("SUPABASE_DB_URL must include its database password")


def load_hosted_env() -> dict[str, str]:
    from dotenv import dotenv_values

    values = {key: value for key, value in dotenv_values(ROOT / ".env").items() if value}
    values.update({key: value for key, value in os.environ.items() if value})
    # Older owner environments used DATABASE_URL for the privileged connection.
    # Adapt only in memory; runtime must continue to reject the postgres role,
    # and provisioning must never overwrite this owner-supplied value.
    if not values.get("SUPABASE_DB_URL") and values.get("DATABASE_URL"):
        candidate = values["DATABASE_URL"]
        parsed = urlsplit(candidate.replace("postgresql+asyncpg://", "postgresql://", 1))
        if parsed.username in {"postgres", f"postgres.{PROJECT_REF}"}:
            values["SUPABASE_DB_URL"] = candidate
    for key in ("SUPABASE_URL", "SUPABASE_DB_URL"):
        if not values.get(key):
            raise ValueError(f"Missing {key}")
    validate_hosted_target(values["SUPABASE_URL"], values["SUPABASE_DB_URL"])
    return values


def write_generated_database_url(path: Path, database_url: str, *, rotate: bool = False) -> None:
    """Touch only DATABASE_URL; preserve every owner supplied line verbatim."""
    original = path.read_text(encoding="utf-8") if path.exists() else ""
    pattern = re.compile(r"^(?:export\s+)?DATABASE_URL\s*=.*$", re.MULTILINE)
    matches = pattern.findall(original)
    if len(matches) > 1:
        raise ValueError("Duplicate DATABASE_URL entries; resolve before provisioning")
    if matches:
        current = matches[0].split("=", 1)[1].strip().strip("'\"")
        if current and rotate and not is_generated_runtime_url(current):
            raise ValueError("Existing DATABASE_URL is owner supplied; it cannot be overwritten")
        if current and not rotate:
            raise ValueError(
                "DATABASE_URL already exists; use --rotate to replace generated credentials"
            )
    line = f'DATABASE_URL="{database_url}"'
    result = (
        pattern.sub(lambda _: line, original)
        if matches
        else original + ("\n" if original and not original.endswith("\n") else "") + line + "\n"
    )
    temp = path.with_name(path.name + ".moodprint-tmp")
    temp.write_text(result, encoding="utf-8")
    temp.replace(path)


def committed_migrations(root: Path = ROOT) -> list[Path]:
    """Refuse untracked, modified, renamed, or missing deployment migrations."""
    result = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", "HEAD", "--", "supabase/migrations"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    committed = set(result.stdout.splitlines())
    actual = {p.relative_to(root).as_posix() for p in (root / "supabase/migrations").glob("*.sql")}
    if actual != committed or not actual:
        raise ValueError(
            "Migration files must exactly match the current commit before hosted deployment"
        )
    for name in sorted(actual):
        path = root / name
        stored = subprocess.run(
            ["git", "show", f"HEAD:{name}"], cwd=root, capture_output=True, check=True
        ).stdout
        if stored.replace(b"\r\n", b"\n") != path.read_bytes().replace(b"\r\n", b"\n"):
            raise ValueError(f"Uncommitted migration changes: {path.name}")
    paths = [root / name for name in sorted(actual)]
    check_history(paths, [])
    return paths


def check_history(paths: list[Path], applied: list[tuple[str, str]]) -> list[Path]:
    pattern = re.compile(r"^(\d{14})_(f0|f1|kb|ag)_[a-z0-9_]+\.sql$")
    for path in paths:
        if not pattern.fullmatch(path.name):
            raise ValueError(f"Invalid migration filename: {path.name}")
        try:
            datetime.strptime(path.name[:14], "%Y%m%d%H%M%S")
        except ValueError:
            raise ValueError(f"Invalid migration timestamp: {path.name}") from None
    counts = Counter(path.name[:14] for path in paths)
    if any(count > 1 for count in counts.values()):
        raise ValueError("Duplicate migration version")
    if any(
        not isinstance(row, (tuple, list))
        or len(row) != 2
        or not all(isinstance(value, str) for value in row)
        for row in applied
    ):
        raise ValueError("Malformed hosted migration history")
    versions = [version for version, _ in applied]
    if len(set(versions)) != len(versions) or versions != sorted(versions):
        raise ValueError("Duplicate or disordered hosted migration history")
    local = {path.name[:14]: path for path in paths}
    for version, name in applied:
        if version not in local or local[version].stem.split("_", 1)[1] != name:
            raise ValueError("Hosted migration history differs from the current commit")
    done = {version for version, _ in applied}
    return [
        path for path in sorted(paths, key=lambda path: path.name) if path.name[:14] not in done
    ]


def deployment_plan(
    root: Path, head: str, pending: list[Path], history: list[tuple[str, str]]
) -> dict:
    """Only committed SQL hashes/provenance and catalog names enter this receipt."""
    entries = []
    for path in pending:
        relative = path.relative_to(root).as_posix()
        blob = subprocess.run(
            ["git", "show", f"{head}:{relative}"], cwd=root, capture_output=True, check=True
        ).stdout
        introduced = subprocess.run(
            ["git", "log", "--diff-filter=A", "--format=%H", "--reverse", head, "--", relative],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.splitlines()
        if not introduced or not re.fullmatch(r"[0-9a-f]{40}", introduced[0]):
            raise ValueError("Migration introducing commit could not be verified")
        entries.append(
            {
                "path": relative,
                "version": path.name[:14],
                "name": path.stem[15:],
                "sha256": hashlib.sha256(blob).hexdigest(),
                "introducing_commit": introduced[0],
            }
        )
    return {
        "version": 1,
        "project_ref": PROJECT_REF,
        "head": head,
        "history": [[version, name] for version, name in history],
        "pending": entries,
        "provenance": {
            "migration_source": "git:HEAD",
            "cli_version": CLI_VERSION,
            "history_source": "supabase_migrations.schema_migrations",
        },
    }


def dry_run_receipt_path(root: Path) -> Path:
    return root / ".local/hosted-migration-dry-run.json"


def write_dry_run_receipt(root: Path, plan: dict, *, cli_dry_run: bool) -> None:
    path = dry_run_receipt_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps({**plan, "passed": True, "cli_dry_run": cli_dry_run}, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def require_dry_run_receipt(root: Path, plan: dict, *, cli_dry_run: bool) -> None:
    try:
        receipt = json.loads(dry_run_receipt_path(root).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise ValueError("A matching prior dry-run receipt is required") from None
    if receipt != {**plan, "passed": True, "cli_dry_run": cli_dry_run}:
        raise ValueError(
            "Prior dry-run receipt does not match HEAD, project, history or pending committed migrations"
        )
