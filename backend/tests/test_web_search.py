import json

import pytest


@pytest.mark.parametrize("card", [
    {"kind": "maps_search", "searchId": "00000000-0000-0000-0000-000000000001"},
    {"kind": "places", "places": [{"name": "Public cafe", "address": "Da Nang",
        "mapsUrl": "https://www.google.com/maps/search/?api=1&query=cafe", "fetchedAt": "2026-11-03T00:00:00Z"}]},
])
def test_grounded_model_contract_excludes_backend_owned_search_cards(card):
    from pydantic import ValidationError

    from app.ai.search.schemas import GroundedReply

    # The model must never be offered output variants that the renderer forbids.
    with pytest.raises(ValidationError):
        GroundedReply(messages=[{"segments": [{"text": "Try this cafe.", "sourceIds": []}], "cards": [card]}])
    schema = json.dumps(GroundedReply.model_json_schema())
    assert '"MapsSearchCard"' not in schema and '"PlacesCard"' not in schema


def test_grounded_segments_use_backend_sources_and_codepoints():
    from app.ai.search.citations import render_grounded_reply
    from app.ai.search.schemas import GroundedReply, SearchSource

    source = SearchSource(source_id="s1", title="Nguồn", url="https://example.org/article")
    draft = GroundedReply(messages=[{"segments": [{"text": "😀 ", "sourceIds": []},
        {"text": "Đúng vậy.", "sourceIds": ["s1"]}], "cards": []}])
    result = render_grounded_reply(draft, {"s1": source})
    assert result.parts[0].text == "😀 Đúng vậy."
    assert result.parts[0].citations[0].start == 2
    assert result.parts[0].citations[0].end == 11
    assert result.parts[0].citations[0].url == source.url
    with pytest.raises(ValueError):
        render_grounded_reply(draft, {})


async def test_isolated_web_request_caps_and_annotations():
    from app.ai.search.web import WebSearchAdapter

    requests = []

    async def create(**kwargs):
        requests.append(kwargs)
        return {"status": "completed", "output": [
            {"type": "web_search_call", "id": "w1", "status": "completed"},
            {"type": "message", "content": [{"type": "output_text", "text": "Thông tin mới.",
             "annotations": [{"type": "url_citation", "title": "Nguồn", "url": "https://example.org/article",
                               "start_index": 0, "end_index": 13}]}]}],
             "usage": {"input_tokens": 100, "output_tokens": 20, "input_tokens_details": {"cached_tokens": 0}}}

    result = await WebSearchAdapter(create, "gpt-6-luna").search("thời tiết Hà Nội", timeout_seconds=10)
    assert requests[0]["input"] == "thời tiết Hà Nội"
    assert requests[0]["store"] is False
    assert requests[0]["max_tool_calls"] == 1
    assert requests[0]["max_output_tokens"] == 1200
    assert requests[0]["reasoning"] == {"effort": "low"}
    assert requests[0]["tool_choice"] == {"type": "web_search"}
    assert requests[0]["tools"][0]["search_context_size"] == "low"
    assert result.calls == 1 and result.input_tokens == 100
    assert result.sources[0].url == "https://example.org/article"
    assert "history" not in json.dumps(requests)


@pytest.mark.parametrize("prompt", ["email của tôi a@example.org tin mới", "mật khẩu sk-12345", "nhật ký hôm qua tôi viết về mẹ", "số điện thoại 0901234567",
    "Find the latest treatment options for my daughter Alice Nguyen diagnosed with HIV",
    "Tra cứu cách chữa bệnh cho con gái Nguyễn Thị Mai", "Tin mới về bệnh án của anh Nam"])
def test_private_query_fails_closed(prompt):
    from app.ai.search.policy import safe_query
    assert safe_query(prompt) is None


def test_public_current_intent_no_location_guess():
    from app.ai.schemas import PromptOptions
    from app.ai.search.policy import search_intent
    assert search_intent("Tìm quán cà phê gần mình", PromptOptions()).maps
    assert search_intent("Tin mới nhất về Python", PromptOptions()).web
    assert not search_intent("Hôm nay mình thấy mệt", PromptOptions()).web


def test_unknown_narrative_is_not_a_public_query_and_known_topics_are_projected():
    from app.ai.search.policy import safe_query
    assert safe_query("Tin mới nhất về cách giúp bé Lan bị bạo hành ở trường Nguyễn Trãi") is None
    assert safe_query("Tin mới nhất về Python cho nhóm Alice Nguyen ở đường X") == "Thông tin mới nhất về Python"


@pytest.mark.parametrize(("prompt", "query"), [
    ("Thời tiết Hà Nội hôm nay thế nào?", "thời tiết tại Hà Nội hôm nay"),
    ("giúp mình tra thời tiết Đà Lạt cuối tuần", "thời tiết tại Đà Lạt cuối tuần"),
    ("sự kiện ở Sài Gòn cuối tuần", "sự kiện tại TP. Hồ Chí Minh cuối tuần"),
    ("Tin mới về AI", "Thông tin mới nhất về trí tuệ nhân tạo"),
    # A street/school/home is never in the public gazetteer, so it is dropped, not copied.
    ("Tin mới nhất về Python cho nhóm Alice Nguyen ở đường X", "Thông tin mới nhất về Python"),
])
def test_public_slots_keep_gazetteer_place_and_time_but_no_free_words(prompt, query):
    from app.ai.search.policy import safe_query
    assert safe_query(prompt) == query


def test_refusal_reason_separates_private_disclosure_from_unsupported_topic():
    from app.ai.search.policy import private_prompt, safe_query
    # Personal disclosures ask for a public topic; the place slot never rescues them.
    for prompt in ("Mình ở Hà Nội, thời tiết hôm nay?", "Tin mới nhất về cách giúp bé Lan bị bạo hành ở trường Nguyễn Trãi"):
        assert safe_query(prompt) is None and private_prompt(prompt)
    # A public but unregistered topic is reported as unsupported, not as a privacy problem.
    assert safe_query("Tin mới nhất về chính trị") is None
    assert not private_prompt("Tin mới nhất về chính trị")


async def test_web_after_maps_needs_twenty_seconds_and_never_claims_or_dispatches():
    import time
    from types import SimpleNamespace

    from app.ai.search.service import WebSearchService
    from app.core.config import Settings

    class Unreachable:
        def __getattr__(self, name):
            raise AssertionError(f"no budget claim or provider call: {name}")

    runtime = SimpleNamespace(settings=Settings(_env_file=None, ai_timeout_seconds=30, ai_dispatch_gate_enabled=False), database=Unreachable(),
                              web_search_adapter=Unreachable(), check=Unreachable())
    run = SimpleNamespace(started=time.monotonic() - 11)  # Maps start/admission used 11 of 30 seconds.
    result = await WebSearchService(runtime).search("thời tiết tại Hà Nội", run)
    assert result.status == "unavailable" and result.sources == []
