"""Run local G0 prerequisites and record evidence. Hosted checks remain a separate gate."""

import argparse
import json
import os
import socket
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from e2e_stack import build_environment, read_local_environment

ROOT = Path(__file__).resolve().parents[1]
CLI_VERSION = "2.122.1"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="1a3c81fca5d5c43bf910aa9ff5f971a4a669bab5")
    parser.add_argument(
        "--regression",
        action="store_true",
        help="Recheck the foundation after Phase 1; omit the historical frontend-unchanged assertion",
    )
    args = parser.parse_args()
    # The gate resets the local database. Refuse while E2E owns the local API/Vite.
    for port in (8008, 5178):
        with socket.socket() as connection:
            if connection.connect_ex(("127.0.0.1", port)) == 0:
                print("FAILED: stop the E2E stack before the foundation gate resets local data")
                return 1
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
        # Bound jsdom workers on shared developer machines; preserve test timeouts
        # and assertions while avoiding CPU contention between 13 environments.
        ([npm, "test", "--", "--maxWorkers=2"], ROOT / "frontend"),
    ]
    history = []
    output_dir = ROOT / ".local/verification"
    output_dir.mkdir(parents=True, exist_ok=True)
    for index, (command, cwd) in enumerate(checks):
        local_file = ROOT / ".local/test.env"
        child_environment = (
            build_environment(read_local_environment(local_file), dict(os.environ))
            if local_file.exists()
            else {**os.environ, "APP_ENV": "test"}
        )
        print(
            f"Running local checkpoint {index + 1}/{len(checks)}: {' '.join(command)}", flush=True
        )
        log = output_dir / f"phase0-{index + 1}.log"
        with log.open("w", encoding="utf-8") as handle:
            result = subprocess.run(
                command,
                cwd=cwd,
                env=child_environment,
                stdout=handle,
                stderr=subprocess.STDOUT,
                check=False,
            )
        history.append({"command": command, "returncode": result.returncode})
        if result.returncode:
            print(f"FAILED: see {log.relative_to(ROOT)}")
            return result.returncode
    if (
        not args.regression
        and subprocess.check_output(
            ["git", "diff", "--name-only", args.base, "--", "frontend"], cwd=ROOT, text=True
        ).strip()
    ):
        print("FAILED: frontend changed during Phase 0")
        return 1
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    # This is a local-prerequisite receipt, never a claim that hosted G0 has passed.
    receipt = {
        "commit": sha,
        "passed": True,
        "scope": "foundation-regression" if args.regression else "local",
        "timestamp": datetime.now(UTC).isoformat(),
        "checks": history,
    }
    receipt_name = "phase0-regression-gate.json" if args.regression else "phase0-gate.json"
    (ROOT / ".local" / receipt_name).write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(
        "VERIFIED: foundation regression; this receipt does not authorize hosted migration."
        if args.regression
        else "VERIFIED: local G0 prerequisites. Hosted configuration, S-05 and smoke evidence are still required for G0."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
