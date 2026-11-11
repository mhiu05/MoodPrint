"""Read-only live-evaluation readiness; plans never grant permission to spend.

uv run python agent/evals/readiness.py --out agent/evals/plans/quality-closure
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evals.cases_io import Case, load_cases
from evals.provenance import build_manifest, compare, file_hash, reconcile
from evals.s06_mechanisms import build_plan, compare_mechanisms
from safevoice_shared.config import AppConfig

RESULTS = Path(__file__).resolve().parent / "results"


def request_bound(case: Case, *, max_turns: int) -> int:
    if case.suite == "screenshot":
        return 1
    if case.suite == "roleplay":
        return len(case.turns) + 1  # partner has no tools; one coach
    return (len(case.turns) + len(case.expect.approvals)) * max_turns


def budget_evidence(budget_path: Path, ledger_path: Path) -> dict[str, Any]:
    """Reconstruct only; never instantiate BudgetLedger (it creates files/locks)."""
    if not budget_path.is_file() or not ledger_path.is_file():
        return {"status": "BLOCKED", "reason": "existing cumulative budget/ledger missing"}
    budget = json.loads(budget_path.read_text(encoding="utf-8"))
    entries = {}
    for line in ledger_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        key = row.get("id")
        kind = row.get("kind")
        if kind == "reserve":
            entries[key] = {"tokens": row["tokens"], "usd": row["usd"], "state": "reserved"}
        elif key in entries and kind == "reconcile":
            entries[key].update(tokens=row["tokens"], usd=row["usd"], state="reconciled")
        elif key in entries and kind == "unknown":
            entries[key]["state"] = "unknown"
    fields = (
        "model",
        "max_usd",
        "max_tokens_total",
        "max_tokens_per_run",
        "max_calls_total",
        "max_output_tokens_per_request",
        "scopes",
        "expires_on",
        "pricing",
    )
    return {
        "status": "BLOCKED",
        "reason": "no paid execution authorized; cumulative call cap exhausted",
        "budget_sha256": hashlib.sha256(budget_path.read_bytes()).hexdigest(),
        "ledger_sha256": hashlib.sha256(ledger_path.read_bytes()).hexdigest(),
        "approved_limits": {k: budget.get(k) for k in fields},
        "calls": len(entries),
        "committed_usd": round(sum(r["usd"] for r in entries.values()), 8),
        "spent_tokens": sum(r["tokens"] for r in entries.values() if r["state"] == "reconciled"),
        "held_tokens": sum(r["tokens"] for r in entries.values() if r["state"] != "reconciled"),
        "unknown_calls": sum(r["state"] == "unknown" for r in entries.values()),
    }


def read_rows(path: Path) -> list[dict[str, Any]]:
    return (
        [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if path.is_file()
        else []
    )


def audit(base: Path) -> dict[str, Any]:
    manifest_path = base / "manifest.json"
    if not manifest_path.is_file() or "provenance_id" not in json.loads(
        manifest_path.read_text(encoding="utf-8")
    ):
        config = (
            json.loads((base / "config.json").read_text(encoding="utf-8"))
            if (base / "config.json").is_file()
            else {}
        )
        return {
            "status": "NOT_VERIFIED",
            "reason": "LEGACY_UNATTRIBUTABLE: no pinned manifest/prompt hashes",
            "historical_prompt_version": config.get("prompt_version"),
            "credited_current_slots": 0,
        }
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    result = reconcile(
        manifest,
        read_rows(base / "outputs.jsonl"),
        read_rows(base / "assertions.jsonl"),
        read_rows(base / "grades.jsonl"),
    )
    result["artifact_sha256"] = {
        p.name: file_hash(p)
        for p in base.iterdir()
        if p.name
        in (
            "config.json",
            "manifest.json",
            "outputs.jsonl",
            "assertions.jsonl",
            "grades.jsonl",
            "usage.json",
        )
    }
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--budget", type=Path, default=Path(".local/eval-budget.json"))
    parser.add_argument("--ledger", type=Path, default=Path(".local/eval-spend.jsonl"))
    parser.add_argument("--corpus-version", default="UNPUBLISHED-QUALITY-CLOSURE")
    parser.add_argument("--corpus-sha256", default="")
    parser.add_argument("--audit", type=Path)
    parser.add_argument(
        "--s06-replay", type=Path, help="directory with plan.json, outputs.jsonl, grades.jsonl"
    )
    parser.add_argument("--compare", nargs=2, type=Path)
    args = parser.parse_args(argv)
    if args.s06_replay:
        base = args.s06_replay
        plan = json.loads((base / "plan.json").read_text(encoding="utf-8"))
        report = compare_mechanisms(
            plan, read_rows(base / "outputs.jsonl"), read_rows(base / "grades.jsonl")
        )
        print(json.dumps(report, indent=2))
        return 0 if report["status"] == "VERIFIED_EVIDENCE" else 1
    if args.audit:
        report = audit(args.audit)
        print(json.dumps(report, indent=2))
        return 0 if report["status"] == "VERIFIED_EVIDENCE" else 1
    if args.compare:
        a, b = args.compare
        if not (a / "manifest.json").is_file() or not (b / "manifest.json").is_file():
            print("NOT_COMPARABLE: legacy run has no pinned manifest")
            return 1
        ma, mb = [json.loads((p / "manifest.json").read_text(encoding="utf-8")) for p in (a, b)]
        if "provenance_id" not in ma or "provenance_id" not in mb:
            print("NOT_COMPARABLE: legacy manifest has no provenance")
            return 1
        result = compare(ma, audit(a), mb, audit(b))
        print(json.dumps(result, indent=2))
        return 0 if result["comparable"] else 1
    if args.out is None:
        parser.error("--out, --audit or --compare is required")
    args.out.mkdir(parents=True, exist_ok=True)
    cfg = AppConfig()
    cases = load_cases()
    plans = {
        "final-fixture": build_manifest(cases, repeat=3),
        "real-knowledge": build_manifest(
            load_cases("knowledge"),
            repeat=3,
            retriever="real",
            corpus_version=args.corpus_version,
            corpus_sha256=args.corpus_sha256,
        ),
        "s06-mechanisms": build_plan(),
    }
    bounds = {
        "final-fixture": sum(request_bound(c, max_turns=cfg.agent.max_turns) * 3 for c in cases),
        "real-knowledge": sum(
            request_bound(c, max_turns=cfg.agent.max_turns) * 3 for c in load_cases("knowledge")
        ),
        "s06-mechanisms": plans["s06-mechanisms"]["max_requests"],
    }
    # Conservative short-context snapshot from the original approved budget, not a new price approval.
    input_cap, output_cap = 272000, 4096
    estimate = {
        "status": "BLOCKED",
        "planned_slots": sum(len(p["slots"]) for p in plans.values()),
        "requests_max_by_plan": bounds,
        "requests_max": sum(bounds.values()),
        "tokens_max": sum(len(p["slots"]) for p in plans.values()) * 60000,
        "request_cap_tokens_envelope": sum(bounds.values()) * (input_cap + output_cap),
        "usd_max_historical_snapshot": round(
            sum(len(p["slots"]) for p in plans.values()) * 60000 * 0.5 / 1000000, 6
        ),
        "assumptions": {
            "input_cap": input_cap,
            "existing_per_slot_max_tokens_per_run": 60000,
            "usd_bound": "all tokens billed at highest output unit price (conservative)",
            "output_cap": output_cap,
            "pricing_verified_on": "2026-11-08",
            "no_cached_discount": True,
            "no_retries": True,
            "compaction": "not wired in this eval harness",
            "Voyage": "separate authorization/metering required by real adapter factory",
        },
        "approval_request": {
            "approved_by": None,
            "approved_on": None,
            "existing_cumulative_ledger": str(args.ledger),
            "additional_calls": None,
            "additional_tokens": None,
            "additional_usd": None,
            "expiry": None,
            "scopes": None,
            "published_corpus_version": None,
            "corpus_manifest_sha256": None,
            "synthetic_data_only": True,
            "no_model_judge": True,
            "hosted_excluded": True,
        },
        "budget_evidence": budget_evidence(args.budget, args.ledger),
    }
    for name, plan in plans.items():
        (args.out / f"{name}.json").write_text(
            json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        result = (
            compare_mechanisms(plan, [], [])
            if name == "s06-mechanisms"
            else reconcile(plan, [], [], [])
        )
        (args.out / f"{name}-status.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    (args.out / "budget-request.json").write_text(
        json.dumps(estimate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    history = {
        p.name: audit(p)
        for p in sorted(RESULTS.iterdir())
        if p.is_dir() and (p / "config.json").is_file()
    }
    (args.out / "historical-reconciliation.json").write_text(
        json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"NOT_RUN {estimate['planned_slots']} slots; max requests {estimate['requests_max']}; paid BLOCKED"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
