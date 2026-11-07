"""Run local G0 prerequisites and record evidence. Hosted checks remain a separate gate."""

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI_VERSION = "2.122.1"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="1a3c81fca5d5c43bf910aa9ff5f971a4a669bab5")
    args = parser.parse_args()
    npx = "npx.cmd" if os.name == "nt" else "npx"
    npm = "npm.cmd" if os.name == "nt" else "npm"
    checks = [
        ([sys.executable, "scripts/check.py"], ROOT),
        ([sys.executable, "scripts/export_contract_schemas.py", "--check"], ROOT),
        ([sys.executable, "scripts/export_openapi.py", "--check"], ROOT),
        ([npx, "--yes", f"supabase@{CLI_VERSION}", "db", "reset", "--local"], ROOT),
        ([sys.executable, "scripts/dev/bootstrap_local_db.py"], ROOT),
        ([npx, "--yes", f"supabase@{CLI_VERSION}", "test", "db"], ROOT),
        ([sys.executable, "-m", "pytest", "-m", "integration", "-q", "-rA"], ROOT),
        ([npm, "test"], ROOT / "frontend"),
    ]
    history = []
    output_dir = ROOT / ".local/verification"
    output_dir.mkdir(parents=True, exist_ok=True)
    for index, (command, cwd) in enumerate(checks):
        print(
            f"Running local checkpoint {index + 1}/{len(checks)}: {' '.join(command)}", flush=True
        )
        log = output_dir / f"phase0-{index + 1}.log"
        with log.open("w", encoding="utf-8") as handle:
            result = subprocess.run(
                command, cwd=cwd, stdout=handle, stderr=subprocess.STDOUT, check=False
            )
        history.append({"command": command, "returncode": result.returncode})
        if result.returncode:
            print(f"FAILED: see {log.relative_to(ROOT)}")
            return result.returncode
    if subprocess.check_output(
        ["git", "diff", "--name-only", args.base, "--", "frontend"], cwd=ROOT, text=True
    ).strip():
        print("FAILED: frontend changed during Phase 0")
        return 1
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    # This is a local-prerequisite receipt, never a claim that hosted G0 has passed.
    receipt = {
        "commit": sha,
        "passed": True,
        "scope": "local",
        "timestamp": datetime.now(UTC).isoformat(),
        "checks": history,
    }
    (ROOT / ".local/phase0-gate.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(
        "VERIFIED: local G0 prerequisites. Hosted configuration, S-05 and smoke evidence are still required for G0."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
