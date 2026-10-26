import json
from pathlib import Path

from app.ai.prompts import SELECTED_VARIANTS, instructions

FIXTURES = Path(__file__).resolve().parents[1] / "evals/fixtures"


def test_new_synthetic_multiturn_suite_is_separate_from_reserved_dataset():
    dataset = json.loads((FIXTURES / "evidence_p0_cases.json").read_text(encoding="utf-8"))
    cases = dataset["cases"]
    assert dataset["synthetic"] and dataset["split"] == "new-regression-evaluation"
    assert len(cases) == len({case["id"] for case in cases}) == 12
    assert {case["botId"] for case in cases} == set(SELECTED_VARIANTS)
    assert sum(len(case["turns"]) for case in cases) == 25
    assert {case["records"] for case in cases} == {0, 1, 2, 3}
    assert all(case["id"].startswith("P0-") for case in cases)


def test_historical_selected_prompts_are_frozen_byte_for_byte():
    baseline = json.loads((FIXTURES / "evidence_p0_baseline.json").read_text(encoding="utf-8"))
    assert baseline == {bot: instructions(bot) for bot in SELECTED_VARIANTS}
