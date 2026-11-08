"""Deterministic gate for agent-proposed memory candidates (before the user ever sees them).

Long-term memory is for durable *preferences and goals*, never for incident facts or people's
names or contacts. The gate returns a coded reason, never the rejected text, so nothing sensitive
reaches logs.
"""

import re
from typing import Final, Literal

Category = Literal["preference", "communication", "support_person", "goal", "context"]
Reason = Literal[
    "empty_after_trim",
    "too_long",
    "contains_contact",
    "contains_name",
    "incident_content",
    "category_mismatch",
]

MAX_CHARS: Final = 500
_EMAIL: Final = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_URL: Final = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_PHONE: Final = re.compile(r"(?<!\w)\+?\d[\d .-]{6,}\d(?!\w)")
_HANDLE: Final = re.compile(r"(?<!\w)@\w{2,}")
_DATE: Final = re.compile(
    r"\b\d{1,2}\s*[/.-]\s*\d{1,2}(?:\s*[/.-]\s*\d{2,4})?\b|\bngày\s+\d{1,2}\b", re.IGNORECASE
)
_INCIDENT: Final = re.compile(
    r"đánh|đấm|đá\b|xô\s*đẩy|đe\s*dọa|dọa|bắt\s*nạt|ép\b|chế\s*giễu|chửi|lăng\s*mạ|"
    r"chụp\s*(?:màn\s*hình|ảnh)|lộ\s*ảnh|ảnh\s*riêng|tung\s*ảnh|tống\s*tiền|xâm\s*hại|bạo\s*hành|"
    r"loại\s*khỏi\s*nhóm|cô\s*lập|nhắn\s*tin\s*(?:dọa|chửi)",
    re.IGNORECASE,
)
_ROLE_PREFIX: Final = frozenset(
    {"bạn", "anh", "chị", "em", "cậu", "ông", "bà", "chú", "bác", "cô", "thầy"}
)
_COMMON_NAMES: Final = frozenset(
    {
        "lan",
        "hoa",
        "nam",
        "hùng",
        "huy",
        "linh",
        "trang",
        "thảo",
        "long",
        "phong",
        "khoa",
        "đạt",
        "tuấn",
        "hương",
        "nga",
        "vy",
        "quân",
        "bảo",
        "dũng",
        "hải",
        "nhung",
        "trâm",
    }
)
# Words that make a "support person" a role ("cô chủ nhiệm") rather than a named person.
_ROLE_WORDS: Final = re.compile(
    r"\b(?:cô|thầy|giáo\s*viên|chủ\s*nhiệm|tư\s*vấn|hiệu\s*trưởng|bố|mẹ|cha|ba|má|anh|chị|ông|bà|"
    r"chú|bác|dì|cậu|huấn\s*luyện\s*viên|người\s*lớn|bạn\s*thân|hàng\s*xóm|người\s*thân)\b",
    re.IGNORECASE,
)


def _is_cap(token: str) -> bool:
    return len(token) > 1 and token[0].isupper() and token[1:].islower()


def _contains_name(text: str) -> bool:
    tokens = re.findall(r"\w+", text)
    for first, second in zip(tokens, tokens[1:], strict=False):
        if _is_cap(first) and _is_cap(second):
            return True  # e.g. "Nguyễn Văn", "Trần Minh"
    for index, token in enumerate(tokens):
        previous = tokens[index - 1].casefold() if index else ""
        if index and token.casefold() in _COMMON_NAMES and token[:1].isupper():
            return True
        if (
            index
            and previous in _ROLE_PREFIX
            and ((len(token) == 1 and token.isupper()) or _is_cap(token))
        ):
            return True  # "bạn A", "cô Hoa"
    return False


def validate_candidate(category: Category, content: str) -> Reason | None:
    """Return a rejection reason, or None when the candidate may be shown to the user."""
    text = content.strip()
    if not text:
        return "empty_after_trim"
    if len(text) > MAX_CHARS:
        return "too_long"
    if _EMAIL.search(text) or _URL.search(text) or _PHONE.search(text) or _HANDLE.search(text):
        return "contains_contact"
    if _contains_name(text):
        return "contains_name"
    if _INCIDENT.search(text) or _DATE.search(text):
        return "incident_content"
    if category == "support_person" and not _ROLE_WORDS.search(text):
        return "category_mismatch"
    if category == "context" and _INCIDENT.search(text):
        return "incident_content"
    return None
