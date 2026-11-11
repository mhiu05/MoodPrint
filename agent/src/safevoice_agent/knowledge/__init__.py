"""Foundation fixture seam; Phase 2 owns the retrieval implementation."""

from safevoice_shared.config import AppConfig
from safevoice_shared.contracts.knowledge import KnowledgeRetriever
from safevoice_shared.testing.knowledge_fixture import FixtureKnowledgeRetriever


def create_retriever(cfg: AppConfig) -> KnowledgeRetriever:
    if cfg.knowledge.retriever != "fixture":
        raise ValueError("unsupported knowledge retriever")
    return FixtureKnowledgeRetriever()
