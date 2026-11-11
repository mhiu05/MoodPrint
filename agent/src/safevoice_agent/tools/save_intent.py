"""Does the student's own message clearly ask to save something?

This only decides whether to add a *hint* to the model for this turn (the A-03a handoff: a clear
"lưu đi" after a proposal must lead to the approval dialog instead of being asked again). It never
grants anything: the write still needs the approval dialog and the stored, hashed proposal
(A-03b). It reads the user's text only, never retrieved documents, memory, notes or image text.
"""

import re
from typing import Final, Literal

from safevoice_agent.tools.safety import fold

SaveIntent = Literal["clear", "ambiguous", "none"]

TURN_HINT_CLEAR: Final = (
    "Người dùng vừa nói rõ muốn lưu. Nếu trong cuộc trò chuyện này đã có đề xuất đầy đủ chưa lưu, "
    "hãy gọi công cụ save_* tương ứng với đúng proposal_id ngay trong lượt này (hộp thoại duyệt sẽ "
    "hiện cho người dùng) và đừng hỏi lại có muốn lưu không. Chưa có đề xuất hoặc còn thiếu thông "
    "tin thì soạn đề xuất hoặc hỏi một câu làm rõ. Việc lưu luôn cần người dùng tự bấm duyệt."
)

_SAVE = re.compile(
    r"\b(?:luu|ghi (?:lai|vao|nhan)|them vao ho so|dong y luu|chot luu|cat vao ho so)\b"
)
_NEGATED = re.compile(
    r"\b(?:dungz|khong|chua|dungz can|khoan|thoi|bo qua|huy|dung co|chua can|khong can)\b"
    r"(?: \w+){0,3} (?:luu|ghi|them)\b"
)
_QUESTION = re.compile(
    r"\b(?:co nen|nen luu|luu duoc khong|luu khong|luu nhe\?|hay la|de minh nghi|de xem|"
    r"khong biet co|phan van|neu luu|lo luu)\b"
)
_CONDITIONAL = re.compile(r"\b(?:neu|giasu|gia su|khi nao|bao gio|sau khi|cho den khi)\b")


def assess_save_intent(text: str) -> SaveIntent:
    """``clear`` only for a plain, affirmative, unconditional request; doubt is ``ambiguous``."""
    folded = fold(text)
    if not _SAVE.search(folded):
        return "none"
    if _NEGATED.search(folded):
        return "none"
    if "?" in text or _QUESTION.search(folded) or _CONDITIONAL.search(folded):
        return "ambiguous"
    return "clear"
