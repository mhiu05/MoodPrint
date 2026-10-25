"""Fair, diverse ordering of eligible candidates (05 section 7). Pure and deterministic.

rank_score = score + cold-start boost - load penalty; then a maximal-marginal-relevance
pass (lambda 0.85, similarity = interest component between candidates) and a daily
viewer-specific tie-break instead of UUID order, so the same people are not always first.
"""

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID

from app.modules.matching import scoring_v2

COLD_START_BOOST = 0.03
COLD_START_DAYS = 7
LOAD_PENALTY = 0.05
LOAD_FREE_PENDING = 2
MMR_LAMBDA = 0.85
# Diversity re-ranking only looks this many times deeper than the requested list.
MMR_DEPTH = 5


@dataclass(frozen=True)
class Candidate:
    peer_id: UUID
    score: float
    payload: Mapping[str, Any]
    first_published_at: datetime | None = None
    pending_incoming: int = 0


def tiebreak(viewer_id: UUID, peer_id: UUID, local_date: date) -> str:
    return hashlib.sha256(f"{viewer_id}|{peer_id}|{local_date.isoformat()}".encode()).hexdigest()


def rank_score(candidate: Candidate, now: datetime) -> float:
    boost = (
        COLD_START_BOOST
        if candidate.first_published_at
        and candidate.first_published_at > now - timedelta(days=COLD_START_DAYS)
        else 0.0
    )
    penalty = LOAD_PENALTY * max(0, candidate.pending_incoming - LOAD_FREE_PENDING)
    return candidate.score + boost - penalty


def rank(
    viewer_id: UUID,
    candidates: Sequence[Candidate],
    local_date: date,
    now: datetime,
    limit: int,
) -> list[UUID]:
    """Return up to `limit` peer ids in display order."""
    base = {item.peer_id: rank_score(item, now) for item in candidates}
    order = {item.peer_id: tiebreak(viewer_id, item.peer_id, local_date) for item in candidates}
    pool = sorted(candidates, key=lambda item: (-base[item.peer_id], order[item.peer_id]))
    pool = pool[: limit * MMR_DEPTH]
    # Greatest similarity to anything already chosen, updated as each pick is made.
    redundancy = {item.peer_id: 0.0 for item in pool}
    # max() keeps the first maximum; inverting the hash makes lower hashes win ties.
    tie = {item.peer_id: -int(order[item.peer_id], 16) for item in pool}
    chosen: list[Candidate] = []
    while pool and len(chosen) < limit:
        best = max(
            pool,
            key=lambda item: (
                MMR_LAMBDA * base[item.peer_id] - (1 - MMR_LAMBDA) * redundancy[item.peer_id],
                tie[item.peer_id],
            ),
        )
        chosen.append(best)
        pool.remove(best)
        for item in pool:
            redundancy[item.peer_id] = max(
                redundancy[item.peer_id],
                scoring_v2.interest_component(best.payload, item.payload),
            )
    return [item.peer_id for item in chosen]
