"""Pure parity oracle for the existing frontend matching behavior.

The legacy scoring version is intentional: changing runtime language does not
change weights, taxonomy, eligibility rules, or the public card projection.
Database authorization and production candidate retrieval remain separate.
"""

from collections.abc import Mapping
from typing import Any

SCORING_VERSION = "mock-v1"

_INTERESTS = {
    "reading": "Đọc sách",
    "music": "Nghe nhạc",
    "walking": "Đi bộ",
    "cooking": "Nấu ăn",
    "english": "Học tiếng Anh",
    "photography": "Chụp ảnh",
    "puzzles": "Giải đố",
}
_VALUES = {
    "respect": "Tôn trọng",
    "sincerity": "Chân thành",
    "curiosity": "Ham học hỏi",
    "kindness": "Tử tế",
}
_STYLES = {"balanced", "listening", "direct"}
_GOALS = {"shared-interests", "friendship"}
_LANGUAGES = {"vi", "en"}
_PROFILE_FIELDS = {
    "interests",
    "values",
    "style",
    "goal",
    "languages",
    "sources",
    "version",
    "valid",
}


def half_up(numerator: int, denominator: int) -> int:
    """Round a rational value using the frontend's final round-half-up rule."""
    return (2 * numerator + denominator) // (2 * denominator)


def _valid_tags(tags: Any, allowed: Mapping[str, str] | set[str], minimum: int) -> bool:
    return (
        isinstance(tags, list)
        and len(tags) >= minimum
        and all(isinstance(tag, str) and tag in allowed for tag in tags)
        and len(tags) == len(set(tags))
    )


def _valid_profile(profile: Mapping[str, Any]) -> bool:
    return (
        not (profile.keys() - _PROFILE_FIELDS)
        and _valid_tags(profile.get("interests"), _INTERESTS, 3)
        and _valid_tags(profile.get("values"), _VALUES, 2)
        and _valid_tags(profile.get("languages"), _LANGUAGES, 1)
        and profile.get("style") in _STYLES
        and profile.get("goal") in _GOALS
        and isinstance(profile.get("sources"), list)
        and all(
            isinstance(source, Mapping)
            and isinstance(source.get("id"), str)
            and type(source.get("version")) in (int, float)
            and source["version"] % 1 == 0
            and not (source.keys() - {"id", "version"})
            for source in profile["sources"]
        )
    )


def score(a: Mapping[str, Any], b: Mapping[str, Any]) -> int:
    """Compute 45% interest Jaccard + 35% value Jaccard + style points.

    Duplicate tags are removed before validation, just as in the TypeScript
    score function. Eligibility validates original profiles separately.
    """
    a = {**a, **{key: list(dict.fromkeys(a[key])) for key in ("interests", "values", "languages")}}
    b = {**b, **{key: list(dict.fromkeys(b[key])) for key in ("interests", "values", "languages")}}
    if not _valid_profile(a) or not _valid_profile(b):
        return 0
    ni = len(set(a["interests"]) & set(b["interests"]))
    di = len(set(a["interests"]) | set(b["interests"]))
    nv = len(set(a["values"]) & set(b["values"]))
    dv = len(set(a["values"]) | set(b["values"]))
    style = 2 if a["style"] == b["style"] else int("balanced" in (a["style"], b["style"]))
    return half_up(45 * ni * dv * 2 + 35 * nv * di * 2 + 20 * style * di * dv, di * dv * 2)


def eligibility(profile: Mapping[str, Any], candidate: Mapping[str, Any]) -> bool:
    """Apply the frontend oracle's peer consent, goal, and language filters."""
    peer = candidate["profile"]
    return bool(
        candidate["allowed"]
        and _valid_profile(profile)
        and _valid_profile(peer)
        and profile["goal"] == peer["goal"]
        and set(profile["languages"]) & set(peer["languages"])
    )


def _can_match(state: Mapping[str, Any]) -> bool:
    published = state.get("published")
    if not (
        state["ready"]
        and state["age"] == "adult"
        and state["consent"]["MATCH"]
        and published
        and published["valid"]
        and _valid_profile(published)
    ):
        return False
    return all(
        any(
            item["id"] == source["id"]
            and item["version"] == source["version"]
            and item["status"] in ("confirmed", "edited")
            and source["id"] == "PI01"
            and "reading" in published["interests"]
            for item in state["privateItems"]
        )
        for source in published["sources"]
    )


def recommendations(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return up to five safe oracle cards, with at most three ordered reasons."""
    if not _can_match(state):
        return []
    published = state["published"]
    cards = []
    for candidate in state["candidates"]:
        identifier = candidate["id"]
        cooldown = state["cooldowns"].get(identifier)
        if (
            not eligibility(published, candidate)
            or identifier in state["blocked"]
            or (cooldown is not None and cooldown > state["clock"])
            or any(
                request["candidateId"] == identifier and request["status"] == "pending"
                for request in state["requests"]
            )
            or any(
                connection["candidateId"] == identifier and connection["status"] == "open"
                for connection in state["connections"]
            )
        ):
            continue
        peer = candidate["profile"]
        points = score(published, peer)
        if points < 30:
            continue
        reasons = [
            f"Cùng thích {label.lower()}"
            for tag, label in _INTERESTS.items()
            if tag in published["interests"] and tag in peer["interests"]
        ] + [
            f"Cùng coi trọng {label.lower()}"
            for tag, label in _VALUES.items()
            if tag in published["values"] and tag in peer["values"]
        ]
        if published["style"] == peer["style"]:
            reasons.append("Cùng cách trò chuyện")
        cards.append(
            {
                "candidate": {
                    "id": identifier,
                    "alias": candidate["alias"],
                    "color": candidate["color"],
                    "profile": {
                        "interests": list(peer["interests"]),
                        "values": list(peer["values"]),
                        "style": peer["style"],
                        "goal": peer["goal"],
                        "languages": list(peer["languages"]),
                    },
                },
                "scoringVersion": SCORING_VERSION,
                "profileVersion": published["version"],
                "peerVersion": candidate["version"],
                "score": points,
                "reasons": reasons[:3],
            }
        )
    cards.sort(key=lambda card: (-card["score"], card["candidate"]["id"]))
    return cards[:5]
