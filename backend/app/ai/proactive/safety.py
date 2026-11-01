"""Deterministic pre-model screen for check-ins that read journal entries (phase-1/07 §8).

NOT a comprehensive safety classifier: a narrow, reviewed phrase list. A match means the
check-in skips the model, quotes nothing and sends the fixed template below. Nothing about
the match is stored, logged with content, or reported to anyone.
"""

import re
import unicodedata

# Accented forms only where the unaccented spelling is ambiguous ("tự tử" vs "từ từ").
_ACCENTED = re.compile(
    r"tự\s*tử|tự\s*sát|muốn\s*chết|không\s*muốn\s*sống|tự\s*làm\s*hại|tự\s*hại\s*bản\s*thân"
    r"|kết\s*liễu|rạch\s*tay|chấm\s*dứt\s*cuộc\s*đời"
)
_FOLDED = re.compile(
    r"\bmuon\s*chet\b|\bkhong\s*muon\s*song\b|\btu\s*sat\b|\bket\s*lieu\b"
    r"|\bkill\s*myself\b|\bsuicid\w*|\bself[\s-]*harm\w*|\bend\s*my\s*life\b|\bwant\s*to\s*die\b"
)
SAFETY_TEMPLATE = (
    "Chào bạn. Mình ở đây nếu bạn muốn trò chuyện, không cần kể nhiều đâu. Nếu lúc này bạn "
    "thấy không an toàn với chính mình, hãy liên hệ ngay một người bạn tin cậy ở gần hoặc "
    "dịch vụ cấp cứu nơi bạn đang ở."
)


def _fold(text: str) -> str:
    lowered = text.lower().replace("đ", "d")
    return "".join(c for c in unicodedata.normalize("NFD", lowered) if not unicodedata.combining(c))


def distress_screen(texts) -> bool:
    for text in texts:
        if not text:
            continue
        lowered = unicodedata.normalize("NFC", text.lower())
        if _ACCENTED.search(lowered) or _FOLDED.search(_fold(text)):
            return True
    return False
