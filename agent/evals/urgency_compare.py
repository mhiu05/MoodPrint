"""S-06 addendum: compare urgency options A (deterministic), B (model only) and C (hybrid).

    uv run python agent/evals/urgency_compare.py --set safety_final_frozen --out results/s06-final \
        --max-calls 64          # paid: needs .local/eval-budget.json and .env.live

* One model call per case, ``gpt-6-luna``, effort ``low``, store=False, through the budget gate.
* C is computed from the recorded B result with the same ``hybrid_assess`` code the runtime uses,
  so it costs no extra request. Cases where the deterministic layer already says ``immediate`` are
  still sent to the model here so B can be scored on its own; the runtime skips the call there.
* No judge model: labels are the fixed ones in the case file.
* ``--replay <results-dir>`` recomputes every metric offline from recorded outputs.
"""

import argparse
import asyncio
import json
import math
import statistics
import sys
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evals.budget import BudgetError  # noqa: E402
from evals.live import EVAL_SCOPE, live_cfg, metered_client, open_ledger  # noqa: E402
from evals.safety_eval import CASE_DIR, LEVELS, load  # noqa: E402
from moodprint_agent.tools.risk_assessor import (
    RISK_ASSESSOR_VERSION,
    AssessorFailed,
    AssessorResult,
    ModelRisk,
    OpenAIRiskAssessor,
    hybrid_assess,
)
from moodprint_agent.tools.safety import assess_conversation
from moodprint_shared.config import AppConfig  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"


def wilson(successes: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    if n == 0:
        return None
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return round(max(0.0, centre - half), 3), round(min(1.0, centre + half), 3)


def metrics(rows: Sequence[dict[str, Any]], key: str) -> dict[str, Any]:
    """``key`` is the field holding the predicted level."""
    matrix: dict[str, dict[str, int]] = {e: dict.fromkeys(LEVELS, 0) for e in LEVELS}
    per_group: dict[str, dict[str, int]] = defaultdict(lambda: {"TP": 0, "FN": 0, "FP": 0, "TN": 0})
    for row in rows:
        got, expected = row[key], row["expected"]
        matrix[expected][got] += 1
        group = per_group[row.get("group", "?")]
        if expected == "immediate":
            group["TP" if got == "immediate" else "FN"] += 1
        elif expected == "none":
            group["FP" if got == "immediate" else "TN"] += 1
    n_imm = sum(matrix["immediate"].values())
    n_none = sum(matrix["none"].values())
    tp = matrix["immediate"]["immediate"]
    fp = matrix["none"]["immediate"]
    # An "elevated" case is correct when flagged at all (elevated or immediate), never when "none".
    n_elev = sum(matrix["elevated"].values())
    elev_flagged = n_elev - matrix["elevated"]["none"]
    exact = sum(matrix[level][level] for level in LEVELS)
    return {
        "n": len(rows),
        "TP": tp,
        "FN": n_imm - tp,
        "FP": fp,
        "TN": n_none - fp,
        "recall_immediate": tp / n_imm if n_imm else None,
        "recall_immediate_ci95": wilson(tp, n_imm),
        "fpr_immediate": fp / n_none if n_none else None,
        "fpr_immediate_ci95": wilson(fp, n_none),
        "elevated_flagged_at_all": f"{elev_flagged}/{n_elev}",
        "exact_level_accuracy": exact / len(rows) if rows else None,
        "confusion_expected_by_got": matrix,
        "per_group": dict(per_group),
        "misses": [
            {"id": r["id"], "expected": r["expected"], "got": r[key]}
            for r in rows
            if (r["expected"] == "immediate" and r[key] != "immediate")
            or (r["expected"] == "none" and r[key] == "immediate")
        ],
    }


def percentile(values: Sequence[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, math.ceil(q * len(ordered)) - 1)]


class _Replay:
    """Replays a recorded model answer (or failure) through the production hybrid code."""

    def __init__(self, row: dict[str, Any]) -> None:
        self.row = row

    async def assess(self, messages: Sequence[str]) -> AssessorResult:
        if self.row.get("model_error"):
            raise AssessorFailed(self.row["model_error"])
        return AssessorResult(
            risk=ModelRisk.model_validate(self.row["model"]),
            usage=self.row.get("usage", {}),
            latency_ms=self.row.get("latency_ms", 0),
        )


async def score(rows: list[dict[str, Any]], cases: dict[str, dict[str, Any]]) -> dict[str, Any]:
    for row in rows:
        case = cases[row["id"]]
        row["expected"], row["group"] = case["expected"], case.get("group", "?")
        det = assess_conversation(case["turns"])
        row["A"] = det.level
        if row.get("model_skipped"):
            row["B"] = "skipped"
        elif row.get("model_error"):
            row["B"] = "failed"
        else:
            row["B"] = row["model"]["level"]
        hybrid = await hybrid_assess(
            case["turns"], _Replay(row), skip_when_immediate=bool(row.get("model_skipped"))
        )
        row["C"] = hybrid.assessment.level
        row["C_signals"] = list(hybrid.assessment.signals)
    scored_b = [r for r in rows if r["B"] not in ("failed", "skipped")]
    # A failed B call counts as "none" for B alone (nothing else would run); C has its fallback.
    # Cases the deterministic layer already settled (skipped) are outside B's coverage.
    b_rows = [
        {**r, "B": "none" if r["B"] == "failed" else r["B"]} for r in rows if r["B"] != "skipped"
    ]
    latencies = [r["latency_ms"] for r in rows if r.get("latency_ms")]
    tokens = [r["usage"].get("total_tokens", 0) for r in rows if r.get("usage")]
    out: dict[str, Any] = {
        "n_cases": len(rows),
        "model_skipped_deterministic_immediate": sum(1 for r in rows if r.get("model_skipped")),
        "model_failures": sum(1 for r in rows if r.get("model_error")),
        "A_deterministic": metrics(rows, "A"),
        "B_model_only": metrics(b_rows, "B"),
        "C_hybrid": metrics(rows, "C"),
        "latency_ms_p50": percentile(latencies, 0.5),
        "latency_ms_p95": percentile(latencies, 0.95),
        "tokens_per_call_mean": statistics.fmean(tokens) if tokens else None,
        "tokens_total": sum(tokens),
        "scored_model_answers": len(scored_b),
    }
    conf: dict[str, dict[str, int]] = {
        "low": {"ok": 0, "n": 0},
        "medium": {"ok": 0, "n": 0},
        "high": {"ok": 0, "n": 0},
    }
    for r in scored_b:
        bucket = conf[r["model"]["confidence"]]
        bucket["n"] += 1
        bucket["ok"] += int(r["model"]["level"] == r["expected"])
    out["B_accuracy_by_confidence"] = conf
    return out


async def run(args: argparse.Namespace) -> int:
    cases = {c["id"]: c for c in load(CASE_DIR / f"{args.set}.jsonl")}
    if args.ids:
        cases = {cid: c for cid, c in cases.items() if cid in args.ids.split(",")}
    out_dir = RESULTS / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    rows_path = out_dir / "model_outputs.jsonl"
    done: dict[str, dict[str, Any]] = {}
    if rows_path.exists():
        for line in rows_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                done[row["id"]] = row
    if not args.replay:
        if args.skip_immediate:
            for cid, case in cases.items():
                if cid not in done and assess_conversation(case["turns"]).immediate:
                    done[cid] = {"id": cid, "model_skipped": True}
                    with rows_path.open("a", encoding="utf-8") as fh:
                        fh.write(json.dumps(done[cid]) + "\n")
        todo = [cid for cid in cases if cid not in done][: args.max_calls]
        if todo:
            try:
                ledger = open_ledger(EVAL_SCOPE)
            except BudgetError as exc:
                print(f"budget gate refused: {exc}", file=sys.stderr)
                return 2
            cfg: AppConfig = live_cfg(ledger)
            client, http = metered_client(ledger, "urgency", timeout=args.timeout + 5)
            assessor = OpenAIRiskAssessor(client, cfg, timeout_s=args.timeout, effort=args.effort)
            sem = asyncio.Semaphore(args.concurrency)

            async def one(cid: str) -> None:
                async with sem:
                    row: dict[str, Any] = {"id": cid, "prompt": RISK_ASSESSOR_VERSION}
                    try:
                        result = await assessor.assess(cases[cid]["turns"])
                        row.update(
                            model=result.risk.model_dump(),
                            usage=result.usage,
                            latency_ms=result.latency_ms,
                        )
                    except AssessorFailed as exc:
                        row["model_error"] = exc.code
                    except BudgetError as exc:
                        row["model_error"] = "budget_refused"
                        row["detail"] = str(exc)[:120]
                    done[cid] = row
                    with rows_path.open("a", encoding="utf-8") as fh:
                        fh.write(json.dumps(row, ensure_ascii=False) + "\n")

            try:
                await asyncio.gather(*(one(cid) for cid in todo))
            finally:
                await http.aclose()
            print(
                f"ledger: calls={ledger.reserved_calls} usd={ledger.committed_usd:.4f} "
                f"unknown={ledger.unknown_calls}"
            )
    rows = [done[cid] for cid in cases if cid in done]
    summary = await score(rows, {cid: cases[cid] for cid in cases})
    summary.update(set=args.set, model_prompt=RISK_ASSESSOR_VERSION, effort=args.effort)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    (out_dir / "scored.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
    )
    for name in ("A_deterministic", "B_model_only", "C_hybrid"):
        m = summary[name]
        if m["recall_immediate"] is None:
            continue
        print(
            f"{name:16} recall={m['recall_immediate']} ci={m['recall_immediate_ci95']} "
            f"fpr={m['fpr_immediate']} exact={m['exact_level_accuracy']:.2f} "
            f"TP/FN/FP/TN={m['TP']}/{m['FN']}/{m['FP']}/{m['TN']}"
        )
    print(
        "latency p50/p95 ms:",
        summary["latency_ms_p50"],
        summary["latency_ms_p95"],
        "failures:",
        summary["model_failures"],
        "tokens:",
        summary["tokens_total"],
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--set", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--max-calls", type=int, default=0)
    parser.add_argument("--timeout", type=float, default=6.0)
    parser.add_argument("--effort", default="low")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--replay", action="store_true")
    parser.add_argument("--ids", default="")
    parser.add_argument("--skip-immediate", action="store_true")
    return asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
