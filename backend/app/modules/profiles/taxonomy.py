"""Versioned product taxonomy (v2): the single source of truth for public tags and labels.

No fixtures, personal data or model inference. `taxonomy_v2.json` also holds the curated
similarity data used by the matching scorer; it is validated at import so an invalid
file fails startup instead of silently mis-ranking people.
"""

import json
from pathlib import Path

from app.contracts import DTO

_DATA = json.loads(Path(__file__).with_name("taxonomy_v2.json").read_text(encoding="utf-8"))


class TaxonomyDTO(DTO):
    version: str = "v2"
    interests: dict[str, str]
    values: dict[str, str]
    styles: dict[str, str]
    goals: dict[str, str]
    languages: dict[str, str]
    activities: dict[str, str]
    availability: dict[str, str]
    categories: dict[str, list[str]]
    category_labels: dict[str, str]
    # [minimum, maximum] selections per facet.
    limits: dict[str, list[int]]


INTERESTS: dict[str, str] = _DATA["interests"]
VALUES: dict[str, str] = _DATA["values"]
STYLES: dict[str, str] = _DATA["styles"]
GOALS: dict[str, str] = _DATA["goals"]
LANGUAGES: dict[str, str] = _DATA["languages"]
ACTIVITIES: dict[str, str] = _DATA["activities"]
AVAILABILITY: dict[str, str] = _DATA["availability"]
ACTIVITY_REASONS: dict[str, str] = _DATA["activityReasons"]
LIMITS: dict[str, tuple[int, int]] = {
    key: (low, high) for key, (low, high) in _DATA["limits"].items()
}
CATEGORY_OF = {tag: name for name, tags in _DATA["categories"].items() for tag in tags}

_SAME_CATEGORY: float = _DATA["interestSimilarity"]["sameCategory"]
_INTEREST_OVERRIDES = {
    frozenset((a, b)): value for a, b, value in _DATA["interestSimilarity"]["overrides"]
}
_GOAL_DEFAULT: float = _DATA["goalCompatibility"]["default"]
_GOAL_PAIRS = {frozenset((a, b)): value for a, b, value in _DATA["goalCompatibility"]["pairs"]}
_STYLE_BALANCED: float = _DATA["styleCompatibility"]["withBalanced"]
_STYLE_PAIRS = {frozenset((a, b)): value for a, b, value in _DATA["styleCompatibility"]["pairs"]}


def _similarity(a: str, b: str) -> float:
    if a == b:
        return 1.0
    override = _INTEREST_OVERRIDES.get(frozenset((a, b)))
    if override is not None:
        return override
    return _SAME_CATEGORY if CATEGORY_OF[a] == CATEGORY_OF[b] else 0.0


# Precomputed once: scoring runs this lookup for every tag pair of every candidate.
SIMILARITY: dict[str, dict[str, float]] = {
    a: {b: _similarity(a, b) for b in INTERESTS} for a in INTERESTS
}


def interest_similarity(a: str, b: str) -> float:
    """Curated tag similarity: 1 for the same tag, overrides, 0.5 within a category, else 0."""
    return SIMILARITY[a][b]  # KeyError for unknown tags


def goal_compat(a: str, b: str) -> float:
    if a not in GOALS or b not in GOALS:
        raise KeyError("Unknown goal")
    return 1.0 if a == b else _GOAL_PAIRS.get(frozenset((a, b)), _GOAL_DEFAULT)


def style_compat(a: str, b: str) -> float:
    if a not in STYLES or b not in STYLES:
        raise KeyError("Unknown style")
    if a == b:
        return 1.0
    if "balanced" in (a, b):
        return _STYLE_BALANCED
    return _STYLE_PAIRS[frozenset((a, b))]


def _validate() -> None:
    members = [tag for tags in _DATA["categories"].values() for tag in tags]
    if sorted(members) != sorted(INTERESTS) or set(_DATA["categoryLabels"]) != set(
        _DATA["categories"]
    ):
        raise ValueError("Every interest must belong to exactly one labelled category")
    for pairs, known in (
        (_INTEREST_OVERRIDES, INTERESTS),
        (_GOAL_PAIRS, GOALS),
        (_STYLE_PAIRS, STYLES),
    ):
        for key, value in pairs.items():
            if len(key) != 2 or not key <= set(known) or not 0.0 <= value <= 1.0:
                raise ValueError("Similarity entries need two known keys and a value in [0, 1]")
    if set(ACTIVITY_REASONS) != set(ACTIVITIES):
        raise ValueError("Every activity needs a reason phrase")
    facets = {"interests", "values", "languages", "activities", "availability"}
    if set(LIMITS) != facets or any(not 0 <= low <= high for low, high in LIMITS.values()):
        raise ValueError("Selection limits must cover every multi-select facet")
    for a in STYLES:
        for b in STYLES:
            style_compat(a, b)


_validate()

TAXONOMY = TaxonomyDTO(
    version=_DATA["version"],
    interests=INTERESTS,
    values=VALUES,
    styles=STYLES,
    goals=GOALS,
    languages=LANGUAGES,
    activities=ACTIVITIES,
    availability=AVAILABILITY,
    categories=_DATA["categories"],
    category_labels=_DATA["categoryLabels"],
    limits={key: list(value) for key, value in LIMITS.items()},
)
