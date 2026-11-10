"""Run the reproducible offline quality gate from any working directory."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    checks = [
        ["ruff", "check", "shared", "agent", "backend", "scripts"],
        ["ruff", "format", "--check", "shared", "agent", "backend", "scripts"],
        ["pyright"],
        ["lint-imports", "--no-cache"],
        [sys.executable, "-m", "pytest", "-q"],
    ]
    for command in checks:
        print(f"Running: {' '.join(command)}", flush=True)
        result = subprocess.run(command, cwd=ROOT, check=False)
        if result.returncode:
            return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
