"""T-MATCH-04: daily tie-break, load penalty, cold-start boost and diversity re-rank."""

from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

from app.modules.matching.ranking import Candidate, rank

NOW = datetime(2026, 10, 25, 9, tzinfo=UTC)
DAY = date(2026, 10, 25)
VIEWER = UUID("00000000-0000-4000-8000-000000000001")
BASE = {
    "interests": ["reading", "music", "walking"],
    "values": ["respect", "kindness"],
    "style": "balanced",
    "goal": "friendship",
    "languages": ["vi"],
}


def peers(count: int, score: float = 0.6, **extra) -> list[Candidate]:
    return [
        Candidate(UUID(f"00000000-0000-4000-8000-{index:012d}"), score, BASE, **extra)
        for index in range(10, 10 + count)
    ]


def test_same_day_is_stable_and_days_rotate_equal_scores():
    pool = peers(8)
    first = rank(VIEWER, pool, DAY, NOW, 8)
    assert first == rank(VIEWER, list(reversed(pool)), DAY, NOW, 8)
    later = [rank(VIEWER, pool, DAY + timedelta(days=n), NOW, 8) for n in range(1, 4)]
    assert any(order != first for order in later)
    assert all(sorted(order) == sorted(first) for order in later)
    assert rank(uuid4(), pool, DAY, NOW, 8) != first or len(pool) < 2


def test_higher_scores_come_first_without_ties():
    low, high = peers(1, 0.4)[0], Candidate(uuid4(), 0.9, BASE)
    assert rank(VIEWER, [low, high], DAY, NOW, 2) == [high.peer_id, low.peer_id]


def test_load_penalty_demotes_a_flooded_profile():
    busy = Candidate(uuid4(), 0.70, BASE, pending_incoming=5)  # 0.70 - 0.15
    calm = Candidate(uuid4(), 0.60, BASE, pending_incoming=2)  # no penalty up to 2
    assert rank(VIEWER, [busy, calm], DAY, NOW, 2) == [calm.peer_id, busy.peer_id]


def test_new_profiles_get_a_small_boost_for_seven_days_only():
    old = Candidate(uuid4(), 0.62, BASE, first_published_at=NOW - timedelta(days=30))
    new = Candidate(uuid4(), 0.60, BASE, first_published_at=NOW - timedelta(days=2))
    expired = Candidate(uuid4(), 0.60, BASE, first_published_at=NOW - timedelta(days=8))
    assert rank(VIEWER, [old, new], DAY, NOW, 2) == [new.peer_id, old.peer_id]
    assert rank(VIEWER, [old, expired], DAY, NOW, 2) == [old.peer_id, expired.peer_id]


def test_diversity_rerank_avoids_three_near_identical_profiles_in_the_top_three():
    clones = [Candidate(uuid4(), 0.70, BASE) for _ in range(3)]
    other = Candidate(
        uuid4(),
        0.66,
        {**BASE, "interests": ["chess", "football", "travel"], "values": ["humor", "calm"]},
    )
    top3 = rank(VIEWER, [*clones, other], DAY, NOW, 3)
    assert other.peer_id in top3


def test_limit_and_empty_pool():
    assert rank(VIEWER, [], DAY, NOW, 5) == []
    assert len(rank(VIEWER, peers(12), DAY, NOW, 5)) == 5
