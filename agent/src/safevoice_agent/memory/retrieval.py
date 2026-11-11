"""Pure lexical ranking shared by database retrieval adapters."""

from safevoice_shared.config import MemoryConfig


def lexical_score(
    *,
    ts_rank: float,
    similarity: float,
    recency_decay: float,
    cfg: MemoryConfig,
) -> float:
    return (
        cfg.lexical_weight * max(0.0, ts_rank)
        + cfg.similarity_weight * max(0.0, min(1.0, similarity))
        + cfg.recency_weight * max(0.0, min(1.0, recency_decay))
    )
