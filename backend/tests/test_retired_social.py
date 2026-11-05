"""Retire social output at publication while keeping frozen persona bytes intact."""

import hashlib

import pytest

LEGACY_HASHES = {
    "may": "697a0b191c2ad83f09a2dff9d2a4a7b695dfff386c0fb5a7a6d63d169cbbf9b4",
    "guong": "987052705570a3c982021dc8842c1465ff0aa46b937e952e8e4c0e3e50e3ab53",
    "nhip": "2c102b424cba0ef812cb205499edc1c565ae750ce2822faab974b693eb97281a",
    "rure": "01b101196a0eda623a3579dc318f7aa28b6a70450ea9dfa51c5fd768fb97c31a",
    "caunoi": "71f24c8ceaa65c3470737ecf132603aba1ce4c52be8fdf85936f44b1680072b2",
}
V3_HASHES = {
    "dieuphoi": "4f9a81052e1e96674caea4ee32dbb099cfbd689af47b9857ca411a58a591ece4",
    "nhatky": "00752c2ba31b6e57c67e63570bf15e631b33a85a257dd4f542dfe46869087898",
    "hoatdong": "acc7a9b28f50e136825be250a54dcad5d68ac45fd8f4bfdb4632545e469c16c4",
}


def test_legacy_prompt_bytes_unchanged():
    from app.ai.prompts import V3_PERSONAS, instructions

    assert {bot: hashlib.sha256(instructions(bot).encode()).hexdigest() for bot in LEGACY_HASHES} == LEGACY_HASHES
    assert {bot: hashlib.sha256(value.encode()).hexdigest() for bot, value in V3_PERSONAS.items()} == V3_HASHES


def test_v3_conversation_instructions_retire_social():
    from app.ai.prompts import conversation_instructions

    assert "Không dùng card discovery" in conversation_instructions("hoatdong", "activity")
    assert "Không dùng card discovery" not in conversation_instructions("may", "conversation")


@pytest.mark.parametrize("bot", ["dieuphoi", "nhatky", "hoatdong", "may", "caunoi"])
def test_only_v3_cards_are_filtered(bot):
    from app.ai.schemas import AiOutput, drop_retired_cards

    result = drop_retired_cards([AiOutput(text="Một gợi ý nhỏ.", cards=[{"kind": "discovery"}, {"kind": "mood_form"}])], bot)
    assert [card.kind for card in result[0].cards] == (
        ["mood_form"] if bot in ("dieuphoi", "nhatky", "hoatdong") else ["discovery", "mood_form"]
    )


@pytest.mark.postgres
async def test_v3_reply_never_persists_a_discovery_card(clients):
    from tests.collaboration_helpers import finish, start
    from tests.orchestration_helpers import scripted
    from tests.test_chat_persistence import enable
    from tests.test_multi_message_persistence import conversation

    app, actors = clients
    client = actors[0][0]
    await enable(client)
    app.state.settings.ai_multi_message_enabled = True
    app.state.settings.ai_three_agent_experience_enabled = True
    model = scripted({"messages": [{"text": "Mình cùng chọn một việc nhỏ nhé.", "cards": [{"kind": "discovery"}]}]})
    app.state.ai.model_override = model
    url = await conversation(client, "dieuphoi")
    run = await finish(await start(app, client, url, "Một gợi ý nhỏ", model=model))
    assert run.terminal_status == "completed", run.failure
    view = (await client.get(url)).json()
    assert [message["cards"] for message in view["messages"] if message["actor"] == "bot"] == [[]]


@pytest.mark.postgres
async def test_group_reply_never_persists_a_discovery_card(clients):
    from tests.group_helpers import create_group, groups_setup, say
    from tests.orchestration_helpers import roles, scripted

    app, actors = clients
    client = actors[0][0]
    await groups_setup(app, client)
    group = await create_group(client)
    model = scripted({"messages": [{"text": "Thử vẽ một đường thẳng.", "cards": [{"kind": "discovery"}]}]})
    roles(app, hoatdong=model)
    run, _ = await say(app, client, group["groupId"], "@Hoạt động gợi ý một việc")
    assert run.terminal_status == "completed", run.failure
    view = (await client.get(f"/api/v1/ai/groups/{group['groupId']}")).json()
    assert [message["cards"] for message in view["messages"] if message["actor"] == "bot"] == [[]]
    assert "Không dùng card discovery" in model.calls[0]["instructions"]
