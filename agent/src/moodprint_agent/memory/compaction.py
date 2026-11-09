"""When to compact a long session: by estimated size, not by the SDK's default of 10 items."""

import json
import math
from collections.abc import Callable, Sequence
from typing import Any, cast

from moodprint_shared.config import AppConfig

Policy = Callable[[dict[str, Any]], bool]


def estimate_item_tokens(item: Any) -> int:
    """Deliberately high (one token per 3 characters of the serialised item)."""
    try:
        return math.ceil(len(json.dumps(item, ensure_ascii=False, default=str)) / 3)
    except (TypeError, ValueError):
        return 0


def estimate_items_tokens(items: Sequence[Any]) -> int:
    return sum(estimate_item_tokens(item) for item in items)


def token_compaction_policy(cfg: AppConfig) -> Policy:
    """Compact once the stored history would cost at least ``compaction_trigger_tokens``.

    The SDK passes ``session_items`` (everything it holds) and the candidate items (assistant and
    tool output; user messages and earlier compaction items are never rewritten). Both must be
    present, so a session that is mostly user text is not compacted for nothing.
    """
    threshold = cfg.agent.compaction_trigger_tokens

    def policy(context: dict[str, Any]) -> bool:
        candidates = cast(Sequence[Any], context.get("compaction_candidate_items") or [])
        session_items = cast(Sequence[Any], context.get("session_items") or candidates)
        return bool(candidates) and estimate_items_tokens(session_items) >= threshold

    return policy
