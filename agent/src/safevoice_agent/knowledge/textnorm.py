"""Vietnamese text cleanup and accent folding.

The fold matches the SQL expression on ``knowledge`` generated columns:
``lower`` → Unicode NFD → drop a fixed combining-mark list → ``đ/Đ`` to ``d``.
The mark list is exactly the set produced by NFD of the Vietnamese alphabet.
"""

from __future__ import annotations

import re
import unicodedata

# Combining marks from NFD of Vietnamese vowels. Order is stable for SQL chr().
VIET_MARKS: tuple[int, ...] = (
    0x0300,
    0x0301,
    0x0302,
    0x0303,
    0x0306,
    0x0309,
    0x031B,
    0x0323,
)
D_WITH_STROKE = (0x0111, 0x0110)
_MARKS = frozenset(chr(code) for code in VIET_MARKS)
_CONTROL = re.compile(r"[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f-\u009f\u200b-\u200f\ufeff]")
_SPACE = re.compile(r"\s+")


def clean_text(value: str) -> str:
    text = unicodedata.normalize("NFC", value)
    text = _CONTROL.sub("", text)
    return _SPACE.sub(" ", text).strip()


def fold_vietnamese(value: str) -> str:
    text = clean_text(value).lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if ch not in _MARKS)
    return text.replace("đ", "d")


def sql_fold_expr(sql_text_expr: str) -> str:
    """ASCII-only SQL for the same fold, safe for the migration scope checker."""
    stroke = "||".join(f"chr({code})" for code in D_WITH_STROKE)
    marks = "||".join(f"chr({code})" for code in VIET_MARKS)
    return f"translate(normalize(lower({sql_text_expr}), nfd), {stroke}||{marks}, 'dd')"
