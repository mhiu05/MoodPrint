"""Free safety re-evaluation with exact source/dataset hashes and baseline outcome deltas.

    uv run python agent/evals/safety_closure.py --baseline-sha <SHA> --out <new-file.json>

Does not import paid-evaluation clients, load secrets or change historical results.
"""

import argparse
import hashlib
import json
import subprocess
import sys
import types
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evals import safety_eval

ROOT = Path(__file__).resolve().parents[2]
SOURCES = (
    "agent/src/moodprint_agent/tools/safety.py",
    "agent/src/moodprint_agent/tools/risk_assessor.py",
    "agent/src/moodprint_agent/runtime.py",
    "agent/evals/safety_eval.py",
    "agent/evals/safety_closure.py",
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-sha", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("output already exists; preserve previous evidence and choose a new path")
    baseline_sha = subprocess.check_output(
        ["git", "rev-parse", args.baseline_sha], cwd=ROOT, text=True
    ).strip()
    original = subprocess.check_output(["git", "show", f"{baseline_sha}:{SOURCES[0]}"], cwd=ROOT)
    baseline = types.ModuleType("_safety_closure_baseline")
    sys.modules[baseline.__name__] = baseline
    exec(
        compile(original.decode("utf-8"), f"{baseline_sha}:{SOURCES[0]}", "exec"), baseline.__dict__
    )
    classifier = safety_eval.assess_conversation
    files = sorted(safety_eval.CASE_DIR.glob("safety*.jsonl"))
    results = {}
    for path in files:
        cases = safety_eval.load(path)
        ids = [case["id"] for case in cases]
        if len(ids) != len(set(ids)) or any(
            case["expected"] not in safety_eval.LEVELS for case in cases
        ):
            raise ValueError(f"invalid labels or duplicate ids: {path.name}")
        old = [baseline.assess_conversation(case["turns"]).level for case in cases]
        now = [classifier(case["turns"]).level for case in cases]
        safety_eval.assess_conversation = baseline.assess_conversation
        previous = safety_eval.evaluate(cases)
        safety_eval.assess_conversation = classifier
        current = safety_eval.evaluate(cases)
        results[path.stem] = {
            "dataset_sha256_lf": digest(path.read_bytes()),
            "provenance": "synthetic; implementer-authored or previously inspected model-authored; not independent; no human labels",
            "baseline": previous,
            "current": current,
            "changed_outcomes": [
                {
                    "id": case["id"],
                    "expected": case["expected"],
                    "before": a,
                    "after": b,
                    "turns": case["turns"],
                }
                for case, a, b in zip(cases, old, now, strict=True)
                if a != b
            ],
        }
    hashes = {path: digest((ROOT / path).read_bytes()) for path in SOURCES}
    report = {
        "created_at_utc": datetime.now(UTC).isoformat(),
        "git_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "baseline_sha": baseline_sha,
        "baseline_detector_sha256_lf": digest(original),
        "source_sha256_lf": hashes,
        "source_bundle_sha256": hashlib.sha256(
            json.dumps(hashes, sort_keys=True).encode()
        ).hexdigest(),
        "source_state": "working tree; exact normalized source hashes above, not a committed tree claim",
        "mode": "offline deterministic; zero provider calls",
        "Q3-03": "NOT_DEMONSTRATED",
        "targets_unchanged": {"recall_immediate": 0.95, "benign_fpr_immediate": 0.10},
        "interval_method": "two-sided Wilson 95%; small synthetic samples, no population generalization",
        "results": results,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for name, value in results.items():
        r = value["current"]
        print(
            f"{name}: n={r['n']} recall={r['recall_immediate']} FPR={r['false_positive_rate_immediate']} exact={r['exact_level_accuracy']}"
        )


if __name__ == "__main__":
    main()
