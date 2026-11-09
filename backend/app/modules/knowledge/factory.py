"""Construct retrieval adapters where backend settings and connections are available.

The choice is explicit. The product default (``KnowledgeConfig.retriever``) is the real pgvector
retriever and it fails closed without a Voyage key. The fixture returns synthetic results: it exists
for deterministic tests and the demo, must be selected on purpose, is announced in the log, and is
refused outright when ``APP_ENV=production``. Nothing falls back from one to the other.
"""

import logging

from moodprint_shared.config import AppConfig
from moodprint_shared.contracts.knowledge import KnowledgeRetriever
from moodprint_shared.env import EnvSettings
from moodprint_shared.testing.knowledge_fixture import FixtureKnowledgeRetriever
from sqlalchemy.ext.asyncio import AsyncEngine

log = logging.getLogger("moodprint.knowledge.factory")


def build_knowledge_retriever(
    engine: AsyncEngine, settings: EnvSettings, cfg: AppConfig
) -> KnowledgeRetriever:
    if cfg.knowledge.retriever == "fixture":
        if settings.app_env == "production":
            raise ValueError(
                "The fixture knowledge retriever is not allowed when APP_ENV=production"
            )
        log.warning("knowledge retriever is the FIXTURE: synthetic results, not for real users")
        return FixtureKnowledgeRetriever()
    if cfg.knowledge.retriever == "pgvector":
        if settings.voyage_api_key is None:
            raise ValueError("Voyage API key is required for the pgvector retriever")
        from moodprint_agent.knowledge.embedder import VoyageEmbedder
        from moodprint_agent.knowledge.retriever import PgVectorKnowledgeRetriever

        return PgVectorKnowledgeRetriever(
            engine,
            VoyageEmbedder(settings.voyage_api_key.get_secret_value(), cfg.knowledge),
            cfg.knowledge,
        )
    raise ValueError(f"Unknown knowledge retriever: {cfg.knowledge.retriever!r}")
