"""Rebuild metrics and human-review examples from saved synthetic evidence, offline."""

import argparse
import json
import statistics
from pathlib import Path

METRICS = (
    "factual_accuracy", "multi_turn_consistency", "relevance_usefulness", "tool_correctness",
    "natural_vietnamese", "initiative", "uncertainty_calibration", "persona_differentiation",
    "privacy_authorization",
)


def summarize(directory: Path):
    candidate_file = "live-candidate-final.json" if (directory / "live-candidate-final.json").exists() else "live-candidate.json"
    reports = [json.loads((directory / name).read_text(encoding="utf-8")) for name in ("live-baseline.json", candidate_file)]
    all_judges = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(directory.glob("live-judge*.json"))]
    judge_paths = [directory / "live-judge-final.json"] if (directory / "live-judge-final.json").exists() else sorted(directory.glob("live-judge*.json"))
    judges = [json.loads(path.read_text(encoding="utf-8")) for path in judge_paths]
    scores = [row for judge in judges for row in judge["rows"] if "error_type" not in row]
    summary = {"dataset": reports[0]["dataset_version"], "model": reports[0]["model"],
               "arms": {}, "judge_errors_retained": [row for judge in all_judges for row in judge["rows"] if "error_type" in row],
               "judge_known_estimated_usd": round(sum(judge["estimated_usd"] for judge in judges), 6),
               "judge_unknown_usage_requests": sum(judge["usage"]["requests"] - len({(row["caseId"], row["repeat"]) for row in judge["rows"] if "error_type" not in row}) for judge in judges),
               "independent_human_review": False}
    examples = ["# Synthetic multi-turn review examples", "", "Frozen new dataset; no reserved heldout cases. LLM judging is not independent human review.", ""]
    for report in reports:
        rows, variant = report["rows"], report["variant"]
        observed_scores = [row for row in scores if row["variant"] == variant and not row["repeat"]]
        latencies = [row["latency_seconds"] for row in rows]
        no_prior_tool_results = all(not any(item.get("type") == "function_call_output" for item in row["model_inputs"][0]["input"]) for row in rows if row["model_inputs"])
        summary["arms"][variant] = {
            "turns": len(rows), "completed": sum(row["status"] == "COMPLETED" for row in rows),
            "assertion_failures": [{"caseId": row["caseId"], "turn": row["turn"], "checks": [key for key, value in row["assertions"].items() if not value]} for row in rows if not all(row["assertions"].values())],
            "no_prior_tool_results_in_first_model_input": no_prior_tool_results,
            "latency_p50_seconds": round(statistics.median(latencies), 3),
            "latency_p95_seconds": round(statistics.quantiles(latencies, n=100, method="inclusive")[94], 3),
            "usage": report["usage"], "estimated_usd": report["estimated_usd"],
            "judged_conversations": len(observed_scores),
            "quality_means": {metric: round(statistics.mean(row[metric] for row in observed_scores), 3) for metric in METRICS} if observed_scores else {},
            "judge_hard_gate_failures": [row["caseId"] for row in observed_scores if row["hard_gate_failure"]],
        }
    all_arms = [json.loads(path.read_text(encoding="utf-8")) for path in directory.glob("live-*.json") if "judge" not in path.name]
    summary["all_rounds_known_estimated_total_usd"] = round(sum(report["estimated_usd"] for report in all_arms) + sum(judge["estimated_usd"] for judge in all_judges), 6)
    summary["all_rounds_judge_unknown_usage_requests"] = sum(judge["usage"]["requests"] - len({(row["caseId"], row["repeat"]) for row in judge["rows"] if "error_type" not in row}) for judge in all_judges)
    summary["all_rounds_requests"] = sum(report["budget_consumed"]["requests"] for report in all_arms) + sum(judge["usage"]["requests"] for judge in all_judges)
    summary["all_rounds_reserved_token_upper_bound"] = sum(report["budget_consumed"]["reserved_token_upper_bound"] for report in all_arms) + sum(judge["reserved_token_upper_bound"] for judge in all_judges)
    summary["judge_adjudication_required"] = {
        "caseId": "P0-MAY-REVOKED-MEMORY",
        "reason": "Raw judge flags both arms for using approved memory on turn 1 because mood scope=false. Mood scope and MEM are independent: the fixture explicitly enables MEM and approves that synthetic memory before turn 1; revocation precedes turn 2. Actual SDK-input assertions pass after revocation. Keep raw scores/flags pending independent review.",
    }
    summary["known_estimated_total_usd"] = round(sum(report["estimated_usd"] for report in reports) + summary["judge_known_estimated_usd"], 6)
    summary["quality_deltas_candidate_minus_baseline"] = {metric: round(summary["arms"]["candidate"]["quality_means"][metric] - summary["arms"]["baseline"]["quality_means"][metric], 3) for metric in METRICS}
    summary["order_repeat_max_absolute_delta"] = max((abs(row[metric] - original[metric]) for row in scores if row["repeat"] for original in scores if not original["repeat"] and original["caseId"] == row["caseId"] and original["variant"] == row["variant"] for metric in METRICS), default=0)
    for case in dict.fromkeys(row["caseId"] for row in reports[0]["rows"]):
        examples.extend([f"## {case}", ""])
        for report in reports:
            examples.extend([f"### {report['variant']}", ""])
            for row in report["rows"]:
                if row["caseId"] == case:
                    examples.extend([f"Turn {row['turn']} · scope={row['scope_present']} · tools={', '.join(row['tools']) or 'none'}", "", f"User: {row['prompt']}", "", f"Assistant: {(row.get('output') or {}).get('text', '[failed]')}", ""])
    (directory / "evaluation-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (directory / "human-review-examples.md").write_text("\n".join(examples), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=True, indent=2))
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    summarize(parser.parse_args().directory)
