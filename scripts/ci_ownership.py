"""Select phase from the actual GitHub head branch; policy comes from an ancestor tag."""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

try:
    from scripts.check_ownership import (
        POLICY,
        ROOT,
        CheckError,
        baseline_text,
        resolve_base,
        validate_policy,
        violations,
    )
except ModuleNotFoundError:
    from check_ownership import (
        POLICY,
        ROOT,
        CheckError,
        baseline_text,
        resolve_base,
        validate_policy,
        violations,
    )


BRANCHES = {"feat/knowledge-base": "2", "feat/agent-companion": "3"}
RETIRED = "feat/knowledge-ingestion-rag"


def normalize_branch(branch: str) -> str:
    # Disposable GitHub refs exercise the same event-based selector without
    # reserving or creating the owner's final feature branches.
    canary = re.fullmatch(r"canary/ownership/(knowledge-base|agent-companion)/[a-z0-9-]+", branch)
    return "feat/" + canary[1] if canary else branch


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--repo", type=Path, default=ROOT)
    parser.add_argument("--local", action="store_true")
    parser.add_argument(
        "--migrations", action="store_true", help="Run SQL scope after ownership passes"
    )
    args = parser.parse_args(argv)
    branch = normalize_branch(args.branch)
    if branch == RETIRED:
        print("retired branch name; rename to feat/knowledge-base", file=sys.stderr)
        return 2
    if branch not in BRANCHES:
        print(f"no ownership profile for {args.branch}")
        return 0
    try:
        base = resolve_base(args.repo, args.head)
        policy = json.loads(baseline_text(args.repo, base, POLICY))
        validate_policy(policy)
        phase = policy["branches"][branch]
        paths, errors = violations(
            args.repo, base, phase, policy, head=None if args.local else args.head
        )
    except (CheckError, ValueError, KeyError, TypeError, OSError) as error:
        print(
            "Ownership check unavailable: "
            + (str(error) if isinstance(error, CheckError) else "invalid baseline input"),
            file=sys.stderr,
        )
        return 2
    for error in errors:
        print(error)
    print(
        f"ownership {'FAIL' if errors else 'PASS'} branch={args.branch} profile={branch} phase={phase} head={args.head} base={base} paths={len(paths)}"
    )
    if not errors and args.migrations:
        return subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/dev/migration_scope_check.py"),
                "--branch",
                branch,
                "--root",
                str(args.repo),
            ],
            check=False,
        ).returncode
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
