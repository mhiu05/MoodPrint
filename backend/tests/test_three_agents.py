"""V3-02/03: exactly three default agents, distinct capabilities, legacy history read-only."""

import json
from uuid import uuid4

import pytest

from tests.collaboration_helpers import finish, start
from tests.fakes import make_test_model
from tests.test_chat_persistence import enable, key
from tests.test_multi_message_persistence import conversation

pytestmark = pytest.mark.postgres


def three_agents(app, on=True):
    app.state.settings.ai_three_agent_experience_enabled = on


async def test_bots_are_the_five_companions_by_default_and_exactly_three_with_the_flag(clients):
    app, [(client, _uid), _] = clients
    off = (await client.get("/api/v1/bots")).json()
    assert [bot["botId"] for bot in off] == ["may", "guong", "nhip", "rure", "caunoi"]
    assert (await client.get("/api/v1/bots/legacy")).json() == []
    # Byte-compatible Phase 2 shape plus two defaulted fields only.
    assert all(bot["legacy"] is False and bot["replacedBy"] is None for bot in off)
    session = (await client.get("/api/v1/session")).json()
    assert session["features"]["threeAgents"] is False
    assert session["features"]["smartOrchestration"] is False and session["features"]["groupChat"] is False

    three_agents(app)
    on = (await client.get("/api/v1/bots")).json()
    assert [(bot["botId"], bot["name"]) for bot in on] == [
        ("dieuphoi", "Điều phối"), ("nhatky", "Nhật ký"), ("hoatdong", "Hoạt động")]
    assert len({bot["role"] for bot in on}) == 3 and len({bot["description"] for bot in on}) == 3
    legacy = (await client.get("/api/v1/bots/legacy")).json()
    assert {bot["botId"]: bot["replacedBy"] for bot in legacy} == {
        "may": "dieuphoi", "guong": "dieuphoi", "nhip": "nhatky", "rure": "hoatdong", "caunoi": None}
    assert all(bot["legacy"] for bot in legacy)
    assert (await client.get("/api/v1/session")).json()["features"]["threeAgents"] is True


async def test_rollout_cohort_limits_the_three_agents_to_listed_accounts(clients):
    app, [(client, uid), (other, _other_uid)] = clients
    three_agents(app)
    app.state.settings.ai_v3_rollout_user_ids = [uid]
    assert (await client.get("/api/v1/bots")).json()[0]["botId"] == "dieuphoi"
    assert (await other.get("/api/v1/bots")).json()[0]["botId"] == "may"


async def test_legacy_conversations_stay_readable_but_read_only_and_nothing_merges(clients):
    app, [(client, _uid), _] = clients
    await enable(client)
    app.state.ai.model_override = make_test_model("Lời đáp cũ của Mây")
    old_url = await conversation(client, "may")
    run = await finish(await start(app, client, old_url, "Kể Mây nghe chuyện hôm nay"))
    assert run.terminal_status == "completed"

    three_agents(app)
    view = (await client.get(old_url)).json()
    assert view["legacy"] is True and view["botId"] == "may"
    assert [m["text"] for m in view["messages"]] == ["Kể Mây nghe chuyện hôm nay", "Lời đáp cũ của Mây"]
    assert view["messages"][1]["speaker"] == "may"
    listed = (await client.get("/api/v1/ai/conversations")).json()
    assert [(c["botId"], c["legacy"]) for c in listed] == [("may", True)]
    # Read-only: a new message is refused with a clear code; reading, renaming and export still work.
    refused = await client.post(old_url + "/messages", headers=key(), json={
        "text": "Còn ở đó không?", "clientMessageId": str(uuid4()), "expectedConversationVersion": view["version"]})
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "LEGACY_CONVERSATION"
    created = await client.post("/api/v1/ai/conversations", json={"botId": "may"}, headers=key())
    assert created.status_code == 409 and created.json()["error"]["code"] == "LEGACY_COMPANION"
    assert (await client.patch(old_url, json={"title": "Chuyện cũ"}, headers=key())).status_code == 200
    assert (await client.get(old_url + "/export")).status_code == 200

    # A new Điều phối conversation starts empty: no legacy transcript is carried over.
    model = make_test_model("Chào bạn, mình là Điều phối.")
    new_url = await conversation(client, "dieuphoi")
    run = await finish(await start(app, client, new_url, "Chào Điều phối", model=model))
    assert run.terminal_status == "completed", run.failure
    sent = json.dumps(model.calls[0]["input"], ensure_ascii=False)
    assert "Lời đáp cũ của Mây" not in sent and "Kể Mây nghe" not in sent
    new_view = (await client.get(new_url)).json()
    assert new_view["legacy"] is False and new_view["messages"][-1]["speaker"] == "dieuphoi"

    # Turning the experience off again: legacy chats answer as in Phase 2, V3 chats are kept but paused.
    three_agents(app, False)
    paused = await client.post(new_url + "/messages", headers=key(), json={
        "text": "Còn đó không?", "clientMessageId": str(uuid4()), "expectedConversationVersion": new_view["version"]})
    assert paused.status_code == 409 and paused.json()["error"]["code"] == "AGENT_UNAVAILABLE"
    assert (await client.get(new_url)).status_code == 200
    run = await finish(await start(app, client, old_url, "Lại là mình đây", model=make_test_model("Mây đây")))
    assert run.terminal_status == "completed"


@pytest.mark.parametrize(
    ("bot_id", "tools", "intent"),
    [
        ("dieuphoi", {"propose_memory"}, "conversation"),
        ("nhatky", {"propose_memory", "search_journal_entries"}, "conversation"),
        ("hoatdong", set(), "activity"),
    ],
)
async def test_each_agent_has_its_own_persona_tools_and_no_borrowed_prompt(clients, bot_id, tools, intent):
    from app.ai.evidence import source_instructions
    from app.ai.journal import journal_instructions
    from app.ai.prompts import V3_PERSONAS, conversation_instructions, instructions

    app, [(client, _uid), _] = clients
    await enable(client)
    three_agents(app)
    model = make_test_model("Ổn rồi.")
    app.state.ai.model_override = model
    url = await conversation(client, bot_id)
    run = await finish(await start(app, client, url, "Mình đang nghĩ nên làm gì tối nay", model=model))
    assert run.terminal_status == "completed", run.failure
    call = model.calls[0]
    assert {tool.name for tool in call["tools"]} == tools
    assert call["instructions"] == (
        instructions(bot_id) + source_instructions(run, bot_id, mood_analysis=False)
        + (journal_instructions(run) if bot_id == "nhatky" else "")
        + conversation_instructions(bot_id, intent)
    )
    assert V3_PERSONAS[bot_id].split("\n")[0] in call["instructions"]
    for legacy_name in ("Bạn là Mây", "Bạn là Gương", "Bạn là Nhịp", "Bạn là Rủ Rê", "Bạn là Cầu Nối"):
        assert legacy_name not in call["instructions"]


async def test_mood_scope_is_only_for_the_journal_agent(clients):
    app, [(client, _uid), _] = clients
    await enable(client)
    three_agents(app)
    app.state.ai.model_override = make_test_model("ok")
    for bot_id, status in (("dieuphoi", 422), ("hoatdong", 422)):
        url = await conversation(client, bot_id)
        response = await client.post(url + "/messages", headers=key(), json={
            "text": "Xem tâm trạng", "clientMessageId": str(uuid4()), "expectedConversationVersion": 1,
            "moodScope": {"fromDate": "2026-10-20", "toDate": "2026-10-26"}})
        assert response.status_code == status
        assert response.json()["error"]["code"] == "MOOD_SCOPE_BOT"


async def test_v3_agent_conversations_need_the_flag_and_groups_never_leak_into_direct_endpoints(clients):
    from app.ai.models import AiConversation
    from app.infrastructure.database.models import now

    app, [(client, uid), _] = clients
    await enable(client)
    app.state.ai.model_override = make_test_model("ok")
    refused = await client.post("/api/v1/ai/conversations", json={"botId": "nhatky"}, headers=key())
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "AGENT_UNAVAILABLE"
    async with app.state.database.sessions.begin() as db:
        group = AiConversation(user_id=uid, bot_id="group", kind="group", expires_at=now().replace(year=2099))
        db.add(group)
    assert (await client.get(f"/api/v1/ai/conversations/{group.id}")).status_code == 404
    assert all(c["conversationId"] != str(group.id) for c in (await client.get("/api/v1/ai/conversations")).json())
