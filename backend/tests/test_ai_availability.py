"""Availability describes service configuration, independently of user consent."""

import json
from uuid import uuid4

import pytest
from pydantic import SecretStr

from app.ai.runtime import AiRuntime
from app.core.config import Settings
from tests.fakes import make_test_model


@pytest.mark.parametrize(
    "status,expected",
    [
        (401, "AI_PROVIDER_CONFIGURATION"),
        (403, "AI_PROVIDER_CONFIGURATION"),
        (404, "AI_PROVIDER_CONFIGURATION"),
        (429, "AI_PROVIDER_RATE_LIMIT"),
        (503, "AI_PROVIDER_UNAVAILABLE"),
    ],
)
def test_provider_http_errors_are_sanitized(status, expected):
    import httpx2
    from openai import (
        AuthenticationError,
        InternalServerError,
        NotFoundError,
        PermissionDeniedError,
        RateLimitError,
    )

    from app.ai.availability import public_failure

    kinds = {
        401: AuthenticationError,
        403: PermissionDeniedError,
        404: NotFoundError,
        429: RateLimitError,
        503: InternalServerError,
    }
    error = kinds[status](
        "PRIVATE-DETAIL",
        response=httpx2.Response(
            status, request=httpx2.Request("POST", "https://api.openai.com/v1/responses")
        ),
        body={"private": "PRIVATE-DETAIL"},
    )
    result = public_failure(error)
    assert result["code"] == expected
    assert "PRIVATE-DETAIL" not in json.dumps(result)


def test_timeout_and_database_failures_are_not_provider_configuration_errors():
    from sqlalchemy.exc import OperationalError

    from app.ai.availability import public_failure

    assert public_failure(TimeoutError())["code"] == "AI_TIMEOUT"
    error = OperationalError("PRIVATE-SQL", {}, RuntimeError("PRIVATE-DETAIL"))
    result = public_failure(error)
    assert result["code"] == "AI_STORAGE_UNAVAILABLE"
    assert "PRIVATE" not in json.dumps(result)


@pytest.mark.parametrize(
    "enabled,key,model,status",
    [
        (False, "", "", "disabled"),
        (True, "", "configured-model", "configuration_missing"),
        (True, "synthetic-key", "", "configuration_missing"),
        (True, "synthetic-key\n", "configured-model", "configuration_invalid"),
        (True, "synthetic-key", "configured-model", "ready"),
    ],
)
def test_configuration_states_do_not_require_network(enabled, key, model, status):
    runtime = AiRuntime(
        Settings(_env_file=None, ai_enabled=enabled, openai_api_key=key, openai_model=model), None
    )
    assert runtime.status_for(uuid4()) == status
    assert runtime.available == (status == "ready")


@pytest.mark.postgres
async def test_session_distinguishes_consent_service_and_synthetic_provider(clients):
    app, actors = clients
    client, uid = actors[0]
    initial = (await client.get("/api/v1/session")).json()
    assert initial["features"]["aiStatus"] == "disabled"
    app.state.settings.ai_enabled = True
    app.state.settings.openai_api_key = SecretStr("synthetic-key")
    app.state.settings.openai_model = "configured-model"
    configured = (await client.get("/api/v1/session")).json()
    assert configured["features"]["aiStatus"] == "ready"
    assert configured["features"]["ai"] is True
    assert configured["consents"]["AI"]["enabled"] is False
    denied = await client.post(
        "/api/v1/ai/conversations", json={"botId": "may"}, headers={"Idempotency-Key": str(uuid4())}
    )
    assert denied.status_code == 403
    app.state.ai.model_override = make_test_model("Synthetic only")
    synthetic = (await client.get("/api/v1/session")).json()
    assert synthetic["features"]["aiStatus"] == "test_provider"
    assert app.state.ai.available_for(uid)


@pytest.mark.postgres
async def test_provider_failure_stream_is_classified_without_leaking_details(clients):
    import httpx2
    from openai import AuthenticationError

    app, actors = clients
    client = actors[0][0]
    app.state.ai.model_override = make_test_model("Never emitted")

    async def broken(**kwargs):
        raise AuthenticationError(
            "PRIVATE-PROVIDER-DETAIL",
            response=httpx2.Response(
                401, request=httpx2.Request("POST", "https://api.openai.com/v1/responses")
            ),
            body={"secret": "PRIVATE-PROVIDER-DETAIL"},
        )

    app.state.ai.provider.run = broken
    await client.put(
        "/api/v1/consents/AI",
        json={"enabled": True, "expectedVersion": 1, "policyVersion": "v1"},
        headers={"Idempotency-Key": str(uuid4())},
    )
    created = await client.post(
        "/api/v1/ai/conversations", json={"botId": "may"}, headers={"Idempotency-Key": str(uuid4())}
    )
    accepted = await client.post(
        f"/api/v1/ai/conversations/{created.json()['conversationId']}/messages",
        json={
            "text": "Synthetic input",
            "clientMessageId": str(uuid4()),
            "expectedConversationVersion": 1,
        },
        headers={"Idempotency-Key": str(uuid4())},
    )
    stream = await client.get(accepted.json()["eventsUrl"])
    events = [
        json.loads(line[6:]) for line in stream.text.splitlines() if line.startswith("data: ")
    ]
    assert events[-1]["type"] == "failed"
    assert events[-1]["data"]["code"] == "AI_PROVIDER_CONFIGURATION"
    assert "PRIVATE-PROVIDER-DETAIL" not in stream.text
    assert not any(event["type"] == "final" for event in events)
