"""Integration vertical slice (INT-03..06): the real retriever inside the real Companion.

Real PostgreSQL with RLS, the real ``PgVectorKnowledgeRetriever`` over a published corpus, the real
proposal, approval and incident services. Only the model is scripted and the query embedder is the
deterministic ``HashingEmbedder`` (no Voyage call). Nothing here falls back to the fixture retriever.

Covered: conversation, real retrieval, citation checked against the corpus, no-result without a
fabricated citation, case context, propose, no write before approval, approval persists exactly what the
user saw, history restore, and user A / user B isolation.
"""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import replace
from uuid import uuid4

import pytest
from agents.testing import ModelStep, ScriptedModel, assistant_message, function_call
from agents.usage import Usage
from app.agent_gateway.sse import RunStream, produce
from app.core.errors import ApiError
from app.modules.conversations.service import ConversationService
from app.modules.incidents.service import IncidentService
from moodprint_agent.knowledge.embedder import HashingEmbedder
from moodprint_agent.knowledge.ingest.cli import main as ingest
from moodprint_agent.knowledge.retriever import PgVectorKnowledgeRetriever
from moodprint_agent.runtime import CompanionRuntime
from moodprint_agent.tools.factory import build_registry
from moodprint_shared.config import AppConfig
from moodprint_shared.contracts.errors import KnowledgeUnavailable, NotFound
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from backend.tests.integration.agent.test_incident_tools import (
    PROPOSE,
    ask_to_save,
    finish_resume,
    propose_via_agent,
    world,
)
from backend.tests.integration.conftest import local_value

pytestmark = pytest.mark.integration
CFG = AppConfig()


def usage() -> Usage:
    return Usage(requests=1, input_tokens=5, output_tokens=5, total_tokens=10)


@pytest.fixture
async def admin():
    engine = create_async_engine(local_value("TEST_ADMIN_DATABASE_URL"), hide_parameters=True)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
def published_corpus():
    """Seed and publish the synthetic corpus into this stack's knowledge schema (loopback only)."""
    os.environ.setdefault("TEST_ADMIN_DATABASE_URL", local_value("TEST_ADMIN_DATABASE_URL"))
    assert ingest(["seed-synthetic", "--target", "test-env"]) == 0


async def rows(admin, sql, **params):
    async with admin.connect() as conn:
        return (await conn.execute(text(sql), params)).mappings().all()


async def run_turn(service, auth, conversation_id, runtime, retriever, content):
    turn = await service.begin_turn(auth, conversation_id, uuid4(), content)
    await produce(
        knowledge=retriever,
        stream=RunStream(),
        runtime=runtime,
        service=service,
        auth=auth,
        turn=turn,
        request_id="int-slice",
        content=content,
    )
    return turn


def knowledge_turn(query: str, answer: str) -> CompanionRuntime:
    return CompanionRuntime(
        CFG,
        build_registry(CFG),
        model=ScriptedModel(
            [
                ModelStep(
                    output=[function_call("knowledge_search", {"query": query}, call_id="k1")],
                    usage=usage(),
                ),
                ModelStep(output=[assistant_message(answer)], usage=usage()),
            ]
        ),
    )


async def assistant_rows(admin, conversation_id):
    return await rows(
        admin,
        "SELECT content, citations FROM app.messages "
        "WHERE conversation_id=:c AND role='assistant' ORDER BY created_at",
        c=conversation_id,
    )


def cited(citation, snake, camel):
    return citation.get(camel) or citation.get(snake)


async def test_real_retrieval_checked_citations_approval_isolation_and_restore(
    db_engine, identities, admin, published_corpus
):
    auth, other, service, case, conversation = await world(db_engine, identities)
    retriever = PgVectorKnowledgeRetriever(db_engine, HashingEmbedder(), CFG.knowledge)
    assert type(retriever).__name__ == "PgVectorKnowledgeRetriever"  # never the fixture

    # 1. A grounded answer: the model's real citation survives, a forged one is dropped.
    await run_turn(
        service,
        auth,
        conversation,
        knowledge_turn(
            "bị nhắn tin dọa trong nhóm lớp",
            "Hãy lưu lại tin nhắn trước khi chặn [S1]. Nguồn này không có thật [S9].",
        ),
        retriever,
        "Có bạn nhắn tin dọa mình trong nhóm lớp",
    )
    (grounded,) = await assistant_rows(admin, conversation)
    assert len(grounded["citations"]) == 1, grounded
    assert "[S9]" not in grounded["content"] and "[1]" in grounded["content"]
    citation = grounded["citations"][0]
    (published,) = await rows(
        admin, "SELECT version FROM knowledge.corpus_versions WHERE status='published'"
    )
    document = await rows(
        admin,
        "SELECT d.document_id, d.source_id, d.licence_class FROM knowledge.documents d "
        "WHERE d.corpus_version=:v AND d.document_id=:d AND d.source_id=:s",
        v=published["version"],
        d=cited(citation, "document_id", "documentId"),
        s=cited(citation, "source_id", "sourceId"),
    )
    assert len(document) == 1, (
        "the citation must name a document and source of the published corpus"
    )
    assert document[0]["licence_class"] in {"authored", "open_reuse"}

    # 2. No result: no citation can exist, even if the model writes a marker.
    await run_turn(
        service,
        auth,
        conversation,
        knowledge_turn("công thức nấu phở bò", "Mình chưa có nguồn phù hợp cho câu này [S1]."),
        retriever,
        "Cho mình công thức nấu phở",
    )
    ungrounded = (await assistant_rows(admin, conversation))[-1]
    assert ungrounded["citations"] == []
    assert "[S1]" not in ungrounded["content"]

    # The model may generalize away the requested number. The user's requirements
    # still bind the real retriever's evidence and final saved assistant message.
    await run_turn(
        service,
        auth,
        conversation,
        knowledge_turn("bạo lực học đường", "Theo nguồn, mức phạt là 9000000 đồng [S1]."),
        retriever,
        "Mức phạt tiền khi học sinh đánh bạn là bao nhiêu?",
    )
    unsupported = (await assistant_rows(admin, conversation))[-1]
    assert unsupported["citations"] == []
    assert "9000000" not in unsupported["content"]
    assert "chưa có đủ thông tin" in unsupported["content"]

    # 3. Case context and an AI proposal: nothing is written before the bound approval.
    await propose_via_agent(service, auth, case.id, conversation)
    (proposal,) = await rows(
        admin, "SELECT * FROM app.agent_proposals WHERE target_case_id=:c", c=case.id
    )
    events = "SELECT id, provenance, description FROM app.case_events WHERE case_id=:c"
    assert proposal["status"] == "proposed"
    assert await rows(admin, events, c=case.id) == []
    paused, turn, checkpoint = await ask_to_save(service, auth, conversation, proposal["id"])
    assert await rows(admin, events, c=case.id) == []  # paused on approval, still nothing written
    await finish_resume(service, auth, paused, turn, checkpoint, approved=True)
    (event,) = await rows(admin, events, c=case.id)
    assert event["provenance"] == "user_confirmed"
    assert event["description"] == PROPOSE["description"]  # exactly what the user saw

    # 4. History restore for the owner; user B sees none of it.
    fresh = ConversationService(db_engine)
    recent = await fresh.recent_user_messages(auth, conversation)
    assert len(recent) == 3
    assert any("M\u1ee9c ph\u1ea1t ti\u1ec1n" in item for item in recent)
    # This journey now has five user turns. Ask for four previous messages to
    # prove the first still persists, while preserving the default window above.
    history = await fresh.recent_user_messages(auth, conversation, limit=4)
    assert any("nhắn tin dọa" in str(item) for item in history)
    with pytest.raises(NotFound):
        await fresh.get(other, conversation)
    with pytest.raises(ApiError) as hidden:
        await IncidentService(db_engine).get_case(other, case.id)
    assert hidden.value.status_code == 404  # another user's case does not exist for user B

    await service.delete(auth, conversation)


class ConfigErrorEmbedder:
    """A rejected key or request: the retriever must fail loudly, not degrade silently."""

    async def embed_query(self, text: str) -> list[float]:  # noqa: ARG002
        raise KnowledgeUnavailable("bad credentials", details={"reason": "embed_config"})


class HangingEmbedder:
    async def embed_query(self, text: str) -> list[float]:  # noqa: ARG002
        await asyncio.sleep(60)
        return []


def fast_failure_config() -> AppConfig:
    """A one-second knowledge budget keeps the failure cases quick."""
    return replace(CFG, agent=replace(CFG.agent, knowledge_tool_timeout_s=2.0))


@pytest.mark.parametrize("failure", ["embedder_config_error", "embedder_hang", "database_down"])
async def test_a_failing_retriever_ends_the_run_cleanly_without_a_citation(
    db_engine, identities, admin, published_corpus, failure
):
    """IT-05: the run finishes inside the budget, the tool reports failure, and nothing is cited."""
    auth, _, _, _, conversation = await world(db_engine, identities)
    # The service's config decides the per-turn knowledge budget, the runtime's config the tools:
    # give both the same short budget so a failing retriever is observable in about a second.
    service = ConversationService(db_engine, fast_failure_config())
    engines = []
    if failure == "database_down":
        engine = create_async_engine(
            "postgresql+asyncpg://moodprint_api:nope@127.0.0.1:1/postgres", hide_parameters=True
        )
        engines.append(engine)
        retriever = PgVectorKnowledgeRetriever(engine, HashingEmbedder(), CFG.knowledge)
    elif failure == "embedder_config_error":
        retriever = PgVectorKnowledgeRetriever(db_engine, ConfigErrorEmbedder(), CFG.knowledge)
    else:
        retriever = PgVectorKnowledgeRetriever(db_engine, HangingEmbedder(), CFG.knowledge)
    cfg = fast_failure_config()
    runtime = CompanionRuntime(
        cfg,
        build_registry(cfg),
        model=ScriptedModel(
            [
                ModelStep(
                    output=[
                        function_call(
                            "knowledge_search", {"query": "bị nhắn tin dọa"}, call_id="k1"
                        )
                    ],
                    usage=usage(),
                ),
                ModelStep(
                    output=[assistant_message("Mình chưa tra được nguồn [S1].")], usage=usage()
                ),
            ]
        ),
    )
    started = time.monotonic()
    try:
        turn = await run_turn(
            service, auth, conversation, runtime, retriever, "Có bạn nhắn tin dọa mình"
        )
    finally:
        for engine in engines:
            await engine.dispose()
    assert time.monotonic() - started < cfg.agent.knowledge_tool_timeout_s + 3.0, (
        "the run must not hang"
    )
    (run,) = await rows(
        admin, "SELECT status, tool_call_count FROM app.agent_runs WHERE id=:r", r=turn.run_id
    )
    assert run["status"] == "completed" and run["tool_call_count"] == 1
    (answer,) = await assistant_rows(admin, conversation)
    assert answer["citations"] == []
    assert "[S1]" not in answer["content"]
    await service.delete(auth, conversation)
