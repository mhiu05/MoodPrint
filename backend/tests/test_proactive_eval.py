"""The check-in eval harness runs offline and covers every companion × slot (P1-19)."""

import asyncio
from collections import Counter


def test_cases_cover_every_companion_and_slot_with_a_holdout():
    from evals.proactive.cases import CASES

    tuning = Counter((c.bot_id, c.slot) for c in CASES if not c.holdout)
    assert len(tuning) == 10 and min(tuning.values()) >= 6
    assert len(CASES) >= 60 and sum(c.holdout for c in CASES) >= 5
    assert len({c.case_id for c in CASES}) == len(CASES)


def test_offline_harness_builds_runs_and_validates_every_case():
    from evals.proactive.__main__ import run_offline

    result = asyncio.run(run_offline())
    assert result["cases"] >= 60 and result["failures"] == []


def test_live_mode_refuses_without_budget_or_confirmation(tmp_path, monkeypatch):
    from evals.proactive.__main__ import main

    monkeypatch.setenv("OPENAI_API_KEY", "")
    assert main(["--live", "--output", str(tmp_path / "r.json")]) == 2
    assert main(["--live", "--confirm-live", "--max-usd", "1", "--output", str(tmp_path / "r2.json")]) == 2
