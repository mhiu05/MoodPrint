"""Run the complete local Phase 1 gate; hosted smoke remains a separate gate."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime

from e2e_stack import ROOT, build_environment, read_local_environment


def main() -> int:
    environment = build_environment(
        read_local_environment(ROOT / ".local/test.env"), dict(os.environ)
    )
    npm = "npm.cmd" if os.name == "nt" else "npm"
    checks = [
        ([sys.executable, "scripts/verify_phase0.py", "--regression"], ROOT),
        # The foundation gate bootstraps a fresh test.env after its local reset.
        *[
            ([npm, "run", script], ROOT / "frontend")
            for script in ("typecheck", "lint", "format:check")
        ],
        ([npm, "test", "--", "--maxWorkers=2"], ROOT / "frontend"),
        *[([npm, "run", script], ROOT / "frontend") for script in ("build", "check:boundaries")],
        ([sys.executable, "scripts/e2e_stack.py", "--run", "--project", "demo"], ROOT),
        ([sys.executable, "scripts/e2e_stack.py", "--run", "--project", "real"], ROOT),
    ]
    output = ROOT / ".local/verification"
    output.mkdir(parents=True, exist_ok=True)
    receipt = ROOT / ".local/phase1-gate.json"
    receipt.unlink(missing_ok=True)
    history = []
    for index, (command, cwd) in enumerate(checks):
        # Bootstrap may rotate the local role password. Never reuse its previous value.
        environment = build_environment(
            read_local_environment(ROOT / ".local/test.env"), dict(os.environ)
        )
        print(
            f"Running local Phase 1 checkpoint {index + 1}/{len(checks)}: {' '.join(command)}",
            flush=True,
        )
        log = output / f"phase1-{index + 1}.log"
        with log.open("w", encoding="utf-8") as handle:
            result = subprocess.run(
                command,
                cwd=cwd,
                env=environment,
                stdout=handle,
                stderr=subprocess.STDOUT,
                check=False,
            )
        history.append(
            {
                "command": command,
                "returncode": result.returncode,
                "log": log.relative_to(ROOT).as_posix(),
            }
        )
        if result.returncode:
            print(f"FAILED: see {log.relative_to(ROOT)}", flush=True)
            return result.returncode
    changed = subprocess.check_output(
        ["git", "diff", "--name-only", "--", "docs/prototype/screenshots"], cwd=ROOT, text=True
    )
    if changed.strip():
        print("FAILED: tracked prototype screenshots changed during E2E")
        return 1
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    receipt.write_text(
        json.dumps(
            {
                "commit": sha,
                "passed": True,
                "scope": "local_phase1",
                "timestamp": datetime.now(UTC).isoformat(),
                "checks": history,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        "VERIFIED: local Phase 1 gate. Hosted migration, smoke and advisor checks remain separate."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
