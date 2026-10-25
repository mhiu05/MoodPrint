"""E-01/F-01: the static banks are complete, well-formed and avoid sensitive topics."""

import copy
from collections import Counter

import pytest

from app.modules.activities import content


def test_icebreaker_bank_has_eight_items_per_tier_with_short_prompts():
    items = content.load_bank("icebreaker_v1")
    counts = Counter(item["tier"] for item in items)
    assert all(counts[tier] >= 8 for tier in content.TIERS) and len(items) >= 24
    assert len({item["id"] for item in items}) == len(items)
    assert all(len(item["prompt"]) <= 120 for item in items)
    assert all(3 <= len(item["options"]) <= 4 for item in items)
    assert all(len(set(item["options"])) == len(item["options"]) for item in items)


def test_quiz_bank_has_sixty_items_five_categories_and_valid_answers():
    items = content.load_bank("coop_quiz_v1")
    assert len(items) >= 60 and len({item["category"] for item in items}) >= 5
    assert len({item["id"] for item in items}) == len(items)
    assert all(item["correctIndex"] in range(4) for item in items)
    assert all(len(item["explanation"]) <= 160 for item in items)
    assert all(len(item["options"]) == 4 for item in items)


def test_no_bank_mentions_a_banned_topic():
    for name in ("icebreaker_v1", "coop_quiz_v1"):
        text = " ".join(
            " ".join([item["prompt"], *item["options"], item.get("explanation", "")])
            for item in content.load_bank(name)
        ).lower()
        assert not [term for term in content.BANNED if term in text]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda items: items.append(copy.deepcopy(items[0])),  # duplicate id
        lambda items: items[0].update(prompt="x" * 121),
        lambda items: items[0].update(options=["Có", "Có", "Không"]),
        lambda items: items[0].update(prompt="Bạn nghĩ gì về tôn giáo?"),
    ],
)
def test_invalid_icebreaker_banks_are_rejected(mutate):
    items = [dict(item) for item in content.load_bank("icebreaker_v1")]
    mutate(items)
    with pytest.raises(content.InvalidBank):
        content.validate_icebreaker(items)
        content._banned(items)


def test_invalid_quiz_answer_is_rejected():
    items = [dict(item) for item in content.load_bank("coop_quiz_v1")]
    items[0]["correctIndex"] = 4
    with pytest.raises(content.InvalidBank):
        content.validate_quiz(items)
