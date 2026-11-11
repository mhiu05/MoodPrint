"""Which memories are worth asking for: intent hints, never "everything".

Approved memory is retrieved lexically from the user's own message (and the linked case title);
it is never embedded and never sent to a third-party retrieval service. Categories narrow the
search only when the message clearly points at one or two of them; an ambiguous message searches
all categories rather than guessing, and a query that matches nothing returns nothing.
"""

from typing import Final

from safevoice_shared.contracts.memory import MemoryCategory, MemoryQuery

from safevoice_agent.tools.safety import fold

INTENT_KEYWORDS: Final[dict[MemoryCategory, tuple[str, ...]]] = {
    "support_person": (
        "nho ai",
        "noi voi ai",
        "nguoi lon",
        "co giao",
        "thay giao",
        "bo me",
        "ba me",
        "ai giup",
        "nguoi tin",
        "tin tuong ai",
    ),
    "communication": (
        "cach noi",
        "mo loi",
        "viet tin",
        "nhan tin",
        "dien tap",
        "trinh bay",
        "noi chuyen",
    ),
    "goal": ("muc tieu", "ke hoach", "du dinh", "muon dat", "tuan nay"),
    "preference": ("thich", "khong thich", "thoi quen", "uu tien", "tra loi ngan", "tra loi dai"),
}
QUERY_MAX_CHARS: Final = 4000


def infer_categories(text: str) -> list[MemoryCategory]:
    """Categories the message clearly asks about; empty when none or too many (ambiguous)."""
    folded = fold(text)
    hits: list[MemoryCategory] = [
        category
        for category, keywords in INTENT_KEYWORDS.items()
        if any(keyword in folded for keyword in keywords)
    ]
    return hits if 1 <= len(hits) <= 2 else []


def memory_query(user_input: str, *, case_title: str | None, limit: int) -> MemoryQuery:
    text = user_input.strip()
    if case_title:
        text = f"{text} {case_title.strip()}"
    return MemoryQuery(
        text=text[:QUERY_MAX_CHARS], categories=infer_categories(user_input), limit=limit
    )
