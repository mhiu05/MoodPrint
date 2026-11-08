"""Local pre-branch gate.

The receipt records commands and exit codes for this worktree HEAD. It does not
certify GitHub Actions, ownership canaries, the preparation merge, the target
SHA, or baseline/phase-2-3-start. Two-stack and hosted checks stay outside this
process: this script does not start a second Supabase stack and does not call
the hosted database.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / ".local" / "prebranch-gate.json"


def git(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError("git " + " ".join(args) + " failed")
    return result.stdout.strip()


def main() -> int:
    head = git("rev-parse", "HEAD")
    ignored_exact = {
        ".claude/settings.local.json",
        ".cursor/mcp.json",
        ".mcp.json",
        "debug.log",
    }
    ignored_prefixes = (".local/", ".playwright-mcp/", "supabase/.branches/")
    dirty = []
    for line in git("status", "--porcelain").splitlines():
        path = line[3:].strip().split(" -> ")[-1].strip().replace("\\", "/")
        if (
            path in ignored_exact
            or path.startswith(ignored_prefixes)
            or "/__pycache__/" in f"/{path}"
            or path.endswith(".pyc")
        ):
            continue
        dirty.append(path)
    checks = [
        [sys.executable, "-m", "pytest", "scripts/tests", "scripts/db/tests", "-q"],
        [sys.executable, "scripts/dev/migration_scope_check.py", "--branch", "feat/knowledge-base"],
        [
            sys.executable,
            "scripts/dev/migration_scope_check.py",
            "--branch",
            "feat/agent-companion",
        ],
        [sys.executable, "scripts/dev/migration_order_check.py", "--self-test"],
        [sys.executable, "scripts/export_contract_schemas.py", "--check"],
        [sys.executable, "scripts/export_openapi.py", "--check"],
        [sys.executable, "scripts/verify_phase1.py"],
    ]
    history: list[dict[str, object]] = []
    failed = False
    for command in checks:
        print("PREBRANCH " + " ".join(command), flush=True)
        result = subprocess.run(command, cwd=ROOT, check=False)
        history.append({"command": command, "returncode": result.returncode})
        if result.returncode:
            failed = True
            break
    receipt = {
        "scope": "local_prebranch",
        "commit": head,
        "dirty_paths": dirty,
        "passed": not failed and not dirty,
        "finished_at": datetime.now(UTC).isoformat(),
        "checks": history,
        "not_certified": [
            "github_actions",
            "ownership_canaries",
            "pull_request_merge",
            "target_sha",
            "baseline_tag",
            "two_stack",
            "hosted_apply",
        ],
    }
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {RECEIPT.relative_to(ROOT).as_posix()} passed={receipt['passed']}")
    if dirty:
        print("Worktree has uncommitted paths outside .local; receipt is not a clean SHA gate.")
    return 1 if failed or dirty else 0


if __name__ == "__main__":
    raise SystemExit(main())
