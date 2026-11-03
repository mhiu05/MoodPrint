import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.ai.schemas import PromptOptions
from app.ai.search.turn import prepare_turn
from app.core.config import Settings


@pytest.mark.parametrize("area", ["Hồ Chí Minh", "Quận 3, Hồ Chí Minh", "TP.HCM", "Hà Nội"])
def test_exact_public_city_names_are_not_personal_pronouns(area):
    from app.ai.search.policy import clarification_area

    assert clarification_area(area) == area


async def test_expired_clarification_and_logout_cannot_dispatch(monkeypatch):
    from app.ai.runtime import AiRuntime
    from app.ai.search import maps_jobs

    async def maps(_runtime, _run, intent):
        return {"status": "needs_area"}

    monkeypatch.setattr(maps_jobs, "maps_for_turn", maps)
    runtime, run = context()
    await prepare_turn(
        runtime, run(PromptOptions(tools=["maps_search"])), "hoatdong", "Tìm quán cà phê"
    )
    identity = next(iter(runtime.maps_clarifications))
    runtime.maps_clarifications[identity] = ("quán cà phê", 0)
    assert await prepare_turn(runtime, run(), "hoatdong", "Hà Nội") == []
    assert not runtime.maps_clarifications
    await prepare_turn(
        runtime, run(PromptOptions(tools=["maps_search"])), "hoatdong", "Tìm quán cà phê"
    )
    runtime.runs, runtime.proposals = {}, {}
    runtime.store = SimpleNamespace(conversations={})
    AiRuntime.invalidate(runtime, str(identity[0]), str(identity[1]))
    assert not runtime.maps_clarifications


def context():
    settings = Settings(
        _env_file=None,
        ai_three_agent_experience_enabled=True,
        ai_multi_message_enabled=True,
        ai_maps_search_enabled=True,
        maps_search_worker_enabled=True,
        ai_accounting_enabled=True,
        ai_daily_budget_usd=20,
        openai_model="gpt-6-luna",
        apify_api_token="synthetic",
        apify_maps_actor_build="test",
        apify_maps_pricing_version="test",
        apify_maps_charge_bound_verified=True,
    )
    runtime = SimpleNamespace(settings=settings, maps_clarifications={})
    actor = SimpleNamespace(user_id=uuid4(), session_id=uuid4(), account_kind="registered")

    def run(options=None):
        return SimpleNamespace(
            response_protocol=3,
            kind="direct",
            actor=actor,
            mood_scope=None,
            conversation_id=conversation,
            data_version=1,
            prompt_options=options or PromptOptions(),
            public_search=False,
            skip_delegation=False,
            turn_instructions="",
        )

    conversation = uuid4()
    return runtime, run


async def test_maps_area_reply_completes_only_the_immediate_pending_search(monkeypatch):
    from app.ai.search import maps_jobs

    seen = []

    async def maps(_runtime, _run, intent):
        seen.append(intent)
        return {"status": "pending" if intent.area else "needs_area"}

    monkeypatch.setattr(maps_jobs, "maps_for_turn", maps)
    runtime, run = context()
    await prepare_turn(
        runtime, run(PromptOptions(tools=["maps_search"])), "hoatdong", "Tìm quán cà phê"
    )
    next_run = run()
    result = await prepare_turn(runtime, next_run, "hoatdong", "Quận 3, TP.HCM")
    assert len(seen) == 2
    assert seen[1].query == "quán cà phê" and seen[1].area == "Quận 3, TP.HCM"
    assert json.loads(result[0]["content"].split(": ", 1)[1])["maps"]["status"] == "pending"
    assert next_run.public_search
    assert await prepare_turn(runtime, run(), "hoatdong", "Hà Nội") == []


@pytest.mark.parametrize(
    "reply",
    [
        "Không tìm nữa",
        "Mình đang ở Hà Nội",
        "Hồ sơ của Lan ở Hà Nội",
        "Học Python",
        "Nhà số 12, Hà Nội",
    ],
)
async def test_unrelated_or_private_reply_does_not_reuse_maps_intent(monkeypatch, reply):
    from app.ai.search import maps_jobs

    seen = []

    async def maps(_runtime, _run, intent):
        seen.append(intent)
        return {"status": "needs_area"}

    monkeypatch.setattr(maps_jobs, "maps_for_turn", maps)
    runtime, run = context()
    await prepare_turn(
        runtime, run(PromptOptions(tools=["maps_search"])), "hoatdong", "Tìm quán cà phê"
    )
    await prepare_turn(runtime, run(), "hoatdong", reply)
    assert len(seen) == 1
    assert not runtime.maps_clarifications


async def test_area_clarification_never_crosses_session_or_data_version(monkeypatch):
    from app.ai.search import maps_jobs

    seen = []

    async def maps(_runtime, _run, intent):
        seen.append(intent)
        return {"status": "needs_area"}

    monkeypatch.setattr(maps_jobs, "maps_for_turn", maps)
    runtime, run = context()
    await prepare_turn(
        runtime, run(PromptOptions(tools=["maps_search"])), "hoatdong", "Tìm quán cà phê"
    )
    next_run = run()
    next_run.data_version = 2
    assert await prepare_turn(runtime, next_run, "hoatdong", "Hà Nội") == []
    next_run = run()
    next_run.actor.session_id = uuid4()
    assert await prepare_turn(runtime, next_run, "hoatdong", "Hà Nội") == []
    assert len(seen) == 1


@pytest.mark.postgres
@pytest.mark.parametrize("persistent", [False, True])
@pytest.mark.parametrize("question_succeeds", [False, True])
async def test_area_followup_dispatches_once_through_real_chat_and_reserves_full_cap(
    clients, persistent, question_succeeds
):
    from sqlalchemy import select

    from app.ai.search.apify import ProviderRunRef
    from app.ai.search.models import AiSearchUsage
    from tests.fakes import ScriptedModel, message_output
    from tests.test_chat_persistence import enable, key
    from tests.test_context_privacy import turn

    app, actors = clients
    client, _ = actors[0]
    await enable(client)
    settings = context()[0].settings
    for name in (
        "ai_three_agent_experience_enabled",
        "ai_multi_message_enabled",
        "ai_maps_search_enabled",
        "maps_search_worker_enabled",
        "ai_accounting_enabled",
        "ai_daily_budget_usd",
        "openai_model",
        "apify_api_token",
        "apify_maps_actor_build",
        "apify_maps_pricing_version",
        "apify_maps_charge_bound_verified",
    ):
        setattr(app.state.settings, name, getattr(settings, name))

    class Maps:
        calls = []

        async def start(self, **kwargs):
            self.calls.append(kwargs)
            return ProviderRunRef("run123", "data123")

    provider = Maps()
    app.state.ai.maps_provider = provider

    def reply(text):
        return ScriptedModel(
            [
                [
                    message_output(
                        json.dumps(
                            {
                                "messages": [
                                    {"segments": [{"text": text, "sourceIds": []}], "cards": []}
                                ]
                            }
                        )
                    )
                ]
            ]
        )

    app.state.ai.model_override = reply("Bạn muốn tìm ở khu vực nào?")
    response = await client.post(
        "/api/v1/ai/conversations",
        json={"botId": "hoatdong", "persistent": persistent},
        headers=key(),
    )
    assert response.status_code == 201
    url = "/api/v1/ai/conversations/" + response.json()["conversationId"]
    await turn(
        app,
        client,
        url,
        "Tìm quán cà phê",
        reply("Bạn muốn tìm ở khu vực nào?")
        if question_succeeds
        else ScriptedModel([[message_output("invalid JSON")]]),
        responseProtocol=3,
        promptOptions={"tools": ["maps_search"]},
        expected_status="completed" if question_succeeds else "failed",
    )
    assert provider.calls == []
    if not question_succeeds:
        assert not app.state.ai.maps_clarifications
        return
    second = await turn(
        app, client, url, "Quận 3, TP.HCM", reply("Đang tìm địa điểm."), responseProtocol=3
    )
    assert provider.calls == [{"category": "cafe", "area": "Quận 3, TP.HCM"}]
    assert second.public_search and second.public_cards[0].kind == "maps_search"
    async with app.state.database.sessions() as db:
        fee = await db.scalar(select(AiSearchUsage).where(AiSearchUsage.parent_run_id == second.id))
        assert fee.reservation_nano_usd == 500_000_000
