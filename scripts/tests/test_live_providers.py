"""No paid request may escape either provider's existing cumulative ledger."""

import importlib.util
import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path.cwd() / "agent"))


def module():
    path = Path(__file__).resolve().parents[1] / "live_providers.py"
    assert path.exists(), "The bounded real-runtime provider composition is missing"
    spec = importlib.util.spec_from_file_location("live_providers", path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


async def test_voyage_transport_reserves_and_settles_original_ledger(tmp_path):
    provider = module()
    ledger = tmp_path / "voyage-ledger.json"
    state = {
        "schema": 1,
        "max_usd": "1.00",
        "spent_usd": "0.10",
        "reserved_usd": "0",
        "reservations": {},
    }
    ledger.write_text(json.dumps(state))

    def reply(request):
        current = json.loads(ledger.read_text())
        assert float(current["reserved_usd"]) > 0
        assert current["reservations"]
        return httpx.Response(200, json={"usage": {"total_tokens": 10}, "data": []})

    transport = provider.VoyageTransport(ledger, inner=httpx.MockTransport(reply))
    async with httpx.AsyncClient(transport=transport) as client:
        response = await client.post(
            "https://api.voyageai.com/v1/embeddings",
            json={"model": "voyage-4", "input": ["synthetic"], "output_dimension": 1024},
        )
    assert response.status_code == 200
    current = json.loads(ledger.read_text())
    assert float(current["spent_usd"]) > 0.10
    assert float(current["reserved_usd"]) == 0
    assert not current["reservations"]


async def test_voyage_timeout_retains_conservative_charge(tmp_path):
    provider = module()
    ledger = tmp_path / "voyage-ledger.json"
    ledger.write_text(
        json.dumps(
            {"max_usd": "1.00", "spent_usd": "0.10", "reserved_usd": "0", "reservations": {}}
        )
    )

    def timeout(request):
        raise httpx.ReadTimeout("synthetic", request=request)

    async with httpx.AsyncClient(
        transport=provider.VoyageTransport(ledger, inner=httpx.MockTransport(timeout))
    ) as client:
        with pytest.raises(httpx.ReadTimeout):
            await client.post(
                "https://api.voyageai.com/v1/embeddings",
                json={"model": "voyage-4", "input": ["synthetic"], "output_dimension": 1024},
            )
    assert float(json.loads(ledger.read_text())["spent_usd"]) > 0.10


async def test_voyage_cannot_create_replacement_ledger_or_use_another_model(tmp_path):
    provider = module()
    with pytest.raises(ValueError, match="existing"):
        provider.VoyageTransport(tmp_path / "missing.json")
    ledger = tmp_path / "voyage-ledger.json"
    ledger.write_text(
        json.dumps({"max_usd": "1.00", "spent_usd": "0", "reserved_usd": "0", "reservations": {}})
    )

    def forbidden(request):
        pytest.fail("Rejected requests must never reach the provider")

    async with httpx.AsyncClient(
        transport=provider.VoyageTransport(ledger, inner=httpx.MockTransport(forbidden))
    ) as client:
        with pytest.raises(ValueError):
            await client.post(
                "https://api.voyageai.com/v1/embeddings",
                json={"model": "voyage-4-large", "input": ["synthetic"], "output_dimension": 1024},
            )


async def test_provider_trace_keeps_request_id_usage_and_outputs_without_request_secrets(tmp_path):
    provider = module()
    trace = tmp_path / "trace.jsonl"
    response = {
        "id": "resp_synthetic",
        "model": "gpt-6-luna",
        "usage": {"input_tokens": 10, "output_tokens": 5},
        "output": [{"type": "message", "content": [{"text": "Synthetic output"}]}],
    }
    transport = provider.RecordingTransport(
        httpx.MockTransport(
            lambda r: httpx.Response(200, json=response, headers={"x-request-id": "req_synthetic"})
        ),
        trace,
    )
    async with httpx.AsyncClient(transport=transport) as client:
        await client.post(
            "https://api.openai.com/v1/responses",
            json={"private": "SECRET-CANARY"},
            headers={"Authorization": "Bearer SECRET-KEY"},
        )
    row = json.loads(trace.read_text())
    assert row["request_id"] == "req_synthetic"
    assert row["response"]["id"] == "resp_synthetic"
    assert row["response"]["usage"]["output_tokens"] == 5
    assert "SECRET" not in trace.read_text()


async def test_standard_tier_is_explicit_before_the_existing_budget_boundary():
    provider = module()
    seen = []

    async def transport(request):
        seen.append(json.loads(await request.aread()))
        return httpx.Response(200, json={"usage": {}})

    assert hasattr(provider, "DefaultTierTransport"), "Explicit standard processing is missing"
    async with httpx.AsyncClient(
        transport=provider.DefaultTierTransport(httpx.MockTransport(transport))
    ) as client:
        await client.post(
            "https://api.openai.com/v1/responses", json={"model": "gpt-6-luna", "store": False}
        )
        with pytest.raises(ValueError):
            await client.post(
                "https://api.openai.com/v1/responses",
                json={"model": "gpt-6-luna", "service_tier": "priority"},
            )
    assert len(seen) == 1
    assert seen[0]["service_tier"] == "default"


async def test_complete_metered_wrapper_shutdown_closes_the_inner_connection_pool(tmp_path):
    from evals.budget import GuardedTransport

    provider = module()

    class Pool(httpx.AsyncBaseTransport):
        closed = False

        async def handle_async_request(self, request):
            pytest.fail("Shutdown must not send any provider request")

        async def aclose(self):
            self.closed = True

    pool = Pool()
    # No generation is requested; the ledger is never accessed in this lifetime probe.
    guard = GuardedTransport(pool, None, run_id="synthetic-shutdown")
    client = httpx.AsyncClient(
        transport=provider.RecordingTransport(
            provider.DefaultTierTransport(guard), tmp_path / "unused-trace.jsonl"
        )
    )
    await client.aclose()
    assert pool.closed
