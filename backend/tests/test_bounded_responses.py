import json

import httpx2
import pytest

from app.core.errors import DomainError


def body(**extra):
    return {"model": "gpt-6-luna", "store": False, "max_output_tokens": 1200,
            "instructions": "synthetic-system", "input": [{"role": "user", "content": "synthetic-history"}],
            "tools": [{"type": "function", "name": "synthetic", "parameters": {"type": "object"}}],
            "text": {"format": {"type": "json_schema", "name": "synthetic", "schema": {"type": "object"}}}, **extra}


async def test_full_payload_is_counted_before_each_generation_and_tool_expansion_is_denied():
    from app.ai.envelope import BoundedResponsesTransport

    counts, generations = [], []

    def fake(request):
        payload = json.loads(request.content)
        if request.url.path.endswith("/input_tokens"):
            counts.append(payload)
            return httpx2.Response(200, json={"object": "response.input_tokens", "input_tokens": 500 if len(counts) == 1 else 64001})
        generations.append(payload)
        return httpx2.Response(200, json={"synthetic": True})

    async with httpx2.AsyncClient(transport=BoundedResponsesTransport(httpx2.MockTransport(fake))) as client:
        payload = body()
        await client.post("https://api.openai.com/v1/responses", json=payload)
        assert generations[0] == payload
        for field in ("model", "instructions", "input", "tools", "text"):
            assert counts[0][field] == payload[field]
        assert "max_output_tokens" not in counts[0] and "store" not in counts[0]
        with pytest.raises(DomainError) as caught:
            await client.post("https://api.openai.com/v1/responses", json=body(input=[{"type": "function_call_output", "call_id": "x", "output": "expanded tool content"}]))
        assert caught.value.code == "AI_CONTEXT_LIMIT"
    assert len(generations) == 1 and len(counts) == 2


@pytest.mark.parametrize("extra", [{"max_output_tokens": 1201}, {"model": "unpriced"},
                                 {"previous_response_id": "mutable"}, {"store": True},
                                 {"tools": [{"type": "web_search"}]}])
async def test_unbounded_payload_is_rejected_without_any_external_dispatch(extra):
    from app.ai.envelope import BoundedResponsesTransport

    calls = []
    transport = BoundedResponsesTransport(httpx2.MockTransport(lambda r: calls.append(r)))
    async with httpx2.AsyncClient(transport=transport) as client:
        with pytest.raises(DomainError):
            await client.post("https://api.openai.com/v1/responses", json=body(**extra))
    assert calls == []


@pytest.mark.parametrize("response", [{"input_tokens": 10}, {"object": "response.input_tokens", "input_tokens": 0},
                                     {"object": "response.input_tokens", "input_tokens": True}])
async def test_invalid_token_count_never_dispatches_generation(response):
    from app.ai.envelope import BoundedResponsesTransport

    paths = []
    def fake(request):
        paths.append(request.url.path)
        return httpx2.Response(200, json=response)
    async with httpx2.AsyncClient(transport=BoundedResponsesTransport(httpx2.MockTransport(fake))) as client:
        with pytest.raises(DomainError):
            await client.post("https://api.openai.com/v1/responses", json=body())
    assert paths == ["/v1/responses/input_tokens"]


def test_bounded_envelope_covers_three_calls_at_conservative_rates():
    from app.ai.envelope import BOUNDED_RESERVATION_NANO

    assert BOUNDED_RESERVATION_NANO >= 3 * (64000 * 550 + 1200 * 1650)
    assert 50 * BOUNDED_RESERVATION_NANO < 50_000_000_000


@pytest.mark.parametrize("input_item", [
    {"type": "item_reference", "id": "synthetic-remote-item"},
    {"role": "user", "content": [{"type": "item_reference", "id": "synthetic-nested"}]},
])
async def test_remote_item_references_never_reach_counting_or_generation(input_item):
    from app.ai.envelope import BoundedResponsesTransport

    calls = []

    def fake(request):
        calls.append(request.url.path)
        return httpx2.Response(200, json={"object": "response.input_tokens", "input_tokens": 100})

    async with httpx2.AsyncClient(transport=BoundedResponsesTransport(httpx2.MockTransport(fake))) as client:
        with pytest.raises(DomainError):
            await client.post("https://api.openai.com/v1/responses", json=body(input=[input_item]))
    assert calls == []


def test_production_provider_fails_closed_when_the_global_budget_is_disabled():
    from app.ai.provider import SdkProvider
    from app.core.config import Settings

    settings = Settings(_env_file=None, app_env="production", openai_api_key="synthetic",
                        openai_model="gpt-6-luna", ai_daily_budget_usd=0, ai_enabled=True, ai_accounting_enabled=True,
                        frontend_origin="https://moodprint.example", supabase_url="https://synthetic.supabase.co",
                        supabase_publishable_key="synthetic", database_url="postgresql://synthetic:synthetic@db.invalid/test")
    provider = SdkProvider(settings)
    with pytest.raises(DomainError):
        provider.model(None, None)
    assert provider._client is None
