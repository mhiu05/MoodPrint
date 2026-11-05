"""Offline money-boundary tests: all prices and account attestations are synthetic."""

import importlib.util
import json
import sqlite3
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/paid_campaign.py"


def controller():
    assert SCRIPT.exists(), "durable paid campaign controller has not been implemented"
    spec = importlib.util.spec_from_file_location("paid_campaign", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def attestation():
    return {
        "environment": "staging",
        "model": "gpt-6-luna",
        "currency": "USD",
        "pricing_version": "synthetic-offline-v1",
        "input_per_million": "1000",
        "cache_write_per_million": "1000",
        "output_per_million": "1000",
        "model_access_verified": True,
        "account_pricing_verified": True,
        "quota_verified": True,
        "rpm": 10,
        "tpm": 100000,
        "evidence_sha256": "a" * 64,
        "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
    }


def ledger(tmp_path):
    module = controller()
    return module, module.Campaign.create(tmp_path / "campaign.sqlite", attestation())


def test_exact_cumulative_cap_survives_reopen_and_success(tmp_path):
    module, campaign = ledger(tmp_path)
    for number in range(3):
        item = campaign.reserve(f"attempt-{number}", input_tokens=999, max_output_tokens=1)
        assert item["reserved_usd"] == "1"
        campaign.dispatch(item["attempt_id"], lambda request: {"local": True})
        campaign.record_actual(item["attempt_id"], "0.001")
    reopened = module.Campaign.open(campaign.path)
    assert reopened.status()["held_usd"] == "3"
    with pytest.raises(ValueError, match="cap"):
        reopened.reserve("fourth", input_tokens=1, max_output_tokens=1)


@pytest.mark.parametrize(
    "change",
    [
        {"model": "gpt-6-sol"},
        {"environment": "production"},
        {"currency": "VND"},
        {"account_pricing_verified": False},
        {"quota_verified": False},
        {"model_access_verified": False},
        {"rpm": 0},
        {"tpm": 0},
        {"pricing_version": ""},
        {"evidence_sha256": ""},
        {"input_per_million": 0.1},
        {"output_per_million": "NaN"},
        {"cache_write_per_million": "-1"},
        {"input_per_million": "0.0000000000001"},
        {"expires_at": "2020-01-01T00:00:00+00:00"},
    ],
)
def test_unproven_or_invalid_preconditions_cannot_create_ledger(tmp_path, change):
    module = controller()
    with pytest.raises(ValueError):
        module.Campaign.create(tmp_path / "campaign.sqlite", {**attestation(), **change})
    assert not (tmp_path / "campaign.sqlite").exists()


def test_request_bounds_and_duplicate_attempt_rejected_without_holds(tmp_path):
    _, campaign = ledger(tmp_path)
    for bounds in [(-1, 1), (64001, 1), (1, 1201), (1, 0), (True, 1), (1.5, 1)]:
        with pytest.raises(ValueError):
            campaign.reserve("bad", input_tokens=bounds[0], max_output_tokens=bounds[1])
    campaign.reserve("same", input_tokens=1, max_output_tokens=1)
    with pytest.raises(ValueError):
        campaign.reserve("same", input_tokens=1, max_output_tokens=1)
    assert campaign.status()["held_usd"] == "0.002"


def test_decimal_rates_do_not_round_away_small_reservations(tmp_path):
    module = controller()
    config = attestation()
    for key in ("input_per_million", "cache_write_per_million", "output_per_million"):
        config[key] = "0.000000000001"
    campaign = module.Campaign.create(tmp_path / "small.sqlite", config)
    campaign.reserve("tiny", input_tokens=1, max_output_tokens=1)
    assert campaign.status()["held_usd"] == "0.000000000000000002"


def test_unknown_cancel_retry_and_duplicate_dispatch_never_release_hold(tmp_path):
    _, campaign = ledger(tmp_path)
    campaign.reserve("first", input_tokens=999, max_output_tokens=1)

    def timeout(request):
        assert request == {
            "model": "gpt-6-luna",
            "max_output_tokens": 1,
            "service_tier": "default",
            "store": False,
        }
        raise TimeoutError("unknown provider outcome")

    with pytest.raises(TimeoutError):
        campaign.dispatch("first", timeout)
    with pytest.raises(ValueError):
        campaign.dispatch("first", lambda request: pytest.fail("duplicate wire attempt"))
    campaign.reserve("retry", input_tokens=999, max_output_tokens=1)
    campaign.cancel("retry")
    with pytest.raises(ValueError):
        campaign.dispatch("retry", lambda request: pytest.fail("cancelled wire attempt"))
    assert campaign.status()["held_usd"] == "2"
    assert [item["state"] for item in campaign.status()["attempts"]] == ["unknown", "cancelled"]


def test_actual_usage_above_reservation_freezes_future_admission(tmp_path):
    _, campaign = ledger(tmp_path)
    campaign.reserve("overrun", input_tokens=1, max_output_tokens=1)
    campaign.dispatch("overrun", lambda request: {})
    with pytest.raises(ValueError, match="exceeds"):
        campaign.record_actual("overrun", "0.003")
    with pytest.raises(ValueError, match="frozen"):
        campaign.reserve("later", input_tokens=1, max_output_tokens=1)
    assert campaign.status()["frozen"] is True


def test_expired_attestation_blocks_dispatch_after_reservation(tmp_path):
    module, campaign = ledger(tmp_path)
    campaign.reserve("stale", input_tokens=1, max_output_tokens=1)
    future = datetime.now(UTC) + timedelta(hours=2)
    with pytest.raises(ValueError, match="expired"):
        module.Campaign.open(campaign.path, now=lambda: future).dispatch(
            "stale", lambda request: pytest.fail("expired wire attempt")
        )
    assert campaign.status()["held_usd"] == "0.002"


def test_process_death_during_dispatch_retains_durable_hold(tmp_path):
    module, campaign = ledger(tmp_path)
    campaign.reserve("crash", input_tokens=999, max_output_tokens=1)
    code = (
        "import os; from scripts.paid_campaign import Campaign; "
        f"Campaign.open({str(campaign.path)!r}).dispatch('crash', lambda request: os._exit(27))"
    )
    result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, check=False)
    assert result.returncode == 27
    recovered = module.Campaign.open(campaign.path)
    assert recovered.status()["held_usd"] == "1"
    assert recovered.status()["attempts"][0]["state"] == "dispatching"
    with pytest.raises(ValueError):
        recovered.dispatch("crash", lambda request: pytest.fail("crash must not retry"))


def test_concurrent_processes_cannot_reserve_more_than_three_dollars(tmp_path):
    _, campaign = ledger(tmp_path)
    code = """
import sys
from scripts.paid_campaign import Campaign
try:
    Campaign.open(sys.argv[1]).reserve(sys.argv[2], input_tokens=999, max_output_tokens=1)
except ValueError:
    sys.exit(3)
"""
    children = [
        subprocess.Popen(
            [sys.executable, "-c", code, str(campaign.path), str(n)],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for n in range(12)
    ]
    codes = []
    for child in children:
        _, error = child.communicate(timeout=30)
        assert not error, error.decode()
        codes.append(child.returncode)
    assert codes.count(0) == 3
    assert codes.count(3) == 9
    assert campaign.status()["held_usd"] == "3"


def test_existing_missing_or_corrupt_ledger_fails_closed(tmp_path):
    module, campaign = ledger(tmp_path)
    with pytest.raises(FileExistsError):
        module.Campaign.create(campaign.path, attestation())
    with pytest.raises(FileNotFoundError):
        module.Campaign.open(tmp_path / "missing.sqlite")
    corrupt = tmp_path / "corrupt.sqlite"
    corrupt.write_text("corrupt", encoding="utf8")
    with pytest.raises(sqlite3.DatabaseError):
        module.Campaign.open(corrupt)


def test_status_cli_is_read_only_and_sanitized(tmp_path):
    _, campaign = ledger(tmp_path)
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "status", str(campaign.path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["held_usd"] == "0"
    assert "evidence_sha256" not in result.stdout
