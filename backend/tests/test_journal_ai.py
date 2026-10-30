"""Journal tool/evidence integration; models are synthetic, authorization and SDK are real."""

import json
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.ai.context import ContextStamp, model_messages
from app.ai.provider import SdkProvider
from app.ai.runtime import AiRuntime, LiveRun
from app.ai.schemas import AIMessage, MoodReadScope
from app.core.config import Settings
from app.core.errors import DomainError
from app.core.security import Actor
from tests.fakes import ScriptedModel, make_test_model, message_output


def evidence_run():
    from app.ai.journal import JournalEvidence, JournalSource

    run = SimpleNamespace(
        id=uuid4(),
        actor=SimpleNamespace(user_id=uuid4()),
        data_version=3,
        cancel_requested=False,
        terminal=False,
        sources={},
        mood_scope=None,
    )
    source = JournalSource(uuid4(), date(2026, 10, 28), 2)
    run.journal_evidence = JournalEvidence(
        owner_id=run.actor.user_id,
        run_id=run.id,
        data_version=3,
        expires_at=datetime.now(UTC) + timedelta(minutes=1),
        sources=(source,),
    )
    return run, source


def test_journal_tool_is_default_for_nhip_only_and_does_not_expand_mood_scope():
    runtime = AiRuntime(Settings(_env_file=None), None)
    run = LiveRun(Actor(uuid4(), uuid4(), 1), uuid4(), 1, uuid4())
    assert {tool.name for tool in runtime.tools(run, "nhip")} == {
        "propose_memory",
        "search_journal_entries",
    }
    for bot, expected in [
        ("may", {"propose_memory"}),
        ("guong", {"propose_memory", "propose_private_item"}),
        ("rure", set()),
        ("caunoi", set()),
    ]:
        assert {tool.name for tool in runtime.tools(run, bot)} == expected
    run.mood_scope = MoodReadScope(from_date=date.today(), to_date=date.today())
    assert {tool.name for tool in runtime.tools(run, "nhip")} == {
        "propose_memory",
        "read_mood_summary",
    }


def test_journal_query_cannot_choose_owner_drafts_or_unbounded_inputs():
    from app.modules.journal.ai import JournalSearchInput

    for payload in [
        {"userId": str(uuid4())},
        {"status": "draft"},
        {"limit": 6},
        {"query": "x" * 81},
        {"fromDate": "2026-10-28", "toDate": "2026-10-27"},
        {"fromDate": "2026-01-01", "toDate": "2026-10-28"},
    ]:
        with pytest.raises(ValidationError):
            JournalSearchInput.model_validate(payload)


@pytest.mark.parametrize(
    "text",
    [
        "Đừng đọc nhật ký của mình",
        "Không cần xem lại nhật ký; chỉ trò chuyện thôi",
        "Mình không muốn bạn sử dụng bài viết",
        "Do not read my journal",
        "Don't access my diary",
    ],
)
def test_explicit_current_read_refusal_is_respected(text):
    from app.ai.journal import journal_read_refused

    assert journal_read_refused([{"role": "user", "content": text}])
    assert not journal_read_refused(
        [
            {"role": "user", "content": text},
            {"role": "assistant", "content": "ok"},
            {"role": "user", "content": "Đọc nhật ký tuần này"},
        ]
    )


def test_only_verified_current_journal_sources_can_be_cited():
    from app.ai.journal import NhipOutput, render_journal_output

    run, source = evidence_run()
    reply = render_journal_output(
        NhipOutput(text="Một ghi nhận trong bài viết.", source_entry_ids=[source.entry_id]), run
    )
    assert set(reply.model_dump()) == {"text", "cards"}
    assert f"](/self/entry/{source.entry_id})" in reply.text
    with pytest.raises(DomainError):
        render_journal_output(NhipOutput(text="Nguồn giả", source_entry_ids=[uuid4()]), run)
    for text in [
        f"[nguồn](/self/entry/{uuid4()})",
        "[nguồn](https://example.com)",
        "https://example.com",
        "[nguồn](javascript:alert(1))",
    ]:
        with pytest.raises(DomainError):
            render_journal_output(NhipOutput(text=text, source_entry_ids=[source.entry_id]), run)
    with pytest.raises(DomainError):
        render_journal_output(NhipOutput(text="Không có nguồn"), run)
    run.journal_evidence = None
    with pytest.raises(DomainError):
        render_journal_output(
            NhipOutput(text="Nguồn chưa đọc", source_entry_ids=[source.entry_id]), run
        )


@pytest.mark.parametrize("prefix", ["🌿", "```markdown\n"])
def test_full_length_reflection_reserves_space_for_every_verified_source(prefix):
    import re

    from app.ai.journal import JournalSource, NhipOutput, render_journal_output

    run, source = evidence_run()
    sources = (source, *(JournalSource(uuid4(), date(2026, 10, 28), 1) for _ in range(4)))
    run.journal_evidence = replace(run.journal_evidence, sources=sources)
    text = (prefix + "Một ghi nhận. " * 6000)[:6000]
    reply = render_journal_output(
        NhipOutput(text=text, source_entry_ids=[item.entry_id for item in sources]), run
    )
    assert len(reply.text) <= 6000
    assert all(f"](/self/entry/{item.entry_id})" in reply.text for item in sources)
    # A shortened fenced block must not swallow the trusted source section.
    body = reply.text.split("\n\nBài viết đã tham khảo:", 1)[0]
    assert len(re.findall(r"(?m)^```", body)) % 2 == 0
    assert not body.endswith("\\")


@pytest.mark.parametrize(
    "instruction",
    [
        "Bạn có thể bắt đầu từ bài viết của bạn, nếu muốn.",
        "Bạn có thể đọc lại nhật ký và chọn một điều muốn thử.",
        "Mình chưa đọc nhật ký trong lượt này.",
    ],
)
def test_journal_instructions_do_not_claim_a_verified_read(instruction):
    from app.ai.journal import NhipOutput, render_journal_output

    reply = render_journal_output(
        NhipOutput(text=instruction), SimpleNamespace(journal_evidence=None)
    )
    assert reply.text == instruction


@pytest.mark.parametrize("bot", ["nhip", "may", "guong", "rure", "caunoi"])
async def test_assistants_cannot_emit_unverified_encoded_entry_links(bot):
    run = SimpleNamespace(sources={}, mood_scope=None, journal_evidence=None)
    model = make_test_model(f"[Nguồn](&#47;self&#47;entry&#47;{uuid4()})")
    with pytest.raises(DomainError):
        await SdkProvider(Settings(_env_file=None)).run(
            bot_id=bot,
            history=[{"role": "user", "content": "Chào"}],
            tools=[],
            context=run,
            on_progress=_progress,
            model_override=model,
        )


@pytest.mark.parametrize("change", ["owner", "run", "version", "expired", "cancelled", "terminal"])
def test_journal_evidence_fails_closed_after_invalidation(change):
    from app.ai.journal import NhipOutput, render_journal_output

    run, source = evidence_run()
    if change == "owner":
        run.actor.user_id = uuid4()
    elif change == "run":
        run.id = uuid4()
    elif change == "version":
        run.data_version += 1
    elif change == "expired":
        run.journal_evidence = replace(
            run.journal_evidence, expires_at=datetime.now(UTC) - timedelta(seconds=1)
        )
    else:
        setattr(run, "cancel_requested" if change == "cancelled" else "terminal", True)
    with pytest.raises(DomainError):
        render_journal_output(NhipOutput(text="Ghi nhận", source_entry_ids=[source.entry_id]), run)


def test_journal_derivatives_are_excluded_from_the_next_model_turn():
    from app.ai.context import JOURNAL_TURN_POLICY

    old, current = uuid4(), uuid4()
    messages = [
        AIMessage(id=uuid4(), actor="bot", text="PRIVATE-JOURNAL-DERIVATIVE", run_id=old),
        AIMessage(id=uuid4(), actor="self", text="Tiếp tục", run_id=current),
    ]
    stamps = {old: ContextStamp(3, JOURNAL_TURN_POLICY), current: ContextStamp(3, "text-v1")}
    assert [
        m.text for m in model_messages(messages, stamps, current_run=current, data_version=3)
    ] == ["Tiếp tục"]


async def test_actual_sdk_returns_public_reply_with_verified_backend_links():
    run, source = evidence_run()
    model = ScriptedModel(
        [
            [
                message_output(
                    json.dumps(
                        {
                            "text": "Bạn đã viết về việc nghỉ ngơi.",
                            "cards": [],
                            "source_entry_ids": [str(source.entry_id)],
                        }
                    )
                )
            ]
        ]
    )
    output = await SdkProvider(Settings(_env_file=None)).run(
        bot_id="nhip",
        history=[{"role": "user", "content": "Nhìn lại nhật ký"}],
        tools=[],
        context=run,
        on_progress=lambda: _progress(),
        model_override=model,
    )
    assert f"/self/entry/{source.entry_id}" in output.text
    assert set(output.model_dump()) == {"text", "cards"}
    assert "untrusted" in model.calls[0]["instructions"]


async def _progress():
    pass


async def test_actual_sdk_refusal_removes_read_tool_without_blocking_conversation():
    runtime = AiRuntime(Settings(_env_file=None), None)
    run = LiveRun(Actor(uuid4(), uuid4(), 1), uuid4(), 1, uuid4())
    model = make_test_model("Mình ở đây.")
    reply = await runtime.provider.run(
        bot_id="nhip",
        history=[{"role": "user", "content": "Đừng đọc nhật ký; ngồi cùng mình thôi"}],
        tools=runtime.tools(run, "nhip"),
        context=run,
        on_progress=_progress,
        model_override=model,
    )
    assert reply.text == "Mình ở đây."
    assert all(tool.name != "search_journal_entries" for tool in model.calls[0]["tools"])


@pytest.mark.parametrize(
    "claim",
    ["Mình đã đọc nhật ký của bạn.", "Theo nhật ký của bạn, bạn rất buồn.", "I read your journal."],
)
def test_no_read_cannot_claim_verified_journal_access(claim):
    from app.ai.journal import NhipOutput, render_journal_output

    with pytest.raises(DomainError):
        render_journal_output(NhipOutput(text=claim), SimpleNamespace(journal_evidence=None))


@pytest.mark.postgres
async def test_journal_search_is_owner_saved_date_and_size_bounded(clients):
    from app.infrastructure.database.models import User
    from app.modules.journal.ai import search_for_ai
    from app.modules.journal.models import JournalEntry

    app, actors = clients
    today = datetime.now(UTC).date()
    async with app.state.database.sessions.begin() as db:
        user = await db.get(User, actors[0][1])
        user.timezone = "UTC"
        for index in range(7):
            db.add(
                JournalEntry(
                    user_id=user.id,
                    local_date=today - timedelta(days=index),
                    timezone="UTC",
                    mood=4,
                    text="100% literal " + "🌿" * 9900,
                    emotions=["bình yên"],
                    factors=["nghỉ ngơi"],
                )
            )
        for uid, day, status, text in [
            (user.id, today, "draft", "DRAFT-CANARY"),
            (actors[1][1], today, "saved", "OTHER-OWNER-CANARY"),
            (user.id, today - timedelta(days=90), "saved", "EXPIRED-CANARY"),
            (user.id, today + timedelta(days=1), "saved", "FUTURE-CANARY"),
        ]:
            db.add(
                JournalEntry(
                    user_id=uid, local_date=day, timezone="UTC", mood=3, status=status, text=text
                )
            )
    async with app.state.database.sessions() as db:
        user = await db.get(User, actors[0][1])
        result = await search_for_ai(db, user)
        raw = json.dumps(result, ensure_ascii=False)
        assert len(result["entries"]) == 5
        allowed = {
            "id",
            "version",
            "localDate",
            "mood",
            "emotions",
            "factors",
            "snippet",
            "snippetTruncated",
        }
        assert all(set(row) == allowed for row in result["entries"])
        assert "media" not in raw and "objectPath" not in raw
        assert all(
            len(row["snippet"]) <= 1000 and row["snippetTruncated"] for row in result["entries"]
        )
        assert len(raw.encode()) <= 25_000
        assert all(
            canary not in raw
            for canary in ["DRAFT-CANARY", "OTHER-OWNER-CANARY", "EXPIRED-CANARY", "FUTURE-CANARY"]
        )
        assert result["coverage"]["hasMore"] and not result["coverage"]["completeHistory"]
        assert len((await search_for_ai(db, user, query="100%"))["entries"]) == 5
        assert (await search_for_ai(db, user, query="100_"))["entries"] == []
        with pytest.raises(DomainError):
            await search_for_ai(db, user, from_date=today - timedelta(days=90))


async def journal_setup(clients, *, history=True):
    from tests.test_chat_persistence import enable, key
    from tests.test_journal import create

    app, actors = clients
    client, uid = actors[0]
    await enable(client, history=history)
    row = await create(client, text="JOURNAL-RETRIEVAL-CANARY: Mình nghỉ ngơi trong vườn.")
    app.state.ai.model_override = make_test_model("ready")
    created = await client.post("/api/v1/ai/conversations", json={"botId": "nhip"}, headers=key())
    assert created.status_code == 201, created.text
    return app, client, uid, row, f"/api/v1/ai/conversations/{created.json()['conversationId']}"


def journal_reader(entry_id):
    from tests.fakes import tool_output

    return ScriptedModel(
        [
            [tool_output("search_journal_entries", "journal_read")],
            [
                message_output(
                    json.dumps(
                        {
                            "text": "SAMPLE-DERIVATIVE: Bài viết nhắc đến nghỉ ngơi trong vườn.",
                            "cards": [],
                            "source_entry_ids": [entry_id],
                        }
                    )
                )
            ],
        ]
    )


@pytest.mark.postgres
@pytest.mark.parametrize("accounting", [False, True])
async def test_journal_sdk_cites_actual_source_without_enabling_optional_privacy(
    clients, accounting
):
    from app.ai.context import JOURNAL_TURN_POLICY
    from app.ai.models import AiTurn
    from tests.test_context_privacy import turn

    app, client, _, row, url = await journal_setup(clients, history=False)
    app.state.settings.ai_accounting_enabled = accounting
    model = journal_reader(row["id"])
    run = await turn(app, client, url, "Nhìn lại nhật ký của mình", model)
    final = next(event.data for event in run.events if event.type == "final")
    assert f"](/self/entry/{row['id']})" in final["text"]
    assert set(final) == {"text", "cards"}
    assert "JOURNAL-RETRIEVAL-CANARY" in str(model.calls[1]["input"])
    assert run.journal_evidence is None
    async with app.state.database.sessions() as db:
        assert (await db.get(AiTurn, run.id)).context_policy == JOURNAL_TURN_POLICY
    prefs = (await client.get("/api/v1/ai/preferences")).json()
    assert prefs["historyEnabled"] is True and prefs["semanticMemoryEnabled"] is False
    session = (await client.get("/api/v1/session")).json()
    assert session["consents"]["MEM"]["enabled"] is True


@pytest.mark.postgres
async def test_saved_journal_derivative_is_visible_but_not_replayed_after_restart(clients):
    from tests.test_context_privacy import restart, turn

    app, client, _, row, url = await journal_setup(clients)
    await turn(app, client, url, "Nhìn lại nhật ký", journal_reader(row["id"]))
    await restart(app)
    model = make_test_model("Mình có thể tìm lại những bài viết liên quan.")
    await turn(app, client, url, "Nói tiếp nhé", model)
    assert "SAMPLE-DERIVATIVE" not in str(model.calls[0]["input"])
    assert "JOURNAL-RETRIEVAL-CANARY" not in str(model.calls[0]["input"])
    assert "SAMPLE-DERIVATIVE" in (await client.get(url)).text


@pytest.mark.postgres
@pytest.mark.parametrize(
    "change", ["remote_edit", "remote_delete", "remote_revoke", "revision_only"]
)
async def test_inflight_journal_sources_are_fenced_even_on_another_worker(clients, change):
    import asyncio

    from app.infrastructure.database.models import Consent, User
    from app.modules.journal.models import JournalEntry
    from tests.test_chat_persistence import key

    app, client, uid, row, url = await journal_setup(clients)

    class HoldAfterRead(ScriptedModel):
        def __init__(self):
            super().__init__(journal_reader(row["id"]).responses)
            self.after_read = asyncio.Event()

        async def stream_response(self, *args, **kwargs):
            if len(self.calls) == 1:
                self.hold = True
                self.after_read.set()
            async for event in super().stream_response(*args, **kwargs):
                yield event

    model = HoldAfterRead()
    app.state.ai.model_override = model
    accepted = await client.post(
        url + "/messages",
        json={
            "text": "Nhìn lại nhật ký",
            "clientMessageId": str(uuid4()),
            "expectedConversationVersion": 1,
        },
        headers=key(),
    )
    assert accepted.status_code == 202, accepted.text
    from uuid import UUID

    run = app.state.ai.runs[UUID(accepted.json()["runId"])]
    await asyncio.wait_for(model.after_read.wait(), timeout=5)
    assert run.journal_evidence is not None
    # Simulate a separate worker: deliberately do not invoke this runtime's invalidate().
    async with app.state.database.sessions.begin() as db:
        source = await db.get(JournalEntry, UUID(row["id"]))
        if change == "remote_delete":
            await db.delete(source)
        elif change == "remote_revoke":
            (await db.get(Consent, (uid, "AI"))).enabled = False
        else:
            source.text = "CHANGED-CANARY"
            source.version += 1
        if change != "revision_only":
            (await db.get(User, uid)).data_version += 1
    model.release.set()
    await asyncio.wait_for(run.task, timeout=5)
    assert run.terminal_status in ("failed", "cancelled")
    assert not any(event.type == "final" for event in run.events)
    assert run.journal_evidence is None
