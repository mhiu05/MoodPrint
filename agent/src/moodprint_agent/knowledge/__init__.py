"""Foundation fixture seam; Phase 2 owns the retrieval implementation."""

from moodprint_shared.config import AppConfig
from moodprint_shared.contracts.knowledge import KnowledgeRetriever
from moodprint_shared.testing.knowledge_fixture import FixtureKnowledgeRetriever


def create_retriever(cfg: AppConfig) -> KnowledgeRetriever:
    if cfg.knowledge.retriever != "fixture":
        raise ValueError("unsupported knowledge retriever")
    return FixtureKnowledgeRetriever()
