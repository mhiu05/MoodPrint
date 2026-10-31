"""P1-04: 1–4 validated bubbles per run behind AI_MULTI_MESSAGE_ENABLED (default off)."""

import json

import pytest
from agents import OutputGuardrailTripwireTriggered
from pydantic import ValidationError

from app.ai.provider import SdkProvider
from app.ai.schemas import AiReply, Bubble, CompanionReply
from app.core.config import Settings
from app.core.errors import DomainError
from tests.fakes import ScriptedModel, make_test_model, message_output
from tests.test_journal_ai import evidence_run


async def no_progress():
    pass


def bubbles(*texts, cards=None):
    cards = cards or {}
    return {"messages": [{"text": text, "cards": cards.get(index, [])} for index, text in enumerate(texts)]}


def scripted(payload) -> ScriptedModel:
    return ScriptedModel([[message_output(json.dumps(payload, ensure_ascii=False))]])


def multi_settings() -> Settings:
    return Settings(_env_file=None, ai_multi_message_enabled=True)


@pytest.mark.parametrize(("count", "ok"), [(0, False), (1, True), (2, True), (4, True), (5, False)])
def test_companion_reply_bounds(count, ok):
    payload = bubbles(*(f"Ý số {index}" for index in range(count)))
    if ok:
        assert len(CompanionReply.model_validate(payload).messages) == count
    else:
        with pytest.raises(ValidationError):
            CompanionReply.model_validate(payload)


@pytest.mark.parametrize(
    "payload",
    [
        bubbles("   "),  # visible text required
        bubbles("Giống nhau", "giống nhau"),  # no duplicate bubbles
        bubbles("x" * 1501),  # per-bubble bound
        bubbles("a" * 1500, "b" * 1500, "c" * 1500, "d" * 1500),  # joined v1 text must stay <= 6000
        bubbles("Một", "Hai", cards={0: [{"kind": "mood_form"}] * 2, 1: [{"kind": "discovery"}] * 2}),
        {"messages": [{"text": "Một", "cards": [], "extra": 1}]},
    ],
)
def test_companion_reply_rejects_unsafe_shapes(payload):
    with pytest.raises(ValidationError):
        CompanionReply.model_validate(payload)


def test_bubble_text_is_trimmed():
    assert Bubble.model_validate({"text": "  Chào bạn  ", "cards": []}).text == "Chào bạn"


def test_joined_reply_is_the_v1_representation():
    reply = AiReply.model_validate(
        {"parts": [{"text": "Một", "cards": []}, {"text": "Hai", "cards": [{"kind": "mood_form"}]}]}
    )
    joined = reply.joined()
    assert joined.text == "Một\n\nHai"
    assert [card.kind for card in joined.cards] == ["mood_form"]


async def test_flag_off_keeps_single_ai_output_contract():
    model = make_test_model("Một phản hồi.")
    reply = await SdkProvider(Settings(_env_file=None)).run_reply(
        bot_id="may", history=[], tools=[], context={}, on_progress=no_progress, model_override=model
    )
    assert [part.text for part in reply.parts] == ["Một phản hồi."]
    schema = json.dumps(model.calls[0]["output_schema"].json_schema())
    assert '"messages"' not in schema and '"text"' in schema


async def test_flag_on_returns_ordered_parts_and_requests_bubble_schema():
    model = scripted(bubbles("Nghe mệt thật.", "Tối nay thử ngủ sớm hơn nhé?", cards={1: [{"kind": "mood_form"}]}))
    provider = SdkProvider(multi_settings())
    reply = await provider.run_reply(
        bot_id="may", history=[], tools=[], context={}, on_progress=no_progress, model_override=model
    )
    assert [part.text for part in reply.parts] == ["Nghe mệt thật.", "Tối nay thử ngủ sớm hơn nhé?"]
    assert [[card.kind for card in part.cards] for part in reply.parts] == [[], ["mood_form"]]
    assert '"messages"' in json.dumps(model.calls[0]["output_schema"].json_schema())
    # Legacy callers (evals, scripts) receive the same joined text that SSE v1 sends.
    joined = await provider.run(
        bot_id="may", history=[], tools=[], context={}, on_progress=no_progress,
        model_override=scripted(bubbles("A", "B")),
    )
    assert joined.text == "A\n\nB"


async def test_flag_on_guardrail_checks_every_bubble():
    with pytest.raises(OutputGuardrailTripwireTriggered):
        await SdkProvider(multi_settings()).run_reply(
            bot_id="may", history=[], tools=[], context=None, on_progress=no_progress,
            model_override=scripted(bubbles("Chào bạn.", "Mình đã lưu hồ sơ của bạn.")),
        )


async def test_flag_on_rejects_model_written_journal_link_in_any_bubble():
    with pytest.raises(DomainError) as error:
        await SdkProvider(multi_settings()).run_reply(
            bot_id="may", history=[], tools=[], context=None, on_progress=no_progress,
            model_override=scripted(bubbles("Chào.", "Xem [đây](/self/entry/abc)")),
        )
    assert error.value.code == "JOURNAL_EVIDENCE_REQUIRED"


async def test_flag_on_journal_citation_is_added_by_backend_to_last_bubble_only():
    run, source = evidence_run()
    payload = {**bubbles("Bạn đã viết về việc nghỉ ngơi.", "Hôm nay thử nghỉ mắt 10 phút nhé."),
               "source_entry_ids": [str(source.entry_id)]}
    reply = await SdkProvider(multi_settings()).run_reply(
        bot_id="nhip", history=[{"role": "user", "content": "Nhìn lại nhật ký"}], tools=[], context=run,
        on_progress=no_progress, model_override=scripted(payload),
    )
    assert len(reply.parts) == 2
    assert "/self/entry/" not in reply.parts[0].text
    assert reply.parts[1].text.startswith("Hôm nay thử nghỉ mắt 10 phút nhé.")
    assert f"/self/entry/{source.entry_id}" in reply.parts[1].text
    assert len(reply.joined().text) <= 6000


async def test_flag_on_journal_link_written_by_model_in_first_bubble_is_rejected():
    run, source = evidence_run()
    payload = {**bubbles(f"Xem [bài](/self/entry/{source.entry_id})", "Ổn."),
               "source_entry_ids": [str(source.entry_id)]}
    with pytest.raises(DomainError) as error:
        await SdkProvider(multi_settings()).run_reply(
            bot_id="nhip", history=[{"role": "user", "content": "Nhìn lại nhật ký"}], tools=[], context=run,
            on_progress=no_progress, model_override=scripted(payload),
        )
    assert error.value.code == "JOURNAL_CITATION_INVALID"
