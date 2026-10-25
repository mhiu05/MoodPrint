"""Reasons for a v2 suggestion, built only from items both published profiles share.

Never a number or a percentage, and never a claim about psychological compatibility
(DR-05). Priority: shared activities, interests, values, same style, availability; one
of each first (variety), then more interests and values, at most three in total.
"""

from app.modules.matching.scoring_v2 import Breakdown
from app.modules.profiles import taxonomy

LIMIT = 3


def _candidates(breakdown: Breakdown) -> list[list[str]]:
    shared = breakdown.shared
    return [
        [taxonomy.ACTIVITY_REASONS[tag] for tag in shared.get("activities", [])],
        [f"Cùng thích {taxonomy.INTERESTS[tag].lower()}" for tag in shared.get("interests", [])],
        [f"Cùng coi trọng {taxonomy.VALUES[tag].lower()}" for tag in shared.get("values", [])],
        ["Cùng cách trò chuyện"] if breakdown.components.get("S") == 1.0 else [],
        [
            f"Hay rảnh {taxonomy.AVAILABILITY[tag].lower()}"
            for tag in shared.get("availability", [])
        ],
    ]


def reasons(breakdown: Breakdown) -> list[str]:
    groups = _candidates(breakdown)
    result = [group[0] for group in groups if group][:LIMIT]
    for group in (groups[1], groups[2]):
        for reason in group[1:]:
            if len(result) == LIMIT:
                return result
            result.append(reason)
    return result
