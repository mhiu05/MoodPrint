"""Live tests refuse to run (exit 3) without an owner-approved budget and a key."""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_live_suite_refuses_without_budget_or_key(tmp_path: Path) -> None:
    env = {k: v for k, v in os.environ.items() if k != "OPENAI_API_KEY"}
    env["SAFEVOICE_EVAL_BUDGET"] = str(tmp_path / "absent-budget.json")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-m",
            "live_agent",
            "agent/tests/live",
            "-q",
            "-p",
            "no:cacheprovider",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 3, result.stdout[-400:]
    assert "BLOCKED" in result.stdout + result.stderr
