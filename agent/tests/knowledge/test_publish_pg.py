"""Publish, rollback, and citation checks against the isolated kb database."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from moodprint_agent.knowledge.embedder import HashingEmbedder
from moodprint_agent.knowledge.ingest.cli import main
from moodprint_agent.knowledge.ingest.runtime import (
    engine_for,
    rollback_version,
    seed_corpus,
    store_records,
)
from moodprint_agent.knowledge.retriever import PgVectorKnowledgeRetriever
from moodprint_shared.config import KnowledgeConfig
from moodprint_shared.contracts.knowledge import KnowledgeFilters, KnowledgeQuery, RetrievalScope

from .kb_env import api_database_url, load_test_env

pytestmark = pytest.mark.integration

SYNTHETIC = Path("agent/ingestion/synthetic/contract_corpus.json")


def _load_kb_env() -> None:
    load_test_env()


def test_seed_publish_rollback_and_citation_round_trip() -> None:
    _load_kb_env()
    payload = json.loads(SYNTHETIC.read_text(encoding="utf-8"))
    assert main(["seed-synthetic", "--target", "test-env"]) == 0
    assert main(["seed-synthetic", "--target", "test-env"]) == 0
    assert main(["status", "--target", "test-env"]) == 0
    assert main(["verify-citations", "--target", "test-env", "--version", payload["version"]]) == 0
    assert main(["publish", "--target", "test-env", "--version", payload["version"]]) == 0
    second = json.loads(json.dumps(payload))
    second["version"] = "kb-20261109-02"
    import asyncio

    asyncio.run(seed_corpus("test-env", second, "b" * 64))
    assert main(["publish", "--target", "test-env", "--version", second["version"]]) == 0
    assert main(["rollback", "--target", "test-env", "--to", payload["version"]]) == 0
    assert main(["rollback", "--target", "test-env", "--to", second["version"]]) == 0
    assert main(["rollback", "--target", "test-env", "--to", "kb-20261109-99"]) == 1
    assert main(["rollback", "--target", "test-env", "--to", second["version"]]) == 1


def test_published_corpus_rejects_a_different_manifest() -> None:
    _load_kb_env()
    assert main(["seed-synthetic", "--target", "test-env"]) == 0
    payload = json.loads(SYNTHETIC.read_text(encoding="utf-8"))

    async def once() -> None:
        engine = engine_for("test-env")
        try:
            with pytest.raises(ValueError):
                await store_records(
                    engine,
                    version=str(payload["version"]),
                    manifest_sha256="c" * 64,
                    embedding_model="hashing",
                    sources=payload["sources"],
                    documents=payload["documents"],
                    chunks=payload["chunks"],
                    vectors=[[0.0] * 1024 for _ in payload["chunks"]],
                )
        finally:
            await engine.dispose()

    import asyncio

    asyncio.run(once())


def test_authenticated_role_can_search_the_published_corpus() -> None:
    _load_kb_env()
    assert main(["seed-synthetic", "--target", "test-env"]) == 0  # do not depend on test order
    from sqlalchemy.ext.asyncio import create_async_engine

    database = api_database_url()

    async def once() -> None:
        engine = create_async_engine(database, hide_parameters=True)
        try:
            retriever = PgVectorKnowledgeRetriever(engine, HashingEmbedder(), KnowledgeConfig())
            result = await retriever.search(
                KnowledgeQuery(
                    text="bị nhắn tin dọa trong nhóm lớp",
                    filters=KnowledgeFilters(languages=["vi"]),
                ),
                scope=RetrievalScope(request_id="api-role"),
                timeout_s=5,
            )
            assert result.status == "ok"
            assert result.chunks[0].citation.document_id == "syn-threat-messages"
        finally:
            await engine.dispose()

    import asyncio

    asyncio.run(once())


def test_empty_filters_do_not_break_search() -> None:
    _load_kb_env()
    assert main(["seed-synthetic", "--target", "test-env"]) == 0
    pinned = str(json.loads(SYNTHETIC.read_text(encoding="utf-8"))["version"])

    async def once() -> None:
        engine = engine_for("test-env")
        try:
            retriever = PgVectorKnowledgeRetriever(
                engine, HashingEmbedder(), KnowledgeConfig(), read_role=None
            )
            result = await retriever.search(
                KnowledgeQuery(text="bị nhắn tin", filters=KnowledgeFilters(languages=["vi"])),
                scope=RetrievalScope(request_id="empty-filters", corpus_version=pinned),
                timeout_s=5,
            )
            assert result.status in {"ok", "no_results"}
            assert result.corpus_version == pinned
        finally:
            await engine.dispose()

    import asyncio

    asyncio.run(once())


def test_rollback_of_the_current_published_version_fails() -> None:
    _load_kb_env()
    assert main(["seed-synthetic", "--target", "test-env"]) == 0
    payload = json.loads(SYNTHETIC.read_text(encoding="utf-8"))

    async def once() -> None:
        engine = engine_for("test-env")
        try:
            with pytest.raises(ValueError):
                await rollback_version(engine, str(payload["version"]))
        finally:
            await engine.dispose()

    import asyncio

    asyncio.run(once())
