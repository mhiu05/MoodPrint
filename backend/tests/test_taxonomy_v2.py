"""Taxonomy v2 is the single source of truth for tags, labels and similarity data."""

import itertools
import json
from pathlib import Path

import httpx
import pytest

from app.modules.matching import scoring
from app.modules.profiles import taxonomy

SOURCE = Path(taxonomy.__file__).with_name("taxonomy_v2.json")


def test_json_loads_and_keeps_every_v1_key():
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    assert data["version"] == "v2"
    assert set(scoring._INTERESTS) <= set(taxonomy.INTERESTS)
    assert set(scoring._VALUES) <= set(taxonomy.VALUES)
    assert scoring._STYLES <= set(taxonomy.STYLES)
    assert scoring._GOALS <= set(taxonomy.GOALS)
    assert scoring._LANGUAGES <= set(taxonomy.LANGUAGES)
    assert len(taxonomy.INTERESTS) == 30 and len(taxonomy.VALUES) == 8
    assert set(taxonomy.GOALS) == {
        "friendship",
        "shared-interests",
        "study-buddy",
        "language-practice",
    }
    assert set(taxonomy.ACTIVITIES) == {"icebreaker", "coop_quiz", "focus", "chat_only"}
    assert len(taxonomy.AVAILABILITY) == 6


def test_every_interest_is_in_exactly_one_category():
    members = [tag for tags in taxonomy.TAXONOMY.categories.values() for tag in tags]
    assert sorted(members) == sorted(taxonomy.INTERESTS)
    assert len(taxonomy.TAXONOMY.categories) == 6


def test_interest_similarity_is_symmetric_bounded_and_one_on_the_diagonal():
    for a, b in itertools.product(taxonomy.INTERESTS, repeat=2):
        value = taxonomy.interest_similarity(a, b)
        assert 0.0 <= value <= 1.0
        assert value == taxonomy.interest_similarity(b, a)
        if a == b:
            assert value == 1.0
    assert taxonomy.interest_similarity("english", "languages") == 0.8
    assert taxonomy.interest_similarity("coffee", "cooking") == 0.5  # same category
    assert taxonomy.interest_similarity("movies", "reading") == 0.0


@pytest.mark.parametrize(
    ("function", "keys"),
    [
        (taxonomy.goal_compat, "GOALS"),
        (taxonomy.style_compat, "STYLES"),
    ],
)
def test_goal_and_style_matrices_are_symmetric_and_complete(function, keys):
    options = getattr(taxonomy, keys)
    for a, b in itertools.product(options, repeat=2):
        value = function(a, b)
        assert 0.0 < value <= 1.0
        assert value == function(b, a)
        assert (value == 1.0) == (a == b)
    assert taxonomy.goal_compat("study-buddy", "language-practice") == 0.7
    assert taxonomy.goal_compat("friendship", "language-practice") == 0.4
    assert taxonomy.style_compat("balanced", "direct") == 0.75
    assert taxonomy.style_compat("listening", "direct") == 0.5


def test_unknown_keys_fail_closed():
    with pytest.raises(KeyError):
        taxonomy.goal_compat("dating", "friendship")


async def test_taxonomy_endpoint_serves_v2_facets():
    from app.main import create_app

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        body = (await client.get("/api/v1/taxonomy")).json()
    assert body["version"] == "v2"
    assert body["activities"]["focus"] == "Cùng tập trung"
    assert body["availability"]["weekend_evening"] == "Tối cuối tuần"
    assert set(body["categories"]) == {
        "learning",
        "creative",
        "active",
        "mind",
        "media",
        "lifestyle",
    }
    assert body["limits"]["interests"] == [3, 10]
    assert "interestSimilarity" not in body  # scoring internals stay server-side
