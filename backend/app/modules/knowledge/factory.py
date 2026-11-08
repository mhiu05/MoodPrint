"""Construct retrieval adapters where backend settings and connections are available."""

from moodprint_shared.config import AppConfig
from moodprint_shared.contracts.knowledge import KnowledgeRetriever
from moodprint_shared.env import EnvSettings
from moodprint_shared.testing.knowledge_fixture import FixtureKnowledgeRetriever
from sqlalchemy.ext.asyncio import AsyncEngine


def build_knowledge_retriever(
    engine: AsyncEngine, settings: EnvSettings, cfg: AppConfig
) -> KnowledgeRetriever:
    """Phase 2 extends this seam with the configured database and embedding client."""
    if cfg.knowledge.retriever != "fixture":
        raise ValueError("retriever not available before Phase 2")
    return FixtureKnowledgeRetriever()
