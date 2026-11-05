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
