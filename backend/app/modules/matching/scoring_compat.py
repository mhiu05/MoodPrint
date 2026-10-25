"""Rollback scorer: v1's exact-overlap formula over the current public taxonomy.

The frozen oracle in scoring.py stays unchanged. v1.1 fixes vocabulary loss without
depending on v2's similarities, weighting, soft goals or diversification, so switching
back from v2 remains an independent rollback. Only public profile fields are inputs.
"""

from collections.abc import Mapping
from typing import Any

from app.modules.matching.scoring import _valid_tags, half_up
from app.modules.profiles import taxonomy

SCORING_VERSION = "rules-v1.1"


def score(a: Mapping[str, Any], b: Mapping[str, Any]) -> int:
    for profile in (a, b):
        if not (
            all(
                _valid_tags(profile.get(field), allowed, taxonomy.LIMITS[field][0])
                for field, allowed in (
                    ("interests", taxonomy.INTERESTS),
                    ("values", taxonomy.VALUES),
                    ("languages", taxonomy.LANGUAGES),
                )
            )
            and profile.get("style") in taxonomy.STYLES
            and profile.get("goal") in taxonomy.GOALS
        ):
            return 0
    ni = len(set(a["interests"]) & set(b["interests"]))
    di = len(set(a["interests"]) | set(b["interests"]))
    nv = len(set(a["values"]) & set(b["values"]))
    dv = len(set(a["values"]) | set(b["values"]))
    style = 2 if a["style"] == b["style"] else int("balanced" in (a["style"], b["style"]))
    return half_up(45 * ni * dv * 2 + 35 * nv * di * 2 + 20 * style * di * dv, di * dv * 2)
