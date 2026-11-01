"""P1-08 eval tooling: rubric, offline runner and the live budget gate (no network)."""

import json

import pytest

from evals.multi_message.__main__ import live, main, offline
from evals.multi_message.cases import CASES
from evals.multi_message.rubric import score, summarize
from tests.fakes import ScriptedModel, message_output

SHORT = next(case for case in CASES if case.kind == "short")
LIST = next(case for case in CASES if case.kind == "list")


def payload(*texts):
    return {"messages": [{"text": text, "cards": []} for text in texts]}


def test_rubric_rewards_one_bubble_for_short_and_unsplit_lists():
    assert score(SHORT, payload("Không có gì đâu."))["singleWhenShort"] is True
    assert score(SHORT, payload("Không có gì.", "Chúc bạn vui!"))["singleWhenShort"] is False
    unsplit = score(LIST, payload("Thử nhé:\n1. Tắt màn hình\n2. Đọc sách\n3. Thở chậm"))
    assert unsplit["listUnsplit"] is True
    split = score(LIST, payload("1. Tắt màn hình", "2. Đọc sách"))
    assert split["listUnsplit"] is False


def test_rubric_marks_contract_violations_invalid_without_echoing_text():
    result = score(SHORT, payload("A", "a"))  # duplicate bubbles
    assert result["valid"] is False
    assert "A" not in json.dumps(result)


def test_summary_gate_needs_every_target():
    perfect = [score(case, payload("1. Một\n2. Hai") if case.kind == "list" else payload("Ổn."))
               for case in CASES]
    assert summarize(perfect)["passed"] is True
    worse = [*perfect[:-1], score(SHORT, payload("Ổn.", "Thật mà."))]
    assert summarize(worse)["shortSingleRate"] < 1


def test_offline_runner_reports_missing_cases(tmp_path):
    recorded = tmp_path / "recorded.jsonl"
    recorded.write_text(json.dumps({"caseId": SHORT.case_id, "output": payload("Ổn.")}) + "\n", encoding="utf-8")
    report = offline(recorded)
    assert report["summary"]["cases"] == 1
    assert len(report["missingCases"]) == len(CASES) - 1


@pytest.mark.parametrize("argv", [["--live", "--max-usd", "1"], ["--live", "--confirm-live"], ["--live", "--confirm-live", "--max-usd", "0"]])
def test_live_mode_refuses_without_explicit_confirmation_and_budget(tmp_path, argv):
    assert main([*argv, "--output", str(tmp_path / "report.json")]) == 2
    assert not (tmp_path / "report.json").exists()


async def test_live_runner_uses_the_flagged_provider_with_a_fake_model():
    model = ScriptedModel([[message_output(json.dumps(payload("Ổn nhé.")))]])
    report = await live(0.01, model_override=model)
    assert report["completedCases"] == len(CASES)
    assert all("Mặc định dùng 1 tin" in call["instructions"] for call in model.calls)
    assert report["summary"]["shortSingleRate"] == 1.0
