"""Fast path (03 §2): decide without a model whether Điều phối should ask the planner at all.

This never routes on its own: it only filters out turns where a planner call would be wasted
(greetings, thanks, short chit-chat) and turns that must never be delegated (distress). The
planner LLM makes the actual decision for everything that passes.
"""

import re
from typing import Literal

from app.ai.collaboration.policy import fold
from app.ai.proactive.safety import distress_screen

_TRIVIAL = re.compile(
    r"^(?:(?:dieu phoi|ban|minh|oi|a|nhe|nha|nhieu|lam|chao|xin chao|hi|hello|alo|cam on|thanks|thank you|ok|oke|"
    r"okay|uh|um|vang|da|hihi|haha|hehe|tot|duoc|bye|tam biet|good morning|chuc ngu ngon)[\s,!.?~]*)+$"
)
# Broad, recall-oriented cues: whether a specialist *might* help. The planner decides.
_SPECIALIST = re.compile(
    r"nhat ky|ghi chep|da ghi|minh ghi|nhung gi minh viet|nhin lai|cam xuc|tam trang|tuan (?:qua|nay|vua roi|truoc)|"
    r"thoi quen|lap lai|hoat dong|ke hoach|len lich|lich trinh|thu thach|hoc (?:gi|them|mot|cach)|cuoi tuan|goi y|"
    r"viec (?:nhe|nho|gi)|so thich|muc tieu|chia nho|buoc tiep|lam gi"
)
_TRANSFER = re.compile(
    r"noi chuyen (?:truc tiep )?voi|chuyen (?:sang|cho|qua)|cho minh gap|de (?:nhat ky|hoat dong)|"
    r"(?:nhat ky|hoat dong) (?:oi|tra loi)"
)
_LONG_WORDS = 25


def triage(text: str) -> Literal["direct", "plan"]:
    folded = fold(text or "").strip()
    if not folded or distress_screen([text]):
        return "direct"
    if _TRIVIAL.match(folded):
        return "direct"
    if _SPECIALIST.search(folded) or _TRANSFER.search(folded) or len(folded.split()) >= _LONG_WORDS:
        return "plan"
    return "direct"


def is_trivial(text: str) -> bool:
    """Greetings, thanks and short acknowledgements (no model needed to pick a speaker)."""
    folded = fold(text or "").strip()
    return not folded or bool(_TRIVIAL.match(folded))
