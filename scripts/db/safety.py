"""Shared guardrails for the two explicit hosted-operation scripts."""

from __future__ import annotations

import json
import os
import re
import subprocess
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
    expected_scope = "local_phase1" if phase == 1 else "local"
    checks = receipt.get("checks", [])
    if (
        receipt.get("commit") != head
        or receipt.get("passed") is not True
        or receipt.get("scope") != expected_scope
        or len(checks) < 8
        or any(check.get("returncode") != 0 for check in checks)
    ):
        raise ValueError(f"A passing local Phase {phase} gate receipt for HEAD is required")
    if phase == 1:
        commands = [check.get("command", []) for check in checks]

        def includes(script: str, option: str) -> bool:
            return any(
                option in command
                and any(str(arg).replace("\\", "/").endswith(script) for arg in command)
                for command in commands
            )

        if not includes("scripts/e2e_stack.py", "--run") or not includes(
            "scripts/verify_phase0.py", "--regression"
        ):
            raise ValueError("Phase 1 gate requires E2E and foundation regression evidence")


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
    return [root / name for name in sorted(actual)]


def check_history(paths: list[Path], applied: list[tuple[str, str]]) -> list[Path]:
    local = {path.name.split("_", 1)[0]: path for path in paths}
    for version, name in applied:
        if version not in local or local[version].stem.split("_", 1)[1] != name:
            raise ValueError("Hosted migration history differs from the current commit")
    done = {version for version, _ in applied}
    return [path for path in paths if path.name.split("_", 1)[0] not in done]
