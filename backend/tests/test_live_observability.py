import asyncio
from uuid import uuid4

import pytest
from agents import OutputGuardrailTripwireTriggered

from app.ai.provider import SdkProvider
from app.core.config import Settings
from tests.fakes import ScriptedModel, make_test_model, message_output


async def noop():
    pass


async def test_usage_survives_guardrail_rejection_without_exposing_content():
    samples = []

    async def observe(sample):
        samples.append(sample)

    provider = SdkProvider(Settings(), usage_observer=observe)
    with pytest.raises(OutputGuardrailTripwireTriggered):
        await provider.run(
            bot_id="may", history=[{"role": "user", "content": "PRIVATE-CANARY"}],
            tools=[], context=None, on_progress=noop,
            model_override=make_test_model("Mình đã lưu hồ sơ của bạn."),
        )
    assert [s.kind for s in samples] == ["request_started", "response_received"]
    # Scripted SDK responses have no provider usage; do not invent token counts.
    assert samples[-1].input_tokens == 0
    assert "CANARY" not in repr(samples)
    assert "lưu" not in repr(samples)


async def test_cancelled_model_has_a_start_but_no_fabricated_usage_receipt():
    samples = []

    async def observe(sample):
        samples.append(sample)

    model = ScriptedModel([[message_output('{"text":"late","cards":[]}')]], hold=True)
    task = asyncio.create_task(SdkProvider(Settings(), usage_observer=observe).run(
        bot_id="may", history=[], tools=[], context=None, on_progress=noop,
        model_override=model,
    ))
    await asyncio.wait_for(model.started.wait(), 2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert [s.kind for s in samples] == ["request_started"]


def test_local_live_actor_allowlist_is_closed_by_default_and_rejected_in_production():
    from pydantic import ValidationError

    actor, outsider = uuid4(), uuid4()
    assert not Settings().ai_available_for(actor)
    settings = Settings(app_env="development", ai_local_test_user_ids=[actor])
    assert settings.ai_available_for(actor)
    assert not settings.ai_available_for(outsider)
    with pytest.raises(ValidationError):
        Settings(app_env="production", ai_local_test_user_ids=[actor])


@pytest.mark.postgres
async def test_local_live_access_and_feature_flag_are_scoped_to_the_actor(clients):
    from pydantic import SecretStr

    app, actors = clients
    settings = app.state.settings
    settings.app_env = "development"
    settings.ai_local_test_user_ids = [actors[0][1]]
    settings.openai_model = "configured-model"
    settings.openai_api_key = SecretStr("test-only-key")
    for index, (client, _) in enumerate(actors):
        await client.put("/api/v1/consents/AI", json={"enabled": True, "expectedVersion": 1, "policyVersion": "v1"}, headers={"Idempotency-Key": str(uuid4())})
        session = (await client.get("/api/v1/session")).json()
        assert session["features"]["ai"] is (index == 0)
        response = await client.post("/api/v1/ai/conversations", json={"botId": "may"}, headers={"Idempotency-Key": str(uuid4())})
        assert response.status_code == (201 if index == 0 else 503)
