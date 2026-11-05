"""Synthetic hybrid ranking with real SQL and unchanged journal evidence gates."""

import json
import time
from datetime import timedelta
from uuid import UUID

import pytest
from pydantic import ValidationError
from sqlalchemy import update

from app.core.security import Actor
from app.infrastructure.database.models import User
from app.modules.journal.ai import JournalSearchInput
from app.modules.journal.ai_models import JournalAiSettings, JournalEntryEmbedding
from app.modules.journal.retrieval import hybrid_search, journal_query_vector
from tests.fakes import FakeEmbedder
from tests.test_journal import create, today
from tests.test_journal_indexing import due, tick


async def search(app, uid, query="", **options):
    async with app.state.database.sessions() as db:
        user = await db.get(User, uid)
        return await hybrid_search(db, user, JournalSearchInput(query=query, **options),
                                   query_vector=await FakeEmbedder(256).embed(query, "query") if query else None,
                                   settings=app.state.settings, reason=None)


async def test_paraphrase_query_finds_entry_without_substring(journal_configured):
    app, actors = journal_configured
    row = await create(actors[0][0], text="mệt rã rời sau ca đêm", localDate=str(today()-timedelta(days=5)))
    app.state.settings.journal_recent_k = 0
    app.state.settings.journal_similarity_threshold = .15
    await due(app)
    await tick(app, FakeEmbedder(256))
    found = await search(app, actors[0][1], "kiệt sức")
    assert found["entries"][0]["id"] == row["id"]
    assert found["entries"][0]["match"] == "semantic"
    assert found["coverage"]["indexed"] == 1
    app.state.settings.journal_semantic_enabled = False
    assert (await search(app, actors[0][1], "kiệt sức"))["entries"] == []


async def test_hybrid_always_includes_recent_entries(journal_configured):
    app, actors = journal_configured
    old = await create(actors[0][0], text="mệt rã rời", localDate=str(today()-timedelta(days=5)))
    recent = await create(actors[0][0], text="đọc sách vui")
    app.state.settings.journal_similarity_threshold = .1
    await due(app)
    await tick(app, FakeEmbedder(256))
    result = await search(app, actors[0][1], "kiệt sức")
    assert {old["id"], recent["id"]} <= {item["id"] for item in result["entries"]}


async def test_unindexed_user_reports_not_indexed(journal_configured):
    app, actors = journal_configured
    await create(actors[0][0], text="nội dung tổng hợp")
    result = await search(app, actors[0][1], "nội dung")
    assert result["coverage"]["retrieval"] == {"mode": "keyword", "reason": "not_indexed"}


async def test_vector_of_an_older_revision_is_ignored(journal_configured):
    app, actors = journal_configured
    await create(actors[0][0], text="mệt rã rời")
    await due(app)
    await tick(app, FakeEmbedder(256))
    async with app.state.database.sessions.begin() as db:
        await db.execute(update(JournalEntryEmbedding).values(entry_version=99))
    app.state.settings.journal_recent_k = 0
    assert (await search(app, actors[0][1], "kiệt sức"))["entries"] == []


async def test_query_embedding_timeout_falls_back_within_budget(journal_configured):
    app, actors = journal_configured
    actor = Actor(actors[0][1], UUID(int=1), 1)
    started = time.monotonic()
    vector, version, reason = await journal_query_vector(app.state.database, app.state.settings, actor,
                                                       "kiệt sức", embedder=FakeEmbedder(256, delay=10))
    assert time.monotonic()-started < 3.5
    assert vector is None and version == 1 and reason == "timeout"
    async with app.state.database.sessions() as db:
        result = await hybrid_search(db, await db.get(User, actor.user_id), JournalSearchInput(query="kiệt sức"),
                                     query_vector=vector, settings=app.state.settings, reason=reason)
    assert result["coverage"]["retrieval"] == {"mode": "keyword", "reason": "timeout"}


async def test_settings_change_between_vector_and_lock_discards_vector(journal_configured):
    app, actors = journal_configured
    actor = Actor(actors[0][1], UUID(int=1), 1)
    await create(actors[0][0], text="mệt rã rời")
    await due(app)
    await tick(app, FakeEmbedder(256))
    vector, version, _ = await journal_query_vector(app.state.database, app.state.settings, actor, "kiệt sức", embedder=FakeEmbedder(256))
    assert vector and version == 1
    async with app.state.database.sessions.begin() as db:
        db.add(JournalAiSettings(user_id=actor.user_id, version=2, embedding_enabled=False))
    app.state.settings.journal_recent_k = 0
    assert (await search(app, actor.user_id, "kiệt sức"))["entries"] == []


async def test_limit_defaults_to_6_and_caps_at_8_within_24kb(journal_configured):
    app, actors = journal_configured
    assert JournalSearchInput().limit == 6
    assert JournalSearchInput(limit=8).limit == 8
    with pytest.raises(ValidationError):
        JournalSearchInput(limit=9)
    for day in range(10):
        await create(actors[0][0], text="🌿"*9900, localDate=str(today()-timedelta(days=day)))
    result = await search(app, actors[0][1], "🌿", limit=8)
    assert len(json.dumps(result["entries"], ensure_ascii=False).encode()) <= 24_000
    assert result["coverage"]["hasMore"]


async def test_instructions_describe_ranking_and_usage_marker_is_j2(monkeypatch):
    from types import SimpleNamespace
    from uuid import uuid4

    from app.ai.journal import journal_instructions
    from app.ai.runtime import AiRuntime
    from app.core.config import Settings

    instructions = journal_instructions(SimpleNamespace(sources={}))
    assert "meaning and keywords" in instructions
    assert "Call search_journal_entries before answering" in instructions
    versions = []

    async def reserve(*args, **kwargs):
        versions.append(args[5])

    monkeypatch.setattr("app.ai.runtime.reserve_accounting", reserve)
    runtime = AiRuntime(Settings(_env_file=None, ai_accounting_enabled=True), None)
    await runtime.reserve_usage(None, uuid4(), uuid4(), "nhatky")
    assert versions[0].endswith("+j2") and len(versions[0]) <= 60


@pytest.mark.parametrize("failure", [RuntimeError("synthetic provider detail"), ValueError("invalid")])
async def test_provider_failure_is_content_free_keyword_fallback(journal_configured, failure):
    app, actors = journal_configured
    actor = Actor(actors[0][1], UUID(int=1), 1)
    vector, version, reason = await journal_query_vector(app.state.database, app.state.settings, actor, "nghỉ ngơi", embedder=FakeEmbedder(256, error=failure))
    assert vector is None and version == 1 and reason == "provider_unavailable"
    async with app.state.database.sessions() as db:
        result = await hybrid_search(db, await db.get(User, actor.user_id), JournalSearchInput(query="nghỉ ngơi"), query_vector=None, settings=app.state.settings, reason=reason)
    assert result["coverage"]["retrieval"] == {"mode": "keyword", "reason": "provider_unavailable"}


async def test_citation_must_be_a_returned_entry(journal_configured):
    from app.ai.journal import NhipOutput, render_journal_output
    from app.core.errors import DomainError
    from tests.test_journal_ai import evidence_run

    _app, actors = journal_configured
    unreturned = await create(actors[0][0], text="Có tồn tại nhưng chưa được tool trả về")
    run, _source = evidence_run()
    with pytest.raises(DomainError) as caught:
        render_journal_output(NhipOutput(text="Không được trích dẫn", source_entry_ids=[unreturned["id"]]), run)
    assert caught.value.status == 409 and caught.value.code == "JOURNAL_CITATION_INVALID"


@pytest.mark.parametrize("denial", ["refusal", "mood_scope"])
async def test_refusal_and_mood_scope_still_deny_the_tool(denial):
    from datetime import date
    from uuid import uuid4

    from app.ai.runtime import AiRuntime, LiveRun
    from app.ai.schemas import MoodReadScope
    from app.core.config import Settings
    from tests.fakes import make_test_model

    runtime = AiRuntime(Settings(_env_file=None), None)
    run = LiveRun(Actor(uuid4(), uuid4(), 1), uuid4(), 1, uuid4())
    if denial == "mood_scope":
        run.mood_scope = MoodReadScope(from_date=date.today(), to_date=date.today())
        assert all(tool.name != "search_journal_entries" for tool in runtime.tools(run, "nhip"))
        return
    model = make_test_model("Mình ở đây.")

    async def progress():
        pass

    await runtime.provider.run(bot_id="nhip", history=[{"role": "user", "content": "Đừng đọc nhật ký" if denial == "refusal" else "Tâm trạng tuần này"}],
                               tools=runtime.tools(run, "nhip"), context=run, on_progress=progress, model_override=model)
    assert all(tool.name != "search_journal_entries" for tool in model.calls[0]["tools"])


async def test_timeout_tool_result_completes_the_actual_sdk_turn(journal_configured):
    from tests.fakes import ScriptedModel, message_output, tool_output
    from tests.test_context_privacy import turn
    from tests.test_journal_ai import journal_setup

    app, client, _uid, row, url = await journal_setup(journal_configured)
    app.state.ai.journal_embedder = FakeEmbedder(256, delay=10)
    call = tool_output("search_journal_entries", "timeout")
    call.arguments = json.dumps({"query": "kiệt sức"})
    model = ScriptedModel([[call], [message_output(json.dumps({"text": "Một trang gần đây.", "cards": [], "source_entry_ids": [row["id"]]}))]])
    run = await turn(app, client, url, "Nhìn lại nhật ký", model)
    assert run.terminal_status == "completed"
    assert '"reason": "timeout"' in str(model.calls[1]["input"])


async def test_runtime_discards_vector_after_settings_version_changes(journal_configured):
    import asyncio

    from tests.fakes import ScriptedModel, message_output, tool_output
    from tests.test_context_privacy import turn
    from tests.test_journal_ai import journal_setup

    app, client, uid, _row, url = await journal_setup(journal_configured)
    await due(app)
    await tick(app, FakeEmbedder(256))
    gate = asyncio.Event()
    fake = FakeEmbedder(256, delay=gate)
    app.state.ai.journal_embedder = fake
    call = tool_output("search_journal_entries", "changed_settings")
    call.arguments = json.dumps({"query": "kiệt sức"})
    app.state.settings.journal_recent_k = 0
    model = ScriptedModel([[call], [message_output(json.dumps({"text": "Chưa có trang phù hợp.", "cards": [], "source_entry_ids": []}))]])
    task = asyncio.create_task(turn(app, client, url, "Nhìn lại nhật ký", model))
    try:
        await asyncio.wait_for(fake.started.wait(), 5)
        async with asyncio.timeout(1), app.state.database.sessions.begin() as db:
            # Keep eligibility enabled: the version fence must discard the old vector.
            db.add(JournalAiSettings(user_id=uid, version=2))
            await db.execute(update(JournalEntryEmbedding).values(settings_version=2))
    finally:
        gate.set()
        await task
    assert '"reason": "disabled"' in str(model.calls[1]["input"])
