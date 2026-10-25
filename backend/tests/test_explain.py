"""Explanation faithfulness: every reason names an item both profiles actually share."""

import random
import re

from app.modules.matching import explain, scoring_v2
from app.modules.profiles import taxonomy
from tests.test_scoring_v2 import A, B, random_profile


def faithful(reason: str, a: dict, b: dict) -> bool:
    for facet, labels, template in (
        ("interests", taxonomy.INTERESTS, "Cùng thích {}"),
        ("values", taxonomy.VALUES, "Cùng coi trọng {}"),
        ("availability", taxonomy.AVAILABILITY, "Hay rảnh {}"),
    ):
        for tag, label in labels.items():
            if reason == template.format(label.lower()):
                return tag in (a.get(facet) or []) and tag in (b.get(facet) or [])
    for tag, phrase in taxonomy.ACTIVITY_REASONS.items():
        if reason == phrase:
            return tag in (a.get("activities") or []) and tag in (b.get("activities") or [])
    if reason == "Cùng cách trò chuyện":
        return a["style"] == b["style"]
    return False


def test_worked_example_reasons():
    assert explain.reasons(scoring_v2.score(A, B)) == [
        "Cả hai muốn thử tập trung cùng nhau",
        "Cùng thích đọc sách",
        "Cùng coi trọng ham học hỏi",
    ]


def test_reasons_are_faithful_bounded_and_number_free_over_random_pairs():
    rng = random.Random(7)
    for _ in range(500):
        a, b = random_profile(rng), random_profile(rng)
        breakdown = scoring_v2.score(a, b)
        reasons = explain.reasons(breakdown)
        assert len(reasons) <= 3 and len(set(reasons)) == len(reasons)
        assert all(faithful(reason, a, b) for reason in reasons), reasons
        assert not any(re.search(r"\d|%", reason) for reason in reasons)
        if scoring_v2.eligible(breakdown):
            assert reasons  # an eligible suggestion always has a truthful reason
        assert reasons == explain.reasons(scoring_v2.score(b, a))


def test_label_mapping():
    assert scoring_v2.label(scoring_v2.score(A, A)) == "many"
    assert scoring_v2.label(scoring_v2.Breakdown(0.31, {}, 1.0, {})) == "some"
