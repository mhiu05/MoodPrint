"""Static, reviewed content banks (DR-09), validated at import so a bad bank fails startup."""

import json
from functools import cache
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
TIERS = ("light", "curious", "reflective")
# Topics the banks must never touch (no politics, religion, health, money or intimacy).
BANNED = (
    "chính trị",
    "đảng",
    "tôn giáo",
    "bệnh",
    "thuốc",
    "tiền lương",
    "thu nhập",
    "tình dục",
    "cân nặng",
    "ly hôn",
    "tự tử",
)


class InvalidBank(ValueError):
    pass


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise InvalidBank(message)


def validate_icebreaker(items: list[dict[str, Any]]) -> None:
    _check(len({item["id"] for item in items}) == len(items), "duplicate ids")
    for tier in TIERS:
        _check(sum(item["tier"] == tier for item in items) >= 8, f"tier {tier} needs 8 items")
    for item in items:
        _check(set(item) == {"id", "tier", "prompt", "options", "allowText"}, item["id"])
        _check(item["tier"] in TIERS and len(item["id"]) <= 32, item["id"])
        _check(0 < len(item["prompt"]) <= 120, f"{item['id']} prompt length")
        options = item["options"]
        _check(3 <= len(options) <= 4 and len(set(options)) == len(options), item["id"])
        _check(all(0 < len(option) <= 60 for option in options), item["id"])


def validate_quiz(items: list[dict[str, Any]]) -> None:
    _check(len(items) >= 60, "quiz needs at least 60 items")
    _check(len({item["id"] for item in items}) == len(items), "duplicate ids")
    _check(len({item["category"] for item in items}) >= 5, "quiz needs 5 categories")
    for item in items:
        _check(
            set(item) == {"id", "category", "prompt", "options", "correctIndex", "explanation"},
            item["id"],
        )
        _check(len(item["id"]) <= 32 and 0 < len(item["prompt"]) <= 120, item["id"])
        _check(len(item["options"]) == 4 and len(set(item["options"])) == 4, item["id"])
        _check(item["correctIndex"] in range(4), item["id"])
        _check(0 < len(item["explanation"]) <= 160, f"{item['id']} explanation length")


def _banned(items: list[dict[str, Any]]) -> None:
    for item in items:
        words = " ".join([item["prompt"], *item["options"], item.get("explanation", "")]).lower()
        _check(not any(term in words for term in BANNED), f"{item['id']} sensitive topic")


@cache
def load_bank(name: str) -> tuple[dict[str, Any], ...]:
    items = json.loads((HERE / f"{name}.json").read_text(encoding="utf-8"))["items"]
    {"icebreaker_v1": validate_icebreaker, "coop_quiz_v1": validate_quiz}[name](items)
    _banned(items)
    return tuple(items)


def item_by_id(name: str, item_id: str) -> dict[str, Any]:
    return next(item for item in load_bank(name) if item["id"] == item_id)


# Fail fast at import (and therefore at application startup).
for _bank in ("icebreaker_v1", "coop_quiz_v1"):
    load_bank(_bank)
