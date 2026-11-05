import json
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.ai.search.schemas import WebSearchResult
from tests.fakes import ScriptedModel, message_output
from tests.test_context_privacy import turn


@pytest.mark.postgres
async def test_skill_direct_current_agent_and_options_idempotency(clients):
    from tests.test_chat_persistence import enable, key
    app, actors = clients
    client, _ = actors[0]
    settings = app.state.settings
    settings.ai_three_agent_experience_enabled = settings.ai_agent_skills_enabled = settings.ai_multi_message_enabled = True
    await enable(client)
    model = ScriptedModel([[message_output(json.dumps({"messages": [{"text": "Thử học vẽ trong 10 phút.", "cards": []}]}))]])
    app.state.ai.model_override = model
    response = await client.post("/api/v1/ai/conversations", json={"botId": "hoatdong"}, headers=key())
    url = f"/api/v1/ai/conversations/{response.json()['conversationId']}"
    client_id = str(uuid4())
    run = await turn(app, client, url, "Có 10 phút muốn học điều mới", model,
        clientMessageId=client_id, responseProtocol=3, promptOptions={"skillId": "learn-new-thing"})
    assert run.skill_id == "learn-new-thing" and run.workflow is None
    assert "5–15" in model.calls[0]["instructions"]
    body = {"text": "Có 10 phút muốn học điều mới", "clientMessageId": client_id,
            "expectedConversationVersion": 1, "responseProtocol": 3, "promptOptions": {"skillId": "hangout"}}
    conflict = await client.post(url+"/messages", json=body, headers=key())
    assert conflict.status_code == 409 and conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"


@pytest.mark.postgres
async def test_manual_web_isolated_before_private_context_and_accounted(clients):
    from app.ai.search.models import AiSearchUsage
    from app.infrastructure.database.models import AiUsage
    from tests.test_chat_persistence import enable, key

    app, actors = clients
    client, _ = actors[0]
    s = app.state.settings
    s.ai_three_agent_experience_enabled = s.ai_multi_message_enabled = s.ai_web_search_enabled = s.ai_accounting_enabled = True
    s.ai_daily_budget_usd = 20
    s.ai_search_daily_budget_usd = 5
    s.openai_model = "gpt-6-luna"
    s.ai_web_search_pricing_version = "test-bound-v1"
    s.ai_web_search_token_bound_verified = True
    await enable(client)
    queries = []
    class FakeWeb:
        async def search(self, query, *, timeout_seconds):
            assert timeout_seconds <= 12
            queries.append(query)
            return WebSearchResult(status="completed", text="Thông tin công khai.", calls=1,
                input_tokens=100, output_tokens=20,
                sources=[{"sourceId": "s1", "title": "Nguồn", "url": "https://example.org/article"}])
    app.state.ai.web_search_adapter = FakeWeb()
    payload = {"messages": [{"segments": [{"text": "Thông tin đã tra.", "sourceIds": ["s1"]}], "cards": []}]}
    model = ScriptedModel([[message_output(json.dumps(payload))]])
    app.state.ai.model_override = model
    created = await client.post("/api/v1/ai/conversations", json={"botId": "nhatky"}, headers=key())
    url = f"/api/v1/ai/conversations/{created.json()['conversationId']}"
    run = await turn(app, client, url, "Tin mới nhất về Python", model, responseProtocol=3,
        promptOptions={"tools": ["web_search"]})
    assert run.public_search and run.workflow is None and run.journal_evidence is None
    assert queries == ["Thông tin mới nhất về Python"]
    call = model.calls[0]
    assert not call["tools"]
    view = (await client.get(url+"?responseProtocol=3")).json()
    assert view["messages"][-1]["citations"][0]["url"] == "https://example.org/article"
    async with app.state.database.sessions() as db:
        fee = await db.scalar(select(AiSearchUsage).where(AiSearchUsage.parent_run_id == run.id))
        assert fee.actual_nano_usd == 10_000_000 and fee.state == "settled"
        usage = await db.get(AiUsage, fee.child_run_id)
        assert usage.requests_started == usage.responses_received == 1
        assert usage.input_tokens == 100 and usage.output_tokens == 20
