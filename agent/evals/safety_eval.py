"""Offline urgency evaluation: confusion matrix, recall and false-positive rate per group.

Deterministic and free. It measures the *detector* only; it says nothing about the quality of
what the model then writes (that is graded separately from live outputs).
"""

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

from safevoice_agent.tools.safety import assess_conversation

CASE_DIR = Path(__file__).resolve().parent / "cases"
LEVELS = ("none", "elevated", "immediate")


def load(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def wilson(successes: int, n: int) -> list[float] | None:
    """Two-sided Wilson 95% interval; no observation means no estimate."""
    if n == 0:
        return None
    z = 1.959963984540054
    p = successes / n
    denominator = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denominator
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return [max(0.0, centre - half), min(1.0, centre + half)]


def evaluate(items: list[dict[str, Any]]) -> dict[str, Any]:
    matrix: dict[str, dict[str, int]] = {e: dict.fromkeys(LEVELS, 0) for e in LEVELS}
    per_group: dict[str, dict[str, int]] = defaultdict(lambda: {"TP": 0, "FN": 0, "FP": 0, "TN": 0})
    misses: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        got = assess_conversation(item["turns"]).level
        expected = item["expected"]
        matrix[expected][got] += 1
        group = item.get("group", "?")
        groups[group].append({"expected": expected, "got": got})
        counts = per_group[group]
        if expected != got:
            errors.append({"id": item["id"], "expected": expected, "got": got})
        if expected == "immediate":
            counts["TP" if got == "immediate" else "FN"] += 1
        elif expected == "none":
            counts["FP" if got == "immediate" else "TN"] += 1
        if (expected == "immediate" and got != "immediate") or (
            expected == "none" and got == "immediate"
        ):
            misses.append(
                {"id": item["id"], "expected": expected, "got": got, "turns": item["turns"]}
            )
    immediate = [i for i in items if i["expected"] == "immediate"]
    benign = [i for i in items if i["expected"] == "none"]
    tp = matrix["immediate"]["immediate"]
    fp = matrix["none"]["immediate"]
    n_elevated = sum(matrix["elevated"].values())
    group_metrics: dict[str, dict[str, Any]] = {}
    for group, rows in groups.items():
        counts = per_group[group]
        positive, negative = counts["TP"] + counts["FN"], counts["FP"] + counts["TN"]
        group_metrics[group] = {
            **counts,
            "n": len(rows),
            "n_immediate": positive,
            "n_benign": negative,
            "n_elevated": sum(r["expected"] == "elevated" for r in rows),
            "recall_immediate": counts["TP"] / positive if positive else None,
            "recall_immediate_ci95": wilson(counts["TP"], positive),
            "false_positive_rate_immediate": counts["FP"] / negative if negative else None,
            "false_positive_rate_immediate_ci95": wilson(counts["FP"], negative),
        }
    return {
        "n": len(items),
        "n_immediate": len(immediate),
        "n_benign": len(benign),
        "recall_immediate": tp / len(immediate) if immediate else None,
        "false_positive_rate_immediate": fp / len(benign) if benign else None,
        "recall_immediate_ci95": wilson(tp, len(immediate)),
        "false_positive_rate_immediate_ci95": wilson(fp, len(benign)),
        "fpr_denominator": "expected_none_only",
        "exact_level_accuracy": sum(matrix[level][level] for level in LEVELS) / len(items)
        if items
        else None,
        "n_elevated": n_elevated,
        "elevated_overtriage": matrix["elevated"]["immediate"] / n_elevated if n_elevated else None,
        "elevated_undertriage": matrix["elevated"]["none"] / n_elevated if n_elevated else None,
        "level_errors": errors,
        "per_group_metrics": group_metrics,
        "confusion_expected_by_got": matrix,
        "per_group": dict(per_group),
        "misses": misses,
    }


def run(paths: list[Path]) -> dict[str, Any]:
    return {path.stem: evaluate(load(path)) for path in paths}
