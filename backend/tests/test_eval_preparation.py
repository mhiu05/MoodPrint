from collections import Counter

from evals.dataset import cases
from evals.evaluate import evaluate


def test_dataset_has_sixty_unique_synthetic_cases_and_balanced_reserved_splits():
    dataset = cases()
    assert len(dataset) == len({row["id"] for row in dataset}) == 60
    assert Counter(row["botId"] for row in dataset) == dict.fromkeys(
        ("may", "guong", "nhip", "rure", "caunoi"), 12
    )
    assert Counter(row["split"] for row in dataset) == dict.fromkeys(
        ("calibration", "development", "heldout"), 20
    )
    assert all(row["synthetic"] and row["criteria"] for row in dataset)
    assert not any(row["memoryApplicable"] for row in dataset if row["botId"] == "caunoi")


def test_offline_checker_never_reports_empty_or_forged_results_as_release_ready():
    report = evaluate([])
    assert not report["completeABC"] and not report["releaseReady"]
    report = evaluate(
        [
            {
                "caseId": "E-MAY-01",
                "variant": "A",
                "synthetic": True,
                "output": {"text": "saved", "cards": [], "receipt": {"status": "succeeded"}},
            }
        ]
    )
    assert any(row["code"] == "INVALID_OUTPUT_CONTRACT" for row in report["failures"])
    assert not report["releaseReady"] and report["liveProviderRunsPerformed"] == 0
