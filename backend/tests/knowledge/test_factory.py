from dataclasses import replace

import pytest
from moodprint_shared.config import AppConfig
from moodprint_shared.contracts.knowledge import KnowledgeQuery, RetrievalScope


async def test_backend_factory_keeps_fixture_search_offline(settings):
    from app.modules.knowledge.factory import build_knowledge_retriever

    result = await build_knowledge_retriever(None, settings, AppConfig()).search(
        KnowledgeQuery(text="friends"),
        scope=RetrievalScope(request_id="backend-factory"),
        timeout_s=1,
    )
    assert result.corpus_version == "synthetic-fixture-v1"


def test_backend_factory_rejects_unavailable_retriever(settings):
    from app.modules.knowledge.factory import build_knowledge_retriever

    cfg = AppConfig()
    cfg = replace(cfg, knowledge=replace(cfg.knowledge, retriever="pgvector"))
    with pytest.raises(ValueError, match="retriever not available before Phase 2"):
        build_knowledge_retriever(None, settings, cfg)
