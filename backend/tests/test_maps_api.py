import json
from uuid import UUID

import pytest
from pydantic import SecretStr
from sqlalchemy import select

from app.infrastructure.database.models import now
from tests.fakes import ScriptedModel, message_output
from tests.test_chat_persistence import enable, key
from tests.test_context_privacy import turn


@pytest.mark.postgres
async def test_maps_pending_ready_reuse_scope_authorization_and_saved_places(clients):
    from decimal import Decimal

    from app.ai.search.apify import ProviderRunRef, ProviderRunStatus
    from app.ai.search.maps import PlaceResult
    from app.ai.search.maps_jobs import advance_one
    from app.ai.search.models import AiMapsSearch, AiSearchUsage
    app, actors = clients
    client, _ = actors[0]
    stranger, _ = actors[1]
    await enable(client)
    s = app.state.settings
    s.ai_three_agent_experience_enabled = s.ai_multi_message_enabled = s.ai_accounting_enabled = True
    s.ai_maps_search_enabled = s.maps_search_worker_enabled = s.apify_maps_charge_bound_verified = True
    s.apify_maps_actor_build, s.apify_maps_pricing_version = "pinned-test", "fake-bound-v1"
    s.apify_api_token = SecretStr("synthetic-test-token")
    s.openai_model, s.ai_daily_budget_usd = "gpt-6-luna", 20
    class Maps:
        starts = 0
        async def start(self, **kwargs):
            assert kwargs == {"category": "cafe", "area": "Quận 3"}
            self.starts += 1
            return ProviderRunRef("run123", "data123")
        async def status(self, ref):
            return ProviderRunStatus("succeeded", Decimal("0.015"))
        async def results(self, ref):
            return [PlaceResult(name="Cà phê", address="Quận 3", fetched_at=now(), maps_url="https://www.google.com/maps/search/?api=1&query=cafe")]
        async def cleanup(self, ref):
            pass
        async def abort(self, ref):
            pass
    maps = Maps()
    app.state.ai.maps_provider = maps
    def reply(text):
        return ScriptedModel([[message_output(json.dumps({"messages": [{"segments": [{"text": text, "sourceIds": []}], "cards": []}]}))]])
    model = reply("Mình đang tìm địa điểm.")
    app.state.ai.model_override = model
    created = await client.post("/api/v1/ai/conversations", json={"botId": "hoatdong"}, headers=key())
    url = "/api/v1/ai/conversations/" + created.json()["conversationId"]
    run = await turn(app, client, url, "Tìm quán cà phê", model, responseProtocol=3,
                     promptOptions={"tools": ["maps_search"], "area": "Quận 3"})
    view = (await client.get(url+"?responseProtocol=3")).json()
    identity = view["messages"][-1]["cards"][0]["searchId"]
    endpoint = "/api/v1/ai/maps-searches/"+identity
    assert (await client.get(endpoint)).json()["status"] == "pending"
    assert (await stranger.get(endpoint)).status_code == 404
    assert await advance_one(app.state.database, maps)
    ready = await client.get(endpoint)
    assert ready.headers["cache-control"] == "no-store" and ready.json()["places"][0]["name"] == "Cà phê"
    assert "run123" not in ready.text and "synthetic" not in ready.text
    await turn(app, client, url, "Gợi ý từ kết quả", reply("Thử ghé quán để đọc sách."), responseProtocol=3,
               promptOptions={"mapsSearchId": identity})
    saved = (await client.get(url+"/export")).json()["messages"][-1]
    assert saved["cards"][0]["kind"] == "places" and saved["cards"][0]["places"][0]["name"] == "Cà phê"
    other = await client.post("/api/v1/ai/conversations", json={"botId": "dieuphoi"}, headers=key())
    other_url = "/api/v1/ai/conversations/"+other.json()["conversationId"]
    await turn(app, client, other_url, "Gợi ý", reply("not published"), responseProtocol=3,
               promptOptions={"mapsSearchId": identity}, expected_status="failed")
    assert maps.starts == 1
    async with app.state.database.sessions() as db:
        fee = await db.scalar(select(AiSearchUsage).where(AiSearchUsage.parent_run_id == run.id))
        assert fee.state == "settled" and fee.actual_nano_usd == 15_000_000
        job = await db.get(AiMapsSearch, UUID(identity))
        assert job.provider_ref and job.conversation_id == UUID(created.json()["conversationId"])
