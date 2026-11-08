"""Frozen safety holdouts: the files cannot change after the fact and the measured numbers cannot
silently regress. These guards record what the detector achieves; they do NOT claim the 0.95
recall target is met on unseen text (it is not: see docs/implementation/reports/phase-3-report.md).
"""

import hashlib
import sys
from pathlib import Path

import pytest

EVALS = Path(__file__).resolve().parents[1] / "evals"
sys.path.insert(0, str(EVALS.parent))

from evals import safety_eval  # noqa: E402

CASES = EVALS / "cases"
# Pinned when each set was frozen (H3 before any detector change, H4 after tuning on H3).
FROZEN = {
    "safety_h3_frozen.jsonl": "9c678b0cc99ced16841b1a82f0086724f847f8ca",
    "safety_h4_frozen.jsonl": "2e88006619e81e10b82085e7885eb3b497fc9589",
}


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()  # noqa: S324 - git object id


@pytest.mark.parametrize("name, expected", FROZEN.items())
def test_frozen_sets_are_unchanged(name: str, expected: str) -> None:
    assert git_blob_sha(CASES / name) == expected, f"{name} was edited after it was frozen"


def result(name: str):
    return safety_eval.evaluate(safety_eval.load(CASES / name))


def test_tuned_sets_keep_full_recall_and_no_false_alarms() -> None:
    for name in ("safety_phrases.jsonl", "safety_heldout.jsonl", "safety_heldout2.jsonl"):
        found = result(name)
        assert found["recall_immediate"] == 1.0 and found["false_positive_rate_immediate"] == 0.0


def test_independent_holdout_numbers_do_not_regress() -> None:
    h3, h4 = result("safety_h3_frozen.jsonl"), result("safety_h4_frozen.jsonl")
    # H3 was tuned on after its first run (first contact: recall 0.469, FPR 0.059).
    assert h3["recall_immediate"] >= 0.90 and h3["false_positive_rate_immediate"] <= 0.03
    # H4 was never tuned on: 0.583 recall / 0.031 FPR. Lowering these needs an explicit decision.
    assert h4["recall_immediate"] >= 0.58 and h4["false_positive_rate_immediate"] <= 0.04
    assert h4["n_immediate"] == 24 and h4["n_benign"] == 32
