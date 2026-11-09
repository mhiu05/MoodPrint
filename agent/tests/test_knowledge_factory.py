from dataclasses import replace

import pytest
from moodprint_agent.knowledge import create_retriever
from moodprint_shared.config import AppConfig
from moodprint_shared.contracts.knowledge import KnowledgeQuery, RetrievalScope


def _fixture_config() -> AppConfig:
    base = AppConfig()
    return replace(base, knowledge=replace(base.knowledge, retriever="fixture"))


async def test_foundation_factory_returns_synthetic_knowledge_fixture_when_selected() -> None:
    result = await create_retriever(_fixture_config()).search(
        KnowledgeQuery(text="bạn bè"),
        scope=RetrievalScope(request_id="factory-test"),
        timeout_s=1,
    )
    assert result.corpus_version == "synthetic-fixture-v1"


def test_the_agent_package_never_hands_out_the_fixture_for_the_product_default() -> None:
    """The product default is the real retriever, built by the backend. This seam only knows the fixture."""
    assert AppConfig().knowledge.retriever == "pgvector"
    with pytest.raises(ValueError, match="unsupported knowledge retriever"):
        create_retriever(AppConfig())
