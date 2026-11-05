import asyncio
import json
from datetime import datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select

from app.ai.search.schemas import WebSearchResult
from tests.fakes import ScriptedModel, message_output
from tests.test_context_privacy import turn


async def skill_conversation(clients, bot="nhatky"):
    from tests.fakes import make_test_model
    from tests.test_chat_persistence import enable, key

    app, actors = clients
    client, uid = actors[0]
    settings = app.state.settings
    settings.ai_three_agent_experience_enabled = True
    settings.ai_agent_skills_enabled = settings.ai_multi_message_enabled = True
    app.state.ai.model_override = make_test_model("ready")
    await enable(client)
    response = await client.post("/api/v1/ai/conversations", json={"botId": bot}, headers=key())
    assert response.status_code == 201, response.text
    return app, client, uid, f"/api/v1/ai/conversations/{response.json()['conversationId']}"


@pytest.mark.postgres
async def test_manual_skill_for_the_wrong_agent_is_rejected(clients):
    from sqlalchemy import func

    from app.infrastructure.database.models import AiRun
    from tests.test_chat_persistence import key

    app, client, uid, url = await skill_conversation(clients, "hoatdong")
    result = await client.post(url + "/messages", headers=key(), json={
        "text": "Nhìn lại tuần", "clientMessageId": str(uuid4()),
        "expectedConversationVersion": 1, "responseProtocol": 3,
        "promptOptions": {"skillId": "weekly-review"},
    })
    assert result.status_code == 422
    assert result.json()["error"]["code"] == "SKILL_NOT_FOR_AGENT"
    async with app.state.database.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(AiRun).where(AiRun.user_id == uid)) == 0


@pytest.mark.postgres
async def test_capabilities_are_per_agent(clients):
    app, client, _uid, _url = await skill_conversation(clients, "hoatdong")
    result = await client.get("/api/v1/ai/prompt-capabilities?botId=hoatdong")
    assert result.status_code == 200
    skills = {skill["id"]: skill for skill in result.json()["skills"]}
    assert not skills["weekly-review"]["available"]
    assert skills["weekly-review"]["reason"] == "Kỹ năng này dành cho trợ lý Nhật ký."
    assert skills["guided-journal"]["reason"] == "Kỹ năng này dành cho trợ lý Nhật ký và Điều phối."
    result = await client.get("/api/v1/ai/prompt-capabilities?botId=nhatky")
    assert next(skill for skill in result.json()["skills"] if skill["id"] == "weekly-review")["available"]


@pytest.mark.postgres
async def test_skill_with_mood_scope_is_still_rejected(clients):
    from tests.test_chat_persistence import key
    app, client, _uid, url = await skill_conversation(clients)
    today = datetime.now(ZoneInfo("Asia/Bangkok")).date().isoformat()
    result = await client.post(url + "/messages", headers=key(), json={
        "text": "Nhìn lại tuần", "clientMessageId": str(uuid4()),
        "expectedConversationVersion": 1, "responseProtocol": 3,
        "promptOptions": {"skillId": "weekly-review"},
        "moodScope": {"fromDate": today, "toDate": today},
    })
    assert result.status_code == 422
    assert result.json()["error"]["code"] == "PROMPT_OPTIONS_MOOD_SCOPE"


@pytest.mark.postgres
async def test_weekly_review_reads_the_last_seven_days_and_cites(clients):
    from app.modules.journal.models import JournalEntry
    from tests.fakes import tool_output
    from tests.test_journal import create

    app, client, uid, url = await skill_conversation(clients)
    row = await create(client, text="SYNTHETIC_WEEKLY_ENTRY: Mình nghỉ ngơi trong vườn.")
    today = datetime.now(ZoneInfo("Asia/Bangkok")).date()
    async with app.state.database.sessions.begin() as db:
        db.add(JournalEntry(user_id=uid, local_date=today-timedelta(days=7), timezone="Asia/Bangkok",
                            mood=2, text="SYNTHETIC_OUTSIDE_WEEK", status="saved"))
    call = tool_output("search_journal_entries", "weekly")
    call.arguments = json.dumps({"from_date": str(today-timedelta(days=6)), "to_date": str(today), "query": "", "limit": 8})
    model = ScriptedModel([[call], [message_output(json.dumps({
        "messages": [{"text": "Bạn đã ghi một khoảng nghỉ trong vườn.", "cards": []}],
        "source_entry_ids": [row["id"]],
    }))]])
    run = await turn(app, client, url, "Nhìn lại tuần này giúp mình", model,
                     responseProtocol=3, promptOptions={"skillId": "weekly-review"})
    assert run.skill_id == "weekly-review" and run.workflow is None
    returned = next(item for item in model.calls[1]["input"] if isinstance(item, dict) and item.get("type") == "function_call_output")
    entries = json.loads(returned["output"])["entries"]
    assert {entry["id"] for entry in entries} == {row["id"]}
    assert all(str(today-timedelta(days=6)) <= entry["localDate"] <= str(today) for entry in entries)
    assert run.journal_evidence is None  # Private evidence is scrubbed after terminal publication.
    assert "SYNTHETIC_OUTSIDE_WEEK" not in str(model.calls[1]["input"])
    messages = (await client.get(url + "?responseProtocol=3")).json()["messages"]
    assert "Bài viết đã tham khảo:" in messages[-1]["text"]
    assert row["id"] in messages[-1]["text"]


@pytest.mark.postgres
async def test_skill_turn_respects_journal_refusal(clients):
    from agents import RunContextWrapper

    from app.core.errors import DomainError

    app, client, _uid, url = await skill_conversation(clients)
    model = ScriptedModel([[message_output(json.dumps({
        "messages": [{"text": "Bạn có thể kể vài dòng về tuần này nếu muốn.", "cards": []}],
        "source_entry_ids": [],
    }))]], hold=True)
    pending = asyncio.create_task(turn(app, client, url, "Đừng đọc nhật ký của mình; chỉ trò chuyện thôi", model,
                    responseProtocol=3, promptOptions={"skillId": "weekly-review"}))
    await asyncio.wait_for(model.started.wait(), 5)
    run = next(run for run in app.state.ai.runs.values() if not run.terminal)
    try:
        assert all(tool.name != "search_journal_entries" for tool in model.calls[0]["tools"])
        tool = next(tool for tool in app.state.ai.tools(run, "nhatky") if tool.name == "search_journal_entries")
        with pytest.raises(DomainError) as denied:
            await tool.on_invoke_tool(RunContextWrapper(context=run), "{}")
        assert denied.value.status == 403 and denied.value.code == "JOURNAL_READ_DENIED"
    finally:
        model.release.set()
        await pending
    assert run.skill_id == "weekly-review" and run.journal_evidence is None
    assert "Bài viết đã tham khảo:" not in (await client.get(url)).text


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
