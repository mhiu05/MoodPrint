"""Scorer rules-v2 (pure): formula, symmetry, renormalization and truthful eligibility."""

import random

import pytest

from app.modules.matching import scoring_v2 as v2
from app.modules.profiles import taxonomy

A = {
    "interests": ["reading", "english", "coffee"],
    "values": ["curiosity", "kindness"],
    "style": "balanced",
    "goal": "study-buddy",
    "languages": ["vi"],
    "activities": ["focus", "coop_quiz"],
    "availability": ["weekday_evening"],
}
B = {
    "interests": ["languages", "reading", "movies", "cooking"],
    "values": ["curiosity", "humor"],
    "style": "listening",
    "goal": "language-practice",
    "languages": ["vi", "en"],
    "activities": ["focus"],
    "availability": [],
}


def random_profile(rng: random.Random) -> dict:
    def pick(options, low, high):
        return rng.sample(sorted(options), rng.randint(low, high))

    return {
        "interests": pick(taxonomy.INTERESTS, 3, 10),
        "values": pick(taxonomy.VALUES, 2, 4),
        "style": rng.choice(sorted(taxonomy.STYLES)),
        "goal": rng.choice(sorted(taxonomy.GOALS)),
        "languages": pick(taxonomy.LANGUAGES, 1, 2),
        "activities": pick(taxonomy.ACTIVITIES, 0, 4),
        "availability": pick(taxonomy.AVAILABILITY, 0, 6),
        "strict_goal": rng.random() < 0.2,
    }


def test_worked_example_matches_the_design():
    result = v2.score(A, B)
    assert result.score == pytest.approx(0.690, abs=0.001)
    assert result.components["I"] == pytest.approx(4.6 / 7)
    assert result.components == pytest.approx(
        {"I": 4.6 / 7, "V": 0.5, "G": 0.7, "S": 0.75, "P": 1.0}
    )
    assert "T" not in result.components
    assert result.coverage == pytest.approx(0.90)
    assert result.shared == {
        "interests": ["reading"],
        "values": ["curiosity"],
        "activities": ["focus"],
        "availability": [],
    }
    assert v2.eligible(result) and v2.label(result) == "many"


def test_symmetric_bounded_and_deterministic_over_random_pairs():
    rng = random.Random(20261025)
    for _ in range(1000):
        a, b = random_profile(rng), random_profile(rng)
        ab, ba = v2.score(a, b), v2.score(b, a)
        assert ab.score == pytest.approx(ba.score, abs=1e-12)
        assert ab.components == pytest.approx(ba.components)
        assert ab.shared == ba.shared
        assert 0.0 <= ab.score <= 1.0
        assert 0.75 <= ab.coverage <= 1.0
        assert v2.score(a, b) == ab
        for facet, items in ab.shared.items():
            assert set(items) <= set(a.get(facet) or []) & set(b.get(facet) or [])


def test_missing_optional_facets_are_dropped_not_imputed():
    core = {key: A[key] for key in ("interests", "values", "style", "goal", "languages")}
    result = v2.score(core, core)
    assert set(result.components) == {"I", "V", "G", "S"}
    assert result.coverage == pytest.approx(0.75)
    assert result.score == pytest.approx(1.0 * (0.9 + 0.1 * 0.75))
    full = v2.score(A, A)
    assert full.score == pytest.approx(1.0) and full.coverage == pytest.approx(1.0)


def test_eligibility_requires_a_threshold_and_an_exact_shared_item():
    a = {**A, "interests": ["english", "running", "chess"], "values": ["humor", "calm"]}
    b = {
        **A,
        "interests": ["languages", "walking", "boardgames"],
        "values": ["growth", "reliability"],
        "activities": ["icebreaker"],
    }
    result = v2.score(a, b)
    assert result.score >= 0.30
    assert result.shared["interests"] == result.shared["values"] == []
    assert result.shared["activities"] == []
    assert not v2.eligible(result)
    low = v2.score(
        {**a, "goal": "friendship", "style": "listening", "activities": []},
        {
            **b,
            "goal": "language-practice",
            "style": "direct",
            "interests": ["football", "yoga", "plants"],
            "availability": ["weekend_morning"],
        },
    )
    assert low.score < 0.30 and not v2.eligible(low)


def test_labels_never_expose_numbers():
    assert v2.label(v2.Breakdown(0.6, {}, 1.0, {})) == "many"
    assert v2.label(v2.Breakdown(0.59, {}, 1.0, {})) == "some"


def test_strict_goal_is_a_reciprocal_hard_filter():
    assert v2.goal_allowed(A, B)
    assert not v2.goal_allowed({**A, "strict_goal": True}, B)
    assert not v2.goal_allowed(A, {**B, "strict_goal": True})
    assert v2.goal_allowed({**A, "strict_goal": True}, {**B, "goal": "study-buddy"})
