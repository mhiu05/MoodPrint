"""The retriever choice is explicit: the product default is the real one, fixture is opt-in and never production."""

import logging
from dataclasses import replace

import pytest
from safevoice_shared.config import AppConfig
from safevoice_shared.contracts.knowledge import KnowledgeQuery, RetrievalScope


def _cfg(retriever: str) -> AppConfig:
    cfg = AppConfig()
    return replace(cfg, knowledge=replace(cfg.knowledge, retriever=retriever))


async def test_explicit_fixture_mode_keeps_search_offline(settings, caplog):
    from app.modules.knowledge.factory import build_knowledge_retriever

    with caplog.at_level(logging.WARNING):
        retriever = build_knowledge_retriever(None, settings, _cfg("fixture"))
    result = await retriever.search(
        KnowledgeQuery(text="friends"),
        scope=RetrievalScope(request_id="backend-factory"),
        timeout_s=1,
    )
    assert result.corpus_version == "synthetic-fixture-v1"
    assert "fixture" in caplog.text.lower()  # selecting synthetic results is never silent


def test_the_product_default_is_the_real_retriever_and_fails_closed_without_a_key(settings):
    from app.modules.knowledge.factory import build_knowledge_retriever

    assert AppConfig().knowledge.retriever == "pgvector"
    assert settings.voyage_api_key is None
    with pytest.raises(ValueError, match="Voyage API key is required"):
        build_knowledge_retriever(None, settings, AppConfig())


def test_the_fixture_retriever_is_refused_in_production(settings):
    from app.modules.knowledge.factory import build_knowledge_retriever

    production = settings.model_copy(update={"app_env": "production"})
    with pytest.raises(ValueError, match="not allowed"):
        build_knowledge_retriever(None, production, _cfg("fixture"))


def test_unknown_retriever_names_are_rejected(settings):
    from app.modules.knowledge.factory import build_knowledge_retriever

    with pytest.raises(ValueError):
        build_knowledge_retriever(None, settings, _cfg("whatever"))


def test_backend_factory_rejects_pgvector_without_a_key(settings):
    from app.modules.knowledge.factory import build_knowledge_retriever

    with pytest.raises(ValueError, match="Voyage API key is required"):
        build_knowledge_retriever(None, settings, _cfg("pgvector"))
