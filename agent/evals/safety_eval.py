"""Offline urgency evaluation: confusion matrix, recall and false-positive rate per group.

Deterministic and free. It measures the *detector* only; it says nothing about the quality of
what the model then writes (that is graded separately from live outputs).
"""

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from moodprint_agent.tools.safety import assess_conversation

CASE_DIR = Path(__file__).resolve().parent / "cases"
LEVELS = ("none", "elevated", "immediate")


def load(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def evaluate(items: list[dict[str, Any]]) -> dict[str, Any]:
    matrix: dict[str, dict[str, int]] = {e: dict.fromkeys(LEVELS, 0) for e in LEVELS}
    per_group: dict[str, dict[str, int]] = defaultdict(lambda: {"TP": 0, "FN": 0, "FP": 0, "TN": 0})
    misses: list[dict[str, Any]] = []
    for item in items:
        got = assess_conversation(item["turns"]).level
        expected = item["expected"]
        matrix[expected][got] += 1
        counts = per_group[item.get("group", "?")]
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
    fp = sum(1 for i in benign if assess_conversation(i["turns"]).level == "immediate")
    return {
        "n": len(items),
        "n_immediate": len(immediate),
        "n_benign": len(benign),
        "recall_immediate": tp / len(immediate) if immediate else None,
        "false_positive_rate_immediate": fp / len(benign) if benign else None,
        "confusion_expected_by_got": matrix,
        "per_group": dict(per_group),
        "misses": misses,
    }


def run(paths: list[Path]) -> dict[str, Any]:
    return {path.stem: evaluate(load(path)) for path in paths}
