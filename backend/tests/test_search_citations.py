from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.ai.schemas import AIEvent, AiOutput, StartRunInput, as_protocol


def citation(url="https://example.org/info"):
    return dict(sourceId="s1", title="Nguồn", url=url, start=0, end=3)


def test_options_are_normalized_for_idempotency():
    base = dict(text="Tra cứu", clientMessageId=uuid4(), expectedConversationVersion=1,
                responseProtocol=3)
    a = StartRunInput(**base, promptOptions={"tools": ["web_search", "maps_search"], "area": "  Quận 3  "})
    b = StartRunInput(**base, promptOptions={"tools": ["maps_search", "web_search", "web_search"], "area": "Quận 3"})
    assert a.model_dump_json() == b.model_dump_json()
    assert a.response_protocol == 3
    with pytest.raises(ValidationError):
        StartRunInput(**base, promptOptions={"skillId": "../../secret"})


@pytest.mark.parametrize("url", ["http://example.org", "https://localhost/a", "https://127.0.0.1/", "https://10.0.0.1/", "https://u:p@example.org", "javascript:alert(1)", "https://[::1]/",
    "https://0x7f.1/", "https://0x7f.0.0.1/", "https://0177.0.0.1/", "https://2130706433/", "https://127.1/",
    "https://[::ffff:127.0.0.1]/", "https://localhost./", "https://foo.localhost/", "https://169.254.169.254/"])
def test_untrusted_citation_url_rejected(url):
    with pytest.raises(ValidationError):
        AiOutput(text="😀ơi", citations=[citation(url)])


def test_citation_codepoints_and_old_protocol_placeholder():
    part = AiOutput(text="😀ơi", citations=[citation()])
    assert part.citations[0].end == len(part.text) == 3
    final = {"partCount": 1, "messages": [{"messageId": str(uuid4()), "partIndex": 0,
              "text": part.text, "cards": [], "citations": [citation()]}],
             "speaker": "hoatdong", "steps": []}
    event = AIEvent(seq="1", type="final", data=final)
    assert as_protocol(event, 3).version == "ai-events-v3"
    assert as_protocol(event, 3).data == final
    for protocol in (1, 2):
        rendered = as_protocol(event, protocol)
        assert "example.org" not in rendered.model_dump_json()
        assert "😀ơi" not in rendered.model_dump_json()
        assert "tải lại" in str(rendered.data).lower()


def test_citation_range_must_fit_visible_text():
    with pytest.raises(ValidationError):
        AiOutput(text="x", citations=[citation()])


def test_search_turn_boundary_cannot_launder_sources_into_ordinary_history():
    from app.ai.context import TEXT_POLICY, ContextStamp, model_messages
    from app.ai.schemas import AIMessage, history_protocol
    first, second = uuid4(), uuid4()
    messages = [AIMessage(id=uuid4(), actor="bot", text="Dữ kiện từ web ở phần đầu.", run_id=first, source_backed=True),
                AIMessage(id=uuid4(), actor="self", text="Nhắc lại giúp mình", run_id=second)]
    result = model_messages(messages, {first: ContextStamp(1, TEXT_POLICY), second: ContextStamp(1, TEXT_POLICY)}, current_run=second, data_version=1)
    assert [m.text for m in result] == ["Nhắc lại giúp mình"]
    assert "Dữ kiện" not in history_protocol(messages[:1], 2)[0].text


@pytest.mark.postgres
async def test_sources_survive_live_save_page_reload_export_and_legacy_redaction(clients, monkeypatch):
    from app.ai.schemas import AiReply
    from tests.fakes import make_test_model
    from tests.test_chat_persistence import enable
    from tests.test_context_privacy import turn
    from tests.test_multi_message_persistence import conversation

    app, actors = clients
    client, _ = actors[0]
    await enable(client)
    app.state.ai.model_override = make_test_model("ready")

    async def answer(**kwargs):
        kwargs["context"].public_search = True  # Trusted search-renderer boundary; SDK provenance has separate tests.
        return AiReply(parts=[AiOutput(text="😀ơi", citations=[citation()])])

    monkeypatch.setattr(app.state.ai.provider, "run_reply", answer)
    url = await conversation(client)
    run = await turn(app, client, url, "Tra cứu", make_test_model("unused"))
    assert run.terminal_status == "completed"
    for suffix in ("?responseProtocol=3", "?responseProtocol=3&limit=1", "/export"):
        view = (await client.get(url + suffix)).json()
        assert view["messages"][-1]["citations"] == [citation()]
    assert (await client.get(url)).json()["messages"][-1]["text"] != "😀ơi"
    for protocol in (1, 2, 3):
        wire = (await client.get(f"/api/v1/ai/runs/{run.id}/events?protocol={protocol}")).text
        assert ("example.org" in wire) == (protocol == 3)
    # Re-read on a worker with no local transcript or run.
    app.state.ai.runs.clear()
    app.state.ai.store.clear()
    assert (await client.get(url + "?responseProtocol=3")).json()["messages"][-1]["citations"] == [citation()]


def test_default_send_digest_keeps_the_pre_search_shape():
    from app.ai.schemas import idempotency_input
    base = dict(text="Chào", clientMessageId=uuid4(), expectedConversationVersion=1)
    old = StartRunInput(**base)
    # Byte-identical to the previous release's digest input, so a cross-rollout retry matches.
    assert idempotency_input(old) == old.model_dump_json(include={"text", "mood_scope"})
    v3 = StartRunInput(**base, responseProtocol=3)
    web = StartRunInput(**base, responseProtocol=3, promptOptions={"tools": ["web_search"]})
    assert len({idempotency_input(old), idempotency_input(v3), idempotency_input(web)}) == 3


@pytest.mark.postgres
async def test_uncited_sibling_page_is_redacted_for_old_clients_but_exported_in_full(clients, monkeypatch):
    from app.ai.schemas import SEARCH_REFRESH, AiReply
    from tests.fakes import make_test_model
    from tests.test_chat_persistence import enable
    from tests.test_context_privacy import turn
    from tests.test_multi_message_persistence import conversation

    app, actors = clients
    client, _ = actors[0]
    await enable(client)
    app.state.ai.model_override = make_test_model("ready")
    uncited = "Dữ kiện 👩‍👩‍👧 chưa gắn nguồn."

    async def answer(**kwargs):
        kwargs["context"].public_search = True
        return AiReply(parts=[AiOutput(text=uncited), AiOutput(text="😀ơi", citations=[citation()])])

    monkeypatch.setattr(app.state.ai.provider, "run_reply", answer)
    url = await conversation(client)
    run = await turn(app, client, url, "Tra cứu", make_test_model("unused"))
    assert run.terminal_status == "completed"
    latest = (await client.get(url + "?responseProtocol=3&limit=1")).json()["messages"]
    assert [m["text"] for m in latest] == [uncited, "😀ơi"]  # Groups are never cut at the older edge.
    older = f"{url}?limit=1&before={latest[1]['id']}"
    # A page holding only the uncited sibling still carries the turn-level marker.
    v3 = (await client.get(older + "&responseProtocol=3")).json()["messages"]
    assert [(m["text"], m["sourceBacked"], m["citations"]) for m in v3] == [(uncited, True, [])]
    for legacy in (older, older + "&responseProtocol=2"):
        page = (await client.get(legacy)).json()["messages"]
        assert [(m["text"], m["cards"], m["citations"]) for m in page] == [(SEARCH_REFRESH, [], [])]
    full = (await client.get(url)).json()["messages"]
    assert uncited not in str(full) and "example.org" not in str(full)
    for protocol in (1, 2):
        wire = (await client.get(f"/api/v1/ai/runs/{run.id}/events?protocol={protocol}")).text
        assert "chưa gắn nguồn" not in wire and "example.org" not in wire and "sourceBacked" not in wire
    exported = (await client.get(url + "/export")).json()["messages"]
    bot = [m for m in exported if m["actor"] == "bot"]
    assert [m["text"] for m in bot] == [uncited, "😀ơi"]
    assert all(m["sourceBacked"] for m in bot) and bot[1]["citations"] == [citation()]
    assert not any(m["sourceBacked"] for m in exported if m["actor"] == "self")
