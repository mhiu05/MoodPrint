"""Content-free rubric for one multi-bubble reply. Reports never contain reply text."""

import re

from pydantic import ValidationError

from app.ai.schemas import CompanionReply
from evals.multi_message.cases import Case

_LIST_ITEM = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+", re.M)

# Gate thresholds from phase-1/08 P1-08.
SHORT_SINGLE_TARGET = 0.95
LIST_UNSPLIT_TARGET = 0.95


def score(case: Case, payload: dict) -> dict:
    """Checks for one model output payload ({"messages": [...]})."""
    try:
        reply = CompanionReply.model_validate(payload)
    except ValidationError:
        return {"caseId": case.case_id, "kind": case.kind, "valid": False, "bubbles": 0,
                "singleWhenShort": False if case.kind == "short" else None,
                "listUnsplit": False if case.kind == "list" else None}
    texts = [bubble.text for bubble in reply.messages]
    with_items = [index for index, text in enumerate(texts) if _LIST_ITEM.search(text)]
    # A list is split when list items appear in more than one bubble.
    unsplit = len(with_items) <= 1
    return {
        "caseId": case.case_id,
        "kind": case.kind,
        "valid": True,
        "bubbles": len(texts),
        "singleWhenShort": (len(texts) == 1) if case.kind == "short" else None,
        "listUnsplit": unsplit if case.kind == "list" else None,
    }


def summarize(scores: list[dict]) -> dict:
    def rate(key: str) -> float | None:
        values = [item[key] for item in scores if item[key] is not None]
        return round(sum(values) / len(values), 4) if values else None

    short, unsplit = rate("singleWhenShort"), rate("listUnsplit")
    valid = rate("valid")
    return {
        "cases": len(scores),
        "validRate": valid,
        "shortSingleRate": short,
        "listUnsplitRate": unsplit,
        "meanBubbles": round(sum(item["bubbles"] for item in scores) / len(scores), 3) if scores else None,
        "passed": bool(
            scores
            and valid == 1.0
            and short is not None and short >= SHORT_SINGLE_TARGET
            and unsplit is not None and unsplit >= LIST_UNSPLIT_TARGET
        ),
    }
