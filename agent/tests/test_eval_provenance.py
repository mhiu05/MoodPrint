"""Offline evidence integrity: absent runs and older prompts cannot pass a gate."""

import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evals.cases_io import Case


def test_plan_pins_every_repeat_and_not_run():
    from evals.provenance import build_manifest, reconcile

    manifest = build_manifest(
        [Case(id="one", suite="chat", turns=["hello"], rubric_ids=["R-02"])], repeat=3
    )
    assert [(s["case_id"], s["repeat"], s["status"]) for s in manifest["slots"]] == [
        ("one", 1, "NOT_RUN"),
        ("one", 2, "NOT_RUN"),
        ("one", 3, "NOT_RUN"),
    ]
    assert len(manifest["provenance"]["prompt_sha256"]["companion_v5"]) == 64
    report = reconcile(manifest, [], [], [])
    assert report["status"] == "NOT_VERIFIED" and report["not_run"] == 3


def evidence():
    from evals.provenance import build_manifest, digest

    manifest = build_manifest(
        [Case(id="one", suite="chat", turns=["hello"], rubric_ids=["R-02"])], repeat=3
    )
    outputs, checks, grades = [], [], []
    for repeat in (1, 2, 3):
        outputs.append(
            {
                "case_id": "one",
                "repeat": repeat,
                "turns": [{"status": "completed"}],
                "provenance_id": manifest["provenance_id"],
            }
        )
        checks.append(
            {
                "case_id": "one",
                "repeat": repeat,
                "p0_total": 1,
                "p0_passed": 1,
                "p1_total": 1,
                "p1_passed": 1,
                "failed": [],
                "provenance_id": manifest["provenance_id"],
                "output_sha256": digest(outputs[-1]),
            }
        )
        grades.append(
            {
                "case_id": "one",
                "repeat": repeat,
                "rubric_id": "R-02",
                "score": 1 if repeat == 2 else 3,
                "reason": "read",
                "grader": "coding agent",
                "provenance_id": manifest["provenance_id"],
                "output_sha256": digest(outputs[-1]),
            }
        )
    return manifest, outputs, checks, grades


def test_worst_rubric_score_and_two_of_three_p1():
    from evals.provenance import reconcile

    manifest, outputs, checks, grades = evidence()
    checks[1].update(p1_passed=0)
    report = reconcile(manifest, outputs, checks, grades)
    assert report["rubric_case_minima"] == {"one/R-02": 1}
    assert report["p1_case_passes"] == {"one": True}
    assert report["status"] == "NOT_VERIFIED"


@pytest.mark.parametrize(
    "damage",
    [
        "old_prompt",
        "missing_output",
        "duplicate",
        "crashed",
        "missing_assertion",
        "missing_grade",
        "orphan_grade",
    ],
)
def test_reconciliation_rejects_incomplete_or_old_evidence(damage):
    from evals.provenance import reconcile

    manifest, outputs, checks, grades = evidence()
    for g in grades:
        g["score"] = 3
    if damage == "old_prompt":
        outputs[0]["provenance_id"] = "historical-v3"
    elif damage == "missing_output":
        outputs.pop()
    elif damage == "duplicate":
        outputs.append(copy.deepcopy(outputs[0]))
    elif damage == "crashed":
        outputs[0].update(turns=[], crashed="ValueError")
    elif damage == "missing_assertion":
        checks.pop()
    elif damage == "missing_grade":
        grades.pop()
    else:
        grades.append({**grades[0], "case_id": "unknown"})
    report = reconcile(manifest, outputs, checks, grades)
    assert report["status"] == "NOT_VERIFIED" and report["errors"]


def test_any_p0_failure_blocks():
    from evals.provenance import reconcile

    manifest, outputs, checks, grades = evidence()
    for g in grades:
        g["score"] = 3
    assert reconcile(manifest, outputs, checks, grades)["status"] == "VERIFIED_EVIDENCE"
    checks[2].update(p0_passed=0, failed=["A-01"])
    assert reconcile(manifest, outputs, checks, grades)["status"] == "NOT_VERIFIED"


def test_compare_rejects_prompt_drift():
    from evals.provenance import compare, reconcile

    manifest, outputs, checks, grades = evidence()
    report = reconcile(manifest, outputs, checks, grades)
    other = copy.deepcopy(manifest)
    other["provenance"]["prompt_sha256"]["companion_v5"] = "0" * 64
    assert compare(manifest, report, other, report)["comparable"] is False


def test_recording_retriever_accepts_injected_adapter():
    from evals.fakes import RecordingKnowledge
    from moodprint_shared.testing.knowledge_fixture import FixtureKnowledgeRetriever

    inner = FixtureKnowledgeRetriever()
    assert RecordingKnowledge(inner=inner)._inner is inner


@pytest.mark.parametrize(
    "record", [{"turns": [], "crashed": "oops"}, {"turns": [], "blocked": "budget"}, {"turns": []}]
)
def test_crashed_or_empty_case_has_failure_assertion(record):
    from evals.run import check_record

    results = check_record(Case(id="one", suite="chat", turns=["hello"]), record)
    assert any(r.p0 and not r.ok and r.id == "A-EXEC" for r in results)


def test_live_ledger_missing_is_refused_without_creating_new_ledger(tmp_path, monkeypatch):
    from evals.budget import BudgetError
    from evals.live import open_ledger

    missing = tmp_path / "eval-spend.jsonl"
    monkeypatch.setenv("MOODPRINT_EVAL_LEDGER", str(missing))
    with pytest.raises(BudgetError, match="existing.*ledger"):
        open_ledger()
    assert not missing.exists()


def test_injection_requesting_no_approval_cannot_prepare_or_save():
    from evals import assertions
    from evals.cases_io import load_cases

    case = next(c for c in load_cases() if c.id == "inj-06")
    from agent.tests.test_eval_harness import record

    bad = record()
    bad["turns"][0]["tools"] = ["propose_case_event", "save_confirmed_event"]
    assert any(r.id == "A-29" and not r.ok for r in assertions.check(case, bad))


def test_rejection_wording_does_not_claim_a_system_failure():
    from evals import assertions
    from evals.cases_io import Expect

    from agent.tests.test_eval_harness import with_decisions

    case = Case(
        id="rejection",
        suite="approval",
        turns=["save"],
        expect=Expect(approvals=["reject"], writes=0),
    )
    bad = with_decisions("[reject]", writes=0)
    bad["turns"][-1]["assistant"] = "Hệ thống không thể lưu kế hoạch."
    assert any(r.id == "A-30" and not r.ok for r in assertions.check(case, bad))
    bad["turns"][-1]["assistant"] = "Bạn đã chọn không lưu; mình giữ kế hoạch ở dạng đề xuất."
    assert not any(r.id == "A-30" and not r.ok for r in assertions.check(case, bad))


def test_plan_only_writes_all_201_not_run_slots_without_opening_budget(tmp_path, monkeypatch):
    import json

    from evals import live, run

    def forbidden(*args, **kwargs):
        raise AssertionError("offline plan tried to open paid infrastructure")

    monkeypatch.setattr(run, "RESULTS", tmp_path)
    monkeypatch.setattr(live, "open_ledger", forbidden)
    assert run.main(["--plan-only", "--run-id", "pinned", "--repeat", "3"]) == 0
    manifest = json.loads((tmp_path / "pinned/manifest.json").read_text(encoding="utf-8"))
    assert manifest["unique_cases"] == 67 and len(manifest["slots"]) == 201
    assert all(s["status"] == "NOT_RUN" for s in manifest["slots"])
    assert not list(tmp_path.rglob("*spend*"))


def test_original_s06_plan_has_four_mechanisms_not_risk_architecture_options():
    from evals.s06_mechanisms import build_plan, compare_mechanisms

    plan = build_plan()
    assert len(plan["inputs"]) == 20 and len(plan["slots"]) == 240
    assert {s["mechanism"] for s in plan["slots"]} == {
        "text_baseline",
        "a_json_stream",
        "b_closing_tool",
        "c_postprocess_classifier",
    }
    assert all(s["status"] == "NOT_RUN" for s in plan["slots"])
    report = compare_mechanisms(plan, [], [])
    assert report["status"] == "NOT_VERIFIED" and report["not_run"] == 240


def test_original_s06_replay_never_treats_missing_structured_output_as_coverage():
    from evals.s06_mechanisms import build_plan, compare_mechanisms

    plan = build_plan()
    rows = [
        {
            "case_id": s["case_id"],
            "mechanism": s["mechanism"],
            "repeat": s["repeat"],
            "ttft_ms": 100,
            "structured": None,
            "reply": "hello",
        }
        for s in plan["slots"]
    ]
    report = compare_mechanisms(plan, rows, [])
    assert report["options"]["a_json_stream"]["assessment_coverage"] == 0
    assert report["status"] == "NOT_VERIFIED"


def test_missing_request_bound_counts_roleplay_coach_and_approval_resumes():
    from evals.cases_io import Expect
    from evals.readiness import request_bound

    assert request_bound(Case(id="r", suite="roleplay", turns=["x"] * 6), max_turns=8) == 7
    assert (
        request_bound(
            Case(id="a", suite="approval", turns=["x"] * 2, expect=Expect(approvals=["approve"])),
            max_turns=8,
        )
        == 24
    )
    assert request_bound(Case(id="s", suite="screenshot", image="x"), max_turns=8) == 1


@pytest.mark.asyncio
async def test_real_adapter_is_not_replaced_with_empty_fixture_setup():
    from evals.cases_io import Setup
    from evals.harness import _domain_for
    from moodprint_shared.contracts.knowledge import KnowledgeQuery, RetrievalScope
    from moodprint_shared.testing.knowledge_fixture import FixtureKnowledgeRetriever

    domain = _domain_for(
        Case(id="real", suite="knowledge", setup=Setup(corpus="empty")), FixtureKnowledgeRetriever()
    )
    result = await domain.knowledge.search(
        KnowledgeQuery(text="bắt nạt"), scope=RetrievalScope(request_id="test"), timeout_s=2
    )
    assert result.status == "ok" and result.chunks


def test_same_title_does_not_validate_a_different_source_identity():
    from evals import assertions

    from agent.tests.test_eval_harness import record

    bad = record(retrieved_citation_titles=["same"])
    bad["turns"][0]["citations"] = ["same"]
    bad["turns"][0]["citation_records"] = [
        {"source_id": "forged", "document_id": "d", "title": "same"}
    ]
    bad["retrieved_citation_records"] = [{"source_id": "real", "document_id": "d", "title": "same"}]
    assert any(
        r.id == "A-04" and not r.ok for r in assertions.check(Case(id="x", suite="knowledge"), bad)
    )


@pytest.mark.parametrize(
    "source_name", ["knowledge_support.py", "s06_runner.py", "s06_mechanisms.py"]
)
def test_shared_evidence_policy_is_part_of_the_pinned_source(monkeypatch, source_name):
    from evals import provenance

    original = provenance.file_hash
    before = provenance.snapshot(
        __import__("moodprint_shared.config", fromlist=["AppConfig"]).AppConfig(),
        effort="low",
        retriever="fixture",
        corpus_version="synthetic-fixture-v1",
    )
    monkeypatch.setattr(
        provenance,
        "file_hash",
        lambda path: "f" * 64 if path.name == source_name else original(path),
    )
    after = provenance.snapshot(
        __import__("moodprint_shared.config", fromlist=["AppConfig"]).AppConfig(),
        effort="low",
        retriever="fixture",
        corpus_version="synthetic-fixture-v1",
    )
    assert before["source_sha256"] != after["source_sha256"]


def test_outputs_for_old_case_text_cannot_verify_a_new_manifest():
    from evals.provenance import build_manifest, reconcile

    manifest, outputs, checks, grades = evidence()
    for grade in grades:
        grade["score"] = 3
    assert reconcile(manifest, outputs, checks, grades)["status"] == "VERIFIED_EVIDENCE"
    changed = build_manifest(
        [Case(id="one", suite="chat", turns=["a different question"], rubric_ids=["R-02"])],
        repeat=3,
    )
    assert reconcile(changed, outputs, checks, grades)["status"] == "NOT_VERIFIED"


def test_repeat_protocol_is_part_of_the_pinned_identity():
    from evals.provenance import build_manifest

    cases = [Case(id="one", suite="chat", turns=["hello"])]
    assert (
        build_manifest(cases, repeat=1)["provenance_id"]
        != build_manifest(cases, repeat=3)["provenance_id"]
    )


def test_case_selection_identity_is_stable_when_only_input_order_changes():
    from evals.provenance import build_manifest

    cases = [
        Case(id="one", suite="chat", turns=["hello"]),
        Case(id="two", suite="chat", turns=["hi"]),
    ]
    assert (
        build_manifest(cases)["provenance_id"]
        == build_manifest(list(reversed(cases)))["provenance_id"]
    )


def test_s06_repeat_protocol_is_part_of_the_pinned_identity():
    from evals.s06_mechanisms import build_plan

    assert build_plan(repeat=1)["provenance_id"] != build_plan(repeat=3)["provenance_id"]


def complete_s06_replay():
    from evals.provenance import digest
    from evals.s06_mechanisms import build_plan

    plan = build_plan(repeat=1)
    labels = {item["case_id"]: item["expected_urgency"] or "none" for item in plan["inputs"]}
    rows, grades = [], []
    for slot in plan["slots"]:
        rows.append(
            {
                **slot,
                "status": "completed",
                "provenance_id": plan["provenance_id"],
                "reply": "Synthetic reply",
                "ttft_ms": 100,
                "deterministic_urgency": labels[slot["case_id"]],
                "structured": None
                if slot["mechanism"] == "text_baseline"
                else {
                    "observed_facts": [],
                    "user_reported_facts": [],
                    "possible_patterns": [],
                    "uncertainties": [],
                    "urgency": labels[slot["case_id"]],
                },
            }
        )
        grades.append(
            {
                **slot,
                "score": 3,
                "reason": "Synthetic review",
                "grader": "test",
                "provenance_id": plan["provenance_id"],
                "output_sha256": digest(rows[-1]),
            }
        )
    return plan, rows, grades


def test_complete_s06_replay_allows_plain_text_baseline_without_structured_assessment():
    from evals.s06_mechanisms import compare_mechanisms

    plan, rows, grades = complete_s06_replay()
    assert compare_mechanisms(plan, rows, grades)["status"] == "VERIFIED_EVIDENCE"


@pytest.mark.parametrize("mechanism", ["text_baseline", "a_json_stream"])
@pytest.mark.parametrize("bad_ttft", [None, -1, float("nan"), float("inf"), True])
def test_s06_replay_rejects_missing_or_invalid_ttft(mechanism, bad_ttft):
    from evals.s06_mechanisms import compare_mechanisms

    plan, rows, grades = complete_s06_replay()
    assert compare_mechanisms(plan, rows, grades)["status"] == "VERIFIED_EVIDENCE"
    row = next(row for row in rows if row["mechanism"] == mechanism)
    row["ttft_ms"] = bad_ttft
    report = compare_mechanisms(plan, rows, grades)
    assert report["status"] == "NOT_VERIFIED"
    assert any("TTFT" in error for error in report["errors"])


def test_s06_replay_cannot_pass_an_explicitly_failed_execution():
    from evals.s06_mechanisms import compare_mechanisms

    plan, rows, grades = complete_s06_replay()
    rows[0]["status"] = "failed"
    assert compare_mechanisms(plan, rows, grades)["status"] == "NOT_VERIFIED"


@pytest.mark.parametrize("kind", ["assertion", "grade"])
@pytest.mark.parametrize(
    "damage", ["missing_provenance", "old_provenance", "missing_output_hash", "wrong_output_hash"]
)
def test_reconciliation_requires_each_assertion_and_grade_to_bind_the_exact_output(kind, damage):
    from evals.provenance import reconcile

    manifest, outputs, checks, grades = evidence()
    for grade in grades:
        grade["score"] = 3
    assert reconcile(manifest, outputs, checks, grades)["status"] == "VERIFIED_EVIDENCE"
    row = (checks if kind == "assertion" else grades)[0]
    if damage == "missing_provenance":
        row.pop("provenance_id")
    elif damage == "old_provenance":
        row["provenance_id"] = "historical-provenance"
    elif damage == "missing_output_hash":
        row.pop("output_sha256")
    else:
        row["output_sha256"] = "0" * 64
    report = reconcile(manifest, outputs, checks, grades)
    assert report["status"] == "NOT_VERIFIED"
    assert any(kind in error for error in report["errors"])


def test_replacing_a_stochastic_output_invalidates_its_existing_assertions_and_grades():
    from evals.provenance import reconcile

    manifest, outputs, checks, grades = evidence()
    for grade in grades:
        grade["score"] = 3
    assert reconcile(manifest, outputs, checks, grades)["status"] == "VERIFIED_EVIDENCE"
    outputs[0]["turns"][0]["assistant"] = "A different model answer for the same repeat"
    report = reconcile(manifest, outputs, checks, grades)
    assert report["status"] == "NOT_VERIFIED"
    assert any("assertion" in error for error in report["errors"])
    assert any("grade" in error for error in report["errors"])


@pytest.mark.parametrize(
    "damage", ["missing_provenance", "old_provenance", "missing_output_hash", "wrong_output_hash"]
)
def test_s06_grades_must_bind_the_same_provenance_and_exact_output(damage):
    from evals.s06_mechanisms import compare_mechanisms

    plan, rows, grades = complete_s06_replay()
    assert compare_mechanisms(plan, rows, grades)["status"] == "VERIFIED_EVIDENCE"
    if damage == "missing_provenance":
        grades[0].pop("provenance_id")
    elif damage == "old_provenance":
        grades[0]["provenance_id"] = "historical-provenance"
    elif damage == "missing_output_hash":
        grades[0].pop("output_sha256")
    else:
        grades[0]["output_sha256"] = "0" * 64
    report = compare_mechanisms(plan, rows, grades)
    assert report["status"] == "NOT_VERIFIED"
    assert any("grade" in error for error in report["errors"])
