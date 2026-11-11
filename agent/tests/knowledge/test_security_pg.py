"""The real retriever against Postgres: hostile queries do not error and the query is never logged."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from pathlib import Path

import pytest
from safevoice_agent.knowledge.embedder import HashingEmbedder
from safevoice_agent.knowledge.ingest.cli import main
from safevoice_agent.knowledge.retriever import PgVectorKnowledgeRetriever
from safevoice_shared.config import KnowledgeConfig
from safevoice_shared.contracts.knowledge import KnowledgeFilters, KnowledgeQuery, RetrievalScope
from sqlalchemy.ext.asyncio import create_async_engine

from .fuzz_cases import fuzz_corpus
from .kb_env import api_database_url, load_test_env

pytestmark = pytest.mark.integration


def _prepare() -> str:
    load_test_env()
    assert main(["seed-synthetic", "--target", "test-env"]) == 0
    return api_database_url()


async def _run(database: str, queries: list[str]) -> list[str]:
    engine = create_async_engine(database, hide_parameters=True)
    try:
        retriever = PgVectorKnowledgeRetriever(engine, HashingEmbedder(), KnowledgeConfig())
        statuses: list[str] = []
        for index, raw in enumerate(queries):
            result = await retriever.search(
                KnowledgeQuery(text=raw[:2000] or " ", filters=KnowledgeFilters(languages=["vi"])),
                scope=RetrievalScope(request_id=f"fuzz-{index}"),
                timeout_s=5,
            )
            statuses.append(result.status)
        return statuses
    finally:
        await engine.dispose()


def test_500_hostile_queries_never_raise_through_the_authenticated_role() -> None:
    database = _prepare()
    statuses = asyncio.run(_run(database, fuzz_corpus()))
    assert len(statuses) == 500
    assert set(statuses) <= {"ok", "no_results"}


def test_the_query_text_never_reaches_any_log(caplog: pytest.LogCaptureFixture) -> None:
    database = _prepare()
    canary = f"ZZ-CANARY-{uuid.uuid4()}"
    with caplog.at_level(logging.DEBUG):
        asyncio.run(_run(database, [canary, f"bị nhắn tin dọa {canary}"]))
    assert canary not in caplog.text
    assert canary.lower() not in caplog.text.lower()


def test_the_synthetic_fixture_still_holds_a_prompt_injection_trap_as_plain_data() -> None:
    payload = json.loads(
        Path("agent/ingestion/synthetic/contract_corpus.json").read_text(encoding="utf-8")
    )
    traps = [d for d in payload["documents"] if "trap" in d["document_id"]]
    assert traps, "the integrator needs the injection trap document"
