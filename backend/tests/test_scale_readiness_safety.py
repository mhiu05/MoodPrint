import asyncio
import importlib.util
from pathlib import Path
from uuid import uuid4

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("scale_cli", ROOT / "scripts/scale_readiness.py")


def load_cli():
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def manifest(run_id):
    return {"run_id": run_id, "environment": "L0", "provider": "fake", "workers": 1,
            "users": 50, "duration_seconds": 900, "warmup_seconds": 0,
            "egress": "denied", "ai_daily_budget_usd": 50, "accounting": True,
            "target": {"host": "127.0.0.1", "database": f"moodprint_{run_id}_test", "port": 55439}}


@pytest.mark.parametrize("change", [
    {"environment": "L2"}, {"provider": "openai"}, {"workers": 2}, {"egress": "allowed"},
    {"accounting": False}, {"ai_daily_budget_usd": 0}, {"openai_api_key": "secret-canary"},
    {"target": {"host": "db.example.com", "database": "postgres", "port": 5432}},
])
def test_unsafe_manifest_is_rejected_before_any_provider_or_database_call(change, tmp_path, monkeypatch):
    cli = load_cli()
    run_id = uuid4().hex
    monkeypatch.setenv("MOODPRINT_TEST_RUN_ID", run_id)
    data = {**manifest(run_id), **change}
    with pytest.raises(ValueError):
        cli.validate_manifest(data, "T4", tmp_path / "new.json")


def test_output_overwrite_and_paid_case_are_rejected(tmp_path, monkeypatch):
    cli = load_cli()
    run_id = uuid4().hex
    monkeypatch.setenv("MOODPRINT_TEST_RUN_ID", run_id)
    output = tmp_path / "result.json"
    output.write_text("original", encoding="utf8")
    with pytest.raises(ValueError):
        cli.validate_manifest(manifest(run_id), "T4", output)
    with pytest.raises(ValueError):
        cli.validate_manifest(manifest(run_id), "T5", tmp_path / "paid.json")
    assert output.read_text() == "original"


def test_cleanup_requires_exact_manifest_ownership(monkeypatch):
    cli = load_cli()
    first, second = uuid4().hex, uuid4().hex
    monkeypatch.setenv("MOODPRINT_TEST_RUN_ID", first)
    with pytest.raises(ValueError):
        cli.validate_manifest(manifest(second), "T1", Path("new-result.json"))


def ai_result():
    return {"requested_users": 50, "requested_duration_seconds": 900,
            "measured_window_seconds": 900, "mean_parent_occupancy": 45,
            "peaks": {"parent_turns": 50}, "attempts": 1900, "completed": 1900,
            "errors": {}, "measurement_errors": {}, "statuses": {"202": 1900}, "financial_invariant": True,
            "pool_acquisition_recent_window": {"p95_ms": 99, "p99_ms": 499, "timeouts": 0, "acquisitions": 10000,
                "whole_run": {"samples": 10000, "p95_lt_100ms": True, "p99_lt_500ms": True}},
            "latency_including_rejections": {"p95_ms": 30000, "p99_ms": 60000},
            "event_loop_lag": {"p95_ms": 99}}


@pytest.mark.parametrize(("path", "value", "failed_gate"), [
    (("latency_including_rejections", "p95_ms"), 30001, "completion_latency"),
    (("latency_including_rejections", "p99_ms"), 60001, "completion_latency"),
    (("latency_including_rejections", "p95_ms"), None, "completion_latency"),
    (("latency_including_rejections", "p95_ms"), float("nan"), "completion_latency"),
    (("pool_acquisition_recent_window", "p95_ms"), 100, "pool_recent_window"),
    (("pool_acquisition_recent_window", "p99_ms"), 500, "pool_recent_window"),
    (("pool_acquisition_recent_window", "timeouts"), 1, "pool_recent_window"),
    (("event_loop_lag", "p95_ms"), 100, "event_loop_lag"),
    (("measured_window_seconds",), 899.9996, "full_measurement_window"),
    (("mean_parent_occupancy",), 44.999, "parent_occupancy"),
    (("measurement_errors",), {"sampler": "RuntimeError"}, "measurement_health"),
    (("financial_invariant",), False, "financial_invariant"),
    (("completed",), 1899, "all_turns_completed"),
    (("errors",), {"noncompleted_stream": 1}, "all_turns_completed"),
    (("statuses",), {"202": 1899, "503": 1}, "all_turns_completed"),
])
def test_ai_probe_rejects_local_slo_failure_even_with_fifty_parents(path, value, failed_gate):
    result = ai_result()
    target = result
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = value
    gates = load_cli().ai_local_gates(result)
    assert gates[failed_gate] is False
    assert not all(gates.values())


def test_ai_probe_accepts_exact_local_boundaries_without_claiming_release_readiness():
    assert all(load_cli().ai_local_gates(ai_result()).values())


@pytest.mark.parametrize("field", ["p95_lt_100ms", "p99_lt_500ms"])
def test_recent_pool_window_cannot_hide_whole_run_checkout_pressure(field):
    result = ai_result()
    result["pool_acquisition_recent_window"]["whole_run"][field] = False
    assert load_cli().ai_local_gates(result)["pool_whole_run"] is False


def test_latency_percentile_must_not_round_an_slo_failure_into_a_pass():
    cli = load_cli()
    result = ai_result()
    result["latency_including_rejections"] = cli.percentiles([30000.0001])
    assert cli.ai_local_gates(result)["completion_latency"] is False


@pytest.mark.parametrize("fail", [False, True])
async def test_measurement_failure_or_early_exit_cannot_leave_a_stale_passing_result(fail):
    cli = load_cli()
    stop, late = asyncio.Event(), asyncio.Event()

    async def sampler():
        await late.wait()
        if fail:
            raise RuntimeError("sensitive failure details must not appear in the report")

    tasks = {"sampler": asyncio.create_task(sampler()), "loop": asyncio.create_task(stop.wait())}
    late.set()
    await asyncio.sleep(0)
    try:
        errors = await cli.finish_measurements(stop, tasks)
        assert errors == {"sampler": "RuntimeError" if fail else "StoppedEarly"}
        result = ai_result()
        result["measurement_errors"] = errors
        assert cli.ai_local_gates(result)["measurement_health"] is False
        assert all(task.done() for task in tasks.values())
    finally:
        stop.set()
        await asyncio.gather(*tasks.values(), return_exceptions=True)
