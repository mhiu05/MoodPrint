"""Execute the complete local Phase 2/3 gate and issue an exact-commit receipt.

Never loads the root dotenv or accepts a hosted URL. All database resets belong
to a named isolated local stack. Paid provider credentials are never inherited.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from e2e_stack import OS_ENVIRONMENT, build_environment, read_local_environment

ROOT = Path(__file__).resolve().parents[1]


def clean_head(root: Path) -> str:
    status = subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=all"], cwd=root, text=True
    )
    if status.strip():
        raise ValueError("Phase 23 requires a clean committed source tree")
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()


def check_plan(name: str, offset: int) -> list[list[str]]:
    python = sys.executable
    stack = ["--name", name, "--offset", str(offset)]
    return [
        [python, "scripts/dev/migration_scope_check.py"],
        [python, "scripts/dev/supabase_worktree.py", "start", *stack, "--lite"],
        [python, "scripts/dev/bootstrap_local_db.py", *stack],
        [python, "scripts/verify_phase1.py"],
        [python, "scripts/dev/migration_order_check.py"],
        # Both migration orders restore and reset the chronological local copy.
        [python, "scripts/dev/bootstrap_local_db.py", *stack],
        [python, "scripts/dev/supabase_worktree.py", "test", *stack],
        [python, "-m", "pytest", "-m", "integration", "-q", "-rA"],
        [python, "-m", "pytest", "agent/tests", "-q"],
        [python, "scripts/export_contract_schemas.py", "--check"],
        [python, "scripts/export_openapi.py", "--check"],
        [python, "scripts/e2e_stack.py", "--run", "--project", "demo"],
        [python, "scripts/e2e_stack.py", "--run", "--project", "real"],
    ]


def run_command(command: list[str], cwd: Path, environment: dict[str, str], log: Path) -> int:
    with log.open("w", encoding="utf-8") as handle:
        return subprocess.run(
            command, cwd=cwd, env=environment, stdout=handle, stderr=subprocess.STDOUT, check=False
        ).returncode


def verify(root: Path, name: str, offset: int) -> int:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,39}", name) or not 1 <= offset <= 9000:
        raise ValueError("Phase 23 requires a named isolated stack with offset 1..9000")
    local = root / ".local"
    local.mkdir(parents=True, exist_ok=True)
    receipt = local / "phase23-gate.json"
    lock = local / "phase23-gate.lock"
    try:
        lock.mkdir()
    except FileExistsError:
        raise ValueError("Another Phase 23 gate owns this worktree") from None
    try:
        receipt.unlink(missing_ok=True)
        head = clean_head(root)
        output = local / f"verification/phase23-{name}-{offset}"
        output.mkdir(parents=True, exist_ok=True)
        environment_file = local / f"stacks/{name}/test.env"
        base = {k: v for k, v in os.environ.items() if k.upper() in OS_ENVIRONMENT}
        base.update(APP_ENV="test", MOODPRINT_STACK_NAME=name, MOODPRINT_PORT_OFFSET=str(offset))
        history = []
        checks = check_plan(name, offset)
        for index, command in enumerate(checks, 1):
            if clean_head(root) != head:
                raise ValueError("Source commit changed during Phase 23 verification")
            environment = (
                build_environment(read_local_environment(environment_file), base)
                if environment_file.exists()
                else base.copy()
            )
            if index >= 4 and not environment_file.exists():
                raise ValueError("Local bootstrap did not create its isolated test environment")
            log = output / f"check-{index:02d}.log"
            started = datetime.now(UTC).isoformat()
            print(f"Phase 23 {index}/{len(checks)}: {' '.join(command)}", flush=True)
            code = run_command(command, root, environment, log)
            history.append(
                {
                    "command": command,
                    "returncode": code,
                    "log": log.relative_to(root).as_posix(),
                    "log_sha256": hashlib.sha256(log.read_bytes()).hexdigest(),
                    "started_at": started,
                    "finished_at": datetime.now(UTC).isoformat(),
                }
            )
            status = {
                "commit": head,
                "scope": "local_phase23",
                "passed": False,
                "checks": history,
                "stack": name,
                "offset": offset,
            }
            (output / "status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
            if code:
                print(f"FAILED: see {log.relative_to(root)}", flush=True)
                return code
        if clean_head(root) != head:
            raise ValueError("Source commit changed during Phase 23 verification")
        status.update(passed=True, timestamp=datetime.now(UTC).isoformat())
        temporary = receipt.with_suffix(".tmp")
        temporary.write_text(json.dumps(status, indent=2), encoding="utf-8")
        temporary.replace(receipt)
        print("VERIFIED: local Phase 23 only; hosted dry-run and apply remain separate.")
        return 0
    finally:
        lock.rmdir()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default="fresh-bootstrap")
    parser.add_argument("--offset", type=int, default=400)
    args = parser.parse_args()
    try:
        return verify(ROOT, args.name, args.offset)
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"Phase 23 failed: {type(exc).__name__}; no passing receipt issued.\n")


if __name__ == "__main__":
    raise SystemExit(main())
