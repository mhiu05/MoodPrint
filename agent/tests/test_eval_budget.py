"""The paid-call gate: nothing is sent without an owner-approved, unexpired, in-scope budget."""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from evals.budget import (
    BudgetError,
    BudgetExhausted,
    BudgetInvalid,
    BudgetLedger,
    GuardedTransport,
    load_budget,
)


def _doc(**overrides: object) -> dict[str, object]:
    doc: dict[str, object] = {
        "approved_by": "owner",
        "approved_on": "2026-11-08",
        "model": "gpt-6-luna",
        "max_usd": 1.0,
        "max_tokens_total": 100_000,
        "max_tokens_per_run": 40_000,
        "max_calls_total": 5,
        "max_output_tokens_per_request": 1_000,
        "pricing": {
            "verified_on": "2026-11-08",
            "source": "https://developers.openai.com/api/docs/pricing",
            "service_tier": "default",
            "max_input_tokens": 272_000,
            "price_usd_per_mtok": {"input": 0.10, "cached_input": 0.01, "output": 0.50},
        },
        "scopes": ["phase3-live-compat"],
        "expires_on": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
    }
    doc.update(overrides)
    return doc


def _write(tmp_path: Path, doc: dict[str, object]) -> Path:
    path = tmp_path / "eval-budget.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def _ledger(tmp_path: Path, **overrides: object) -> BudgetLedger:
    budget = load_budget(_write(tmp_path, _doc(**overrides)), scope="phase3-live-compat")
    return BudgetLedger(budget, tmp_path / "spend.jsonl")


def test_missing_file_is_refused_with_exit_code_three(tmp_path: Path) -> None:
    with pytest.raises(BudgetInvalid) as info:
        load_budget(tmp_path / "absent.json", scope="phase3-live-compat")
    assert info.value.exit_code == 3


@pytest.mark.parametrize(
    "overrides",
    [
        {"model": "gpt-5"},
        {"expires_on": "2020-01-01T00:00:00+00:00"},
        {"expires_on": "2099-01-01"},  # naive date: expiry must be an explicit UTC instant
        {"approved_by": "<owner điền>"},
        {"max_usd": "<owner điền>"},
        {"max_calls_total": 0},
        {"scopes": ["phase3-eval"]},
    ],
)
def test_invalid_or_wrong_scope_budget_is_refused(
    tmp_path: Path, overrides: dict[str, object]
) -> None:
    with pytest.raises(BudgetInvalid):
        load_budget(_write(tmp_path, _doc(**overrides)), scope="phase3-live-compat")


def test_template_placeholders_are_not_an_approval(tmp_path: Path) -> None:
    doc = _doc()
    for key in ("max_usd", "max_tokens_total", "max_calls_total", "max_output_tokens_per_request"):
        doc[key] = f"<owner điền {key}>"
    with pytest.raises(BudgetInvalid):
        load_budget(_write(tmp_path, doc), scope="phase3-live-compat")


def test_reservation_is_made_before_the_call_and_uses_conservative_cost(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    reservation = ledger.reserve(
        model="gpt-6-luna", input_tokens=10_000, max_output_tokens=1_000, run_id="r1"
    )
    # 10_000 in * $0.10/M + 1_000 out * $0.50/M, never the cheaper cached price
    assert reservation.usd == pytest.approx(10_000 * 0.10e-6 + 1_000 * 0.50e-6)
    assert ledger.reserved_calls == 1
    assert ledger.reserved_tokens == 11_000


def test_call_count_cap_refuses_before_the_next_request(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path, max_calls_total=2)
    for _ in range(2):
        ledger.reserve(model="gpt-6-luna", input_tokens=10, max_output_tokens=10, run_id="r")
    with pytest.raises(BudgetExhausted):
        ledger.reserve(model="gpt-6-luna", input_tokens=10, max_output_tokens=10, run_id="r")
    assert ledger.reserved_calls == 2


def test_token_usd_and_per_run_caps(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path, max_tokens_total=5_000, max_tokens_per_run=3_000)
    with pytest.raises(BudgetExhausted):  # over per-run cap in one request
        ledger.reserve(model="gpt-6-luna", input_tokens=3_000, max_output_tokens=500, run_id="r")
    ledger.reserve(model="gpt-6-luna", input_tokens=2_000, max_output_tokens=500, run_id="r")
    with pytest.raises(BudgetExhausted):  # per-run total would be 5_000 > 3_000
        ledger.reserve(model="gpt-6-luna", input_tokens=2_000, max_output_tokens=500, run_id="r")
    ledger.reserve(model="gpt-6-luna", input_tokens=2_000, max_output_tokens=500, run_id="r2")
    with pytest.raises(BudgetExhausted):  # global token cap
        ledger.reserve(model="gpt-6-luna", input_tokens=1_000, max_output_tokens=500, run_id="r3")


def test_usd_cap(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path, max_usd=0.0001, max_tokens_total=10_000_000)
    with pytest.raises(BudgetExhausted):
        ledger.reserve(
            model="gpt-6-luna", input_tokens=200_000, max_output_tokens=1_000, run_id="r"
        )


def test_output_cap_wrong_model_and_long_context_are_refused(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    with pytest.raises(BudgetError):
        ledger.reserve(model="gpt-6-luna", input_tokens=10, max_output_tokens=5_000, run_id="r")
    with pytest.raises(BudgetError):
        ledger.reserve(model="gpt-5", input_tokens=10, max_output_tokens=10, run_id="r")
    with pytest.raises(BudgetError):  # price table only covers <= 272K input
        ledger.reserve(model="gpt-6-luna", input_tokens=272_001, max_output_tokens=10, run_id="r")


def test_reconcile_releases_unused_reservation_but_unknown_keeps_it(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    ok = ledger.reserve(model="gpt-6-luna", input_tokens=1_000, max_output_tokens=1_000, run_id="r")
    unknown = ledger.reserve(
        model="gpt-6-luna", input_tokens=1_000, max_output_tokens=1_000, run_id="r"
    )
    ledger.reconcile(ok, input_tokens=100, output_tokens=50, cached_input_tokens=0)
    ledger.mark_unknown(unknown)
    assert ledger.spent_tokens == 150
    assert ledger.reserved_tokens == 2_000  # the unknown call keeps its conservative hold
    lines = (tmp_path / "spend.jsonl").read_text(encoding="utf-8").splitlines()
    kinds = [json.loads(line)["kind"] for line in lines]
    assert kinds == ["reserve", "reserve", "reconcile", "unknown"]
    assert "content" not in lines[0]


def test_ledger_survives_a_new_process(tmp_path: Path) -> None:
    first = _ledger(tmp_path, max_calls_total=2)
    first.reserve(model="gpt-6-luna", input_tokens=10, max_output_tokens=10, run_id="r")
    second = _ledger(tmp_path, max_calls_total=2)
    assert second.reserved_calls == 1
    second.reserve(model="gpt-6-luna", input_tokens=10, max_output_tokens=10, run_id="r")
    with pytest.raises(BudgetExhausted):
        _ledger(tmp_path, max_calls_total=2).reserve(
            model="gpt-6-luna", input_tokens=10, max_output_tokens=10, run_id="r"
        )


async def test_concurrent_reservations_cannot_overshoot(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path, max_calls_total=3)

    async def attempt() -> bool:
        await asyncio.sleep(0)
        try:
            ledger.reserve(model="gpt-6-luna", input_tokens=10, max_output_tokens=10, run_id="r")
        except BudgetExhausted:
            return False
        return True

    results = await asyncio.gather(*(attempt() for _ in range(20)))
    assert sum(results) == 3


def _request(
    body: dict[str, object], url: str = "https://api.openai.com/v1/responses"
) -> httpx.Request:
    return httpx.Request("POST", url, json=body)


async def test_transport_blocks_without_sending_when_unsafe(tmp_path: Path) -> None:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, json={"usage": {"input_tokens": 3, "output_tokens": 2}})

    ledger = _ledger(tmp_path, max_calls_total=2)
    transport = GuardedTransport(httpx.MockTransport(handler), ledger, run_id="r")
    async with httpx.AsyncClient(transport=transport) as client:
        good = {"model": "gpt-6-luna", "store": False, "max_output_tokens": 100, "input": "hi"}
        assert (await client.send(_request(good))).status_code == 200
        for bad in (
            {**good, "store": True},
            {**good, "model": "gpt-5"},
            {k: v for k, v in good.items() if k != "max_output_tokens"},
            {k: v for k, v in good.items() if k != "store"},
        ):
            with pytest.raises(BudgetError):
                await client.send(_request(bad))
    assert len(sent) == 1
    assert ledger.reserved_calls == 1  # refused requests never reach the ledger


async def test_transport_counts_every_http_attempt_and_stops_at_the_cap(tmp_path: Path) -> None:
    sent = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal sent
        sent += 1
        return httpx.Response(500)

    ledger = _ledger(tmp_path, max_calls_total=2)
    transport = GuardedTransport(httpx.MockTransport(handler), ledger, run_id="r")
    body = {"model": "gpt-6-luna", "store": False, "max_output_tokens": 50, "input": "hi"}
    async with httpx.AsyncClient(transport=transport) as client:
        await client.send(_request(body))
        await client.send(_request(body))
        with pytest.raises(BudgetExhausted):
            await client.send(_request(body))
    assert sent == 2  # the third attempt never left the process
    assert ledger.unknown_calls == 2  # a 5xx without usage keeps its reservation


async def test_non_paid_hosts_are_not_forwarded_at_all(tmp_path: Path) -> None:
    transport = GuardedTransport(
        httpx.MockTransport(lambda r: httpx.Response(200)), _ledger(tmp_path), run_id="r"
    )
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(BudgetError):
            await client.send(_request({}, url="https://example.com/v1/responses"))
