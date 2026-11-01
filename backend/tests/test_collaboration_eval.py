"""P2-09: the collaboration eval harness runs offline and never spends without explicit budget."""

from collections import Counter


def test_cases_cover_every_rule_negatives_and_a_holdout():
    from evals.collaboration.cases import ENERGY, ROUTING

    labels = Counter(case.expected for case in ROUTING)
    assert labels["R1"] >= 5 and labels["R3"] >= 5 and labels["R4"] >= 5 and labels[None] >= 15
    assert sum(case.holdout for case in ROUTING) >= 10
    assert {"injection", "distress", "listening", "not_requester"} <= {t for c in ROUTING for t in c.tags}
    assert len({case.case_id for case in ROUTING}) == len(ROUTING)
    assert len(ENERGY) >= 20 and sum("injection" in c.tags for c in ENERGY) >= 3


def test_offline_routing_minimization_and_fail_closed():
    from evals.collaboration.__main__ import run_offline

    result = run_offline()
    routing = result["routing"]
    assert routing["all"]["unnecessaryDelegation"] == 0 and routing["holdout"]["accuracy"] >= 0.9
    assert routing["all"]["recall"] >= 0.9 and routing["leaks"] == []
    assert result["failClosed"]["accepted"] == 0 and result["failClosed"]["attempts"] >= 60
    for edge in result["cost"]["edges"].values():
        assert edge["estimatedUsdPerConsultation"] < 0.001


def test_live_mode_refuses_without_budget_confirmation_or_key(tmp_path, monkeypatch):
    from evals.collaboration.__main__ import main

    monkeypatch.setenv("OPENAI_API_KEY", "")
    assert main(["--live", "--output", str(tmp_path / "a.json")]) == 2
    assert main(["--live", "--confirm-live", "--max-usd", "1", "--output", str(tmp_path / "b.json")]) == 2
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-used")
    assert main(["--live", "--max-usd", "1", "--output", str(tmp_path / "c.json")]) == 2
    assert main(["--live", "--confirm-live", "--output", str(tmp_path / "d.json")]) == 2
    assert main(["--live", "--confirm-live", "--max-usd", "1", "--model", "unknown-model",
                 "--output", str(tmp_path / "e.json")]) == 2
    assert not any((tmp_path / name).exists() for name in ("a.json", "b.json", "c.json", "d.json", "e.json"))
