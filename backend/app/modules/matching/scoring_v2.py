"""Scorer `rules-v2`: deterministic, symmetric and explainable taxonomy similarity (DR-04).

Inputs are two *published* profile payloads only. The score is an internal ranking
signal; users only ever see a qualitative label and reasons built from shared items
(DR-05). Formula and weights: docs/productization/05-matching-design.md section 4.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from app.modules.profiles import taxonomy

SCORING_VERSION = "rules-v2"
WEIGHTS = {"I": 0.30, "V": 0.20, "G": 0.15, "P": 0.15, "S": 0.10, "T": 0.10}
THRESHOLD = 0.30
MANY = 0.60
# Facets whose exact overlap can be explained truthfully; availability is supportive only.
EXPLAINABLE = ("interests", "values", "activities")


@dataclass(frozen=True)
class Breakdown:
    score: float
    components: dict[str, float]
    coverage: float
    shared: dict[str, list[str]]


def _tags(profile: Mapping[str, Any], facet: str) -> list[str]:
    return list(dict.fromkeys(profile.get(facet) or []))


def _overlap(a: list[str], b: list[str]) -> float | None:
    if not a or not b:
        return None
    return len(set(a) & set(b)) / min(len(a), len(b))


def _interests(a: list[str], b: list[str]) -> float:
    if not a or not b:
        return 0.0
    matrix = taxonomy.SIMILARITY
    # map() over precomputed rows: this runs for every candidate on every request.
    forward = sum([max(map(matrix[x].__getitem__, b)) for x in a])
    backward = sum([max(map(matrix[y].__getitem__, a)) for y in b])
    return (forward + backward) / (len(a) + len(b))


def interest_component(a: Mapping[str, Any], b: Mapping[str, Any]) -> float:
    """The I component alone; ranking uses it as candidate-to-candidate similarity."""
    return _interests(_tags(a, "interests"), _tags(b, "interests"))


ORDER = {
    "interests": taxonomy.INTERESTS,
    "values": taxonomy.VALUES,
    "activities": taxonomy.ACTIVITIES,
    "availability": taxonomy.AVAILABILITY,
}


def score(a: Mapping[str, Any], b: Mapping[str, Any]) -> Breakdown:
    ta = {facet: _tags(a, facet) for facet in ORDER}
    tb = {facet: _tags(b, facet) for facet in ORDER}
    components: dict[str, float] = {
        "I": _interests(ta["interests"], tb["interests"]),
        "V": _overlap(ta["values"], tb["values"]) or 0.0,
        "G": taxonomy.goal_compat(a["goal"], b["goal"]),
        "S": taxonomy.style_compat(a["style"], b["style"]),
    }
    for key, facet in (("P", "activities"), ("T", "availability")):
        value = _overlap(ta[facet], tb[facet])
        if value is not None:
            components[key] = value
    coverage = sum(WEIGHTS[key] for key in components)
    raw = sum(WEIGHTS[key] * value for key, value in components.items()) / coverage
    shared = {}
    for facet, order in ORDER.items():
        common = set(ta[facet]).intersection(tb[facet])
        # Taxonomy order keeps the result identical for (a, b) and (b, a).
        shared[facet] = [tag for tag in order if tag in common] if common else []
    return Breakdown(raw * (0.9 + 0.1 * coverage), components, coverage, shared)


def eligible(breakdown: Breakdown) -> bool:
    """Shown only above the threshold *and* with at least one truthful shared reason."""
    return breakdown.score >= THRESHOLD and any(
        breakdown.shared.get(facet) for facet in EXPLAINABLE
    )


def label(breakdown: Breakdown) -> Literal["many", "some"]:
    return "many" if breakdown.score >= MANY else "some"


def goal_allowed(a: Mapping[str, Any], b: Mapping[str, Any]) -> bool:
    """strictGoal on either side requires the same goal (reciprocal by construction)."""
    strict = bool(a.get("strict_goal")) or bool(b.get("strict_goal"))
    return not strict or a["goal"] == b["goal"]
