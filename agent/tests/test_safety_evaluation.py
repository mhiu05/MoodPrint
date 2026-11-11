"""Hand-checked metrics: every error level and small-sample uncertainty remain visible."""

import sys
from pathlib import Path

import pytest
from safevoice_agent.tools.safety import UrgencyAssessment

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evals import safety_eval


def test_metrics_include_benign_only_fpr_elevated_errors_and_intervals(monkeypatch) -> None:
    predictions = ["immediate", "elevated", "immediate", "none", "immediate", "none"]
    expected = ["immediate", "immediate", "none", "none", "elevated", "elevated"]
    rows = [
        {"id": str(i), "turns": [str(i)], "expected": e, "group": "mixed"}
        for i, e in enumerate(expected)
    ]
    monkeypatch.setattr(
        safety_eval,
        "assess_conversation",
        lambda turns: UrgencyAssessment(predictions[int(turns[0])]),
    )
    result = safety_eval.evaluate(rows)
    assert result["recall_immediate"] == 0.5
    assert result["false_positive_rate_immediate"] == 0.5
    assert result["exact_level_accuracy"] == pytest.approx(1 / 3)
    assert len(result["level_errors"]) == 4
    assert result["elevated_overtriage"] == 0.5 and result["elevated_undertriage"] == 0.5
    assert result["recall_immediate_ci95"] == pytest.approx([0.094531, 0.905469], abs=1e-6)
    assert result["per_group_metrics"]["mixed"]["n_elevated"] == 2


def test_empty_metrics_are_unknown_instead_of_a_perfect_score() -> None:
    result = safety_eval.evaluate([])
    assert result["recall_immediate_ci95"] is None
    assert result["false_positive_rate_immediate_ci95"] is None
    assert result["exact_level_accuracy"] is None
