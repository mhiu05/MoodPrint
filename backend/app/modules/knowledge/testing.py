"""Explicit hashing retriever for scripted E2E. Production never calls this."""

from moodprint_agent.knowledge.embedder import HashingEmbedder
from moodprint_agent.knowledge.retriever import PgVectorKnowledgeRetriever
from moodprint_shared.config import AppConfig
from moodprint_shared.contracts.knowledge import KnowledgeRetriever
from sqlalchemy.ext.asyncio import AsyncEngine


def build_e2e_retriever(engine: AsyncEngine, cfg: AppConfig) -> KnowledgeRetriever:
    return PgVectorKnowledgeRetriever(engine, HashingEmbedder(), cfg.knowledge)
