"""Product evidence must exercise runtime boundaries and never manufacture live grades."""

import importlib.util

import pytest


def test_product_evaluation_has_a_runnable_offline_entrypoint() -> None:
    assert importlib.util.find_spec("evals.product") is not None, (
        "The product matrix needs a runnable runtime-backed offline harness."
    )


@pytest.mark.parametrize("case_id", [f"PC-{n:02}" for n in range(1, 21)])
async def test_product_scenario_records_observed_runtime_and_action_results(case_id: str) -> None:
    from evals.product import evaluate, load_cases

    case = next(c for c in load_cases() if c["id"] == case_id)
    record = await evaluate(case)
    assert record["checks"], "An executed case without assertions is not evidence."
    assert all(check["passed"] for check in record["checks"]), record["checks"]
    assert record["turns"] and record["events"]
    assert record["live_status"] == "NOT_RUN"
    assert record["rubric_scores"] == {}, "Scripted prose cannot earn semantic quality grades."


async def test_product_checker_rejects_missing_execution_and_unauthorised_writes() -> None:
    from evals.product import check_record, evaluate, load_cases

    case = load_cases()[0]
    record = await evaluate(case)
    record["events"] = []
    record["writes"] = 1
    record["model_calls"] = []
    failed = {c["id"] for c in check_record(case, record) if not c["passed"]}
    assert {"execution", "writes", "prompt_binding"} <= failed


async def test_product_checker_detects_a_missing_event_and_a_different_saved_payload() -> None:
    from evals.product import check_record, evaluate, load_cases

    case = next(c for c in load_cases() if c["id"] == "PC-08")
    record = await evaluate(case)
    record["events"].pop(1)
    record["events_written"][0]["event"]["description"] = "Nội dung khác bản đã duyệt"
    failed = {c["id"] for c in check_record(case, record) if not c["passed"]}
    assert {"event_sequence", "approved_payload"} <= failed


async def test_product_artifacts_bind_each_trace_to_the_prompt_snapshot(tmp_path) -> None:
    import json

    from evals.product import load_cases, run
    from evals.provenance import digest

    assert await run(tmp_path) == 0
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    rows = [
        json.loads(line)
        for line in (tmp_path / "outputs.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert len(rows) == 20 and len({r["case_id"] for r in rows}) == 20
    assert manifest["live_status"] == "NOT_RUN" and manifest["paid_provider_calls"] == 0
    assert manifest["authorization_request"]["max_provider_requests"] == 690
    assert manifest["authorization_request"]["max_tokens"] == 3600000
    assert len(manifest["provenance"]["prompt_sha256"]["companion_v5"]) == 64
    assert digest(manifest["provenance"]) == manifest["provenance_id"]
    cases = {c["id"]: c for c in load_cases()}
    for row in rows:
        assert row["provenance_id"] == manifest["provenance_id"]
        assert row["case_sha256"] == digest(cases[row["case_id"]])
        output_hash = row.pop("output_sha256")
        assert output_hash == digest(row)
