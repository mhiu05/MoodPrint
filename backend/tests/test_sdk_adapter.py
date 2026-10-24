import asyncio
import json

import httpx2 as httpx
import pytest
from agents import (
    MaxTurnsExceeded,
    ModelBehaviorError,
    OutputGuardrailTripwireTriggered,
    function_tool,
)
from agents.models.interface import ModelTracing
from openai import AsyncOpenAI, InternalServerError
from pydantic import SecretStr

from app.ai.provider import SdkProvider
from app.core.config import Settings
from app.core.errors import DomainError
from tests.fakes import (
    ScriptedModel,
    completed_response,
    make_test_model,
    message_output,
    tool_output,
)


async def no_progress():
    pass


@pytest.mark.parametrize("bot_id", ["may", "guong", "nhip", "rure", "caunoi"])
async def test_real_sdk_streams_typed_output_with_private_run_configuration(bot_id, caplog):
    model = make_test_model("Một phản hồi tổng hợp từ SDK.")
    progress = []

    async def report():
        progress.append("progress")

    output = await SdkProvider(Settings()).run(
        bot_id=bot_id,
        history=[{"role": "user", "content": "PRIVATE-INPUT-CANARY"}],
        tools=[],
        context={},
        on_progress=report,
        model_override=model,
    )
    assert output.text == "Một phản hồi tổng hợp từ SDK."
    assert output.cards == []
    assert model.stream_finished
    assert len(model.calls) == 1
    assert model.calls[0]["tracing"] == ModelTracing.DISABLED
    settings = model.calls[0]["settings"]
    assert (settings.store, settings.parallel_tool_calls, settings.max_tokens) == (
        False,
        False,
        1200,
    )
    assert settings.retry.max_retries == 0
    assert progress == ["progress"]
    assert "CANARY" not in caplog.text


async def test_unknown_bot_fails_before_model_execution():
    model = make_test_model("Hello")
    with pytest.raises(DomainError) as error:
        await SdkProvider(Settings()).run(
            bot_id="unknown",
            history=[],
            tools=[],
            context=None,
            on_progress=no_progress,
            model_override=model,
        )
    assert error.value.code == "BOT_NOT_FOUND"
    assert model.calls == []


async def test_unconfigured_provider_fails_without_scripted_reply():
    with pytest.raises(DomainError) as error:
        await SdkProvider(Settings()).run(
            bot_id="may", history=[], tools=[], context=None, on_progress=no_progress
        )
    assert error.value.code == "AI_UNAVAILABLE"


@pytest.mark.parametrize(
    "payload",
    [
        {"text": "", "cards": []},
        {"text": "x" * 6001, "cards": []},
        {"text": "hello", "cards": [{"kind": "execute_sql"}]},
    ],
)
async def test_invalid_structured_output_never_becomes_a_final_response(payload):
    model = ScriptedModel([[message_output(json.dumps(payload))]])
    with pytest.raises((ModelBehaviorError, ValueError)):
        await SdkProvider(Settings()).run(
            bot_id="may",
            history=[],
            tools=[],
            context=None,
            on_progress=no_progress,
            model_override=model,
        )


async def test_two_tools_then_final_use_exactly_three_model_calls():
    executed = []

    @function_tool
    async def inspect_profile() -> str:
        """Read synthetic profile data."""
        executed.append("read")
        return "a synthetic result"

    model = ScriptedModel(
        [
            [tool_output("inspect_profile", "call_1")],
            [tool_output("inspect_profile", "call_2")],
            [message_output('{"text":"Done reading","cards":[]}')],
        ]
    )
    result = await SdkProvider(Settings()).run(
        bot_id="guong",
        history=[],
        tools=[inspect_profile],
        context=None,
        on_progress=no_progress,
        model_override=model,
    )
    assert result.text == "Done reading"
    assert executed == ["read", "read"]
    assert len(model.calls) == 3


async def test_third_tool_is_blocked_before_execution_and_no_fourth_model_call():
    executed = []

    @function_tool
    async def inspect_profile() -> str:
        """Read synthetic profile data."""
        executed.append("read")
        return "a synthetic result"

    model = ScriptedModel([[tool_output("inspect_profile", f"call_{n}")] for n in range(1, 5)])
    with pytest.raises(DomainError) as error:
        await SdkProvider(Settings()).run(
            bot_id="guong",
            history=[],
            tools=[inspect_profile],
            context=None,
            on_progress=no_progress,
            model_override=model,
        )
    assert error.value.code == "TOOL_LIMIT"
    assert executed == ["read", "read"]
    assert len(model.calls) == 3


async def test_empty_structured_responses_stop_at_exactly_three_sdk_model_calls():
    model = ScriptedModel([[]])
    with pytest.raises(MaxTurnsExceeded):
        await SdkProvider(Settings()).run(
            bot_id="may",
            history=[],
            tools=[],
            context=None,
            on_progress=no_progress,
            model_override=model,
        )
    assert len(model.calls) == 3


async def test_live_policy_check_can_deny_before_model_receives_input():
    model = make_test_model("Never sent")

    async def deny():
        raise DomainError(403, "CONSENT_REQUIRED", "Quyền đã thay đổi.")

    with pytest.raises(DomainError) as error:
        await SdkProvider(Settings()).run(
            bot_id="may",
            history=[],
            tools=[],
            context=None,
            on_progress=deny,
            model_override=model,
        )
    assert error.value.code == "CONSENT_REQUIRED"
    assert model.calls == []


async def test_cancelling_caller_cancels_sdk_background_model():
    model = ScriptedModel([[message_output('{"text":"late","cards":[]}')]], hold=True)
    task = asyncio.create_task(
        SdkProvider(Settings()).run(
            bot_id="may",
            history=[],
            tools=[],
            context=None,
            on_progress=no_progress,
            model_override=model,
        )
    )
    await asyncio.wait_for(model.started.wait(), 2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert model.cancelled


async def test_whole_run_deadline_leaves_no_active_model(monkeypatch):
    monkeypatch.setattr("app.ai.provider.RUN_TIMEOUT_SECONDS", 0.02)
    model = ScriptedModel([[message_output('{"text":"late","cards":[]}')]], hold=True)
    task = asyncio.create_task(
        SdkProvider(Settings()).run(
            bot_id="may",
            history=[],
            tools=[],
            context=None,
            on_progress=no_progress,
            model_override=model,
        )
    )
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(task, 2)
    # The application's deadline must fire, rather than the outer test watchdog.
    assert not task.cancelled()
    # A deadline may expire during SDK setup, before a model was ever started.
    assert model.cancelled or not model.calls


async def test_unreceipted_durable_success_claim_is_rejected():
    with pytest.raises(OutputGuardrailTripwireTriggered):
        await SdkProvider(Settings()).run(
            bot_id="may",
            history=[],
            tools=[],
            context=None,
            on_progress=no_progress,
            model_override=make_test_model("Mình đã lưu hồ sơ của bạn."),
        )


async def test_real_responses_adapter_sends_store_false_and_never_retries_503(monkeypatch):
    requests = []

    async def handler(request):
        requests.append(request)
        if len(requests) == 1:
            response = completed_response([message_output('{"text":"From transport","cards":[]}')])
            event = {
                "type": "response.completed",
                "sequence_number": 1,
                "response": response.model_dump(mode="json"),
            }
            return httpx.Response(
                200,
                headers={"Content-Type": "text/event-stream"},
                content=("data: " + json.dumps(event) + "\n\n").encode(),
            )
        return httpx.Response(
            503, json={"error": {"message": "unavailable", "type": "server_error"}}
        )

    def client_factory(**kwargs):
        # Swap the production transport for the mock; retry policy stays the SDK's own.
        kwargs.pop("http_client", None)
        return AsyncOpenAI(
            **kwargs, http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
        )

    monkeypatch.setattr("app.ai.provider.AsyncOpenAI", client_factory)

    @function_tool
    async def read_only() -> str:
        """Read a synthetic value."""
        return "synthetic value"

    provider = SdkProvider(
        Settings(
            ai_enabled=True,
            openai_model="configured-test-model",
            openai_api_key=SecretStr("test-key"),
        )
    )
    result = await provider.run(
        bot_id="may",
        history=[{"role": "user", "content": "hello"}],
        tools=[read_only],
        context=None,
        on_progress=no_progress,
    )
    assert result.text == "From transport"
    payload = json.loads(requests[0].content)
    assert payload["store"] is False
    assert payload["parallel_tool_calls"] is False
    assert payload["max_output_tokens"] == 1200
    assert payload["model"] == "configured-test-model"
    assert payload["text"]["format"]["type"] == "json_schema"
    with pytest.raises(InternalServerError):
        await provider.run(
            bot_id="may", history=[], tools=[], context=None, on_progress=no_progress
        )
    assert len(requests) == 2


async def test_provider_reuses_one_client_and_retries_only_connection_setup():
    from app.ai.provider import SdkProvider
    from app.core.config import Settings
    from app.core.outbound import CONNECT_RETRIES, openai_http_client, provider_transport

    provider = SdkProvider(Settings(_env_file=None, provider_force_ipv4=True))
    first, second = provider._openai("sk-test"), provider._openai("sk-test")
    assert first is second
    await provider.aclose()
    assert provider._client is None and first.is_closed()
    # httpcore retries only ConnectError/ConnectTimeout, i.e. before a request is sent.
    pool = provider_transport(True)._pool
    assert pool._retries == CONNECT_RETRIES and pool._local_address == "0.0.0.0"
    assert provider_transport(False)._pool._local_address is None
    client = openai_http_client(False)
    assert client.timeout.connect == 5.0 and client.timeout.read == 30
    await client.aclose()
