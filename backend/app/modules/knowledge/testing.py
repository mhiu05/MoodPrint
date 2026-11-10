"""Explicit hashing retriever for scripted E2E. Production never calls this."""

from dataclasses import replace

from moodprint_agent.knowledge.embedder import HashingEmbedder
from moodprint_agent.knowledge.retriever import PgVectorKnowledgeRetriever
from moodprint_shared.config import AppConfig
from moodprint_shared.contracts.knowledge import KnowledgeRetriever
from sqlalchemy.ext.asyncio import AsyncEngine

# The product gate (``min_vector_score`` 0.425) was calibrated on Voyage vectors. The deterministic
# HashingEmbedder scores related Vietnamese text much lower (about 0.27 to 0.39 normalised against 0.22
# for the closest unrelated query on the synthetic corpus), so scripted E2E lowers only the vector gate.
# This is a test-fixture calibration with no quality claim; nothing in production reads it.
HASHING_MIN_VECTOR_SCORE = 0.25


def build_e2e_retriever(engine: AsyncEngine, cfg: AppConfig) -> KnowledgeRetriever:
    knowledge = replace(cfg.knowledge, min_vector_score=HASHING_MIN_VECTOR_SCORE)
    return PgVectorKnowledgeRetriever(engine, HashingEmbedder(), knowledge)
