"""Pure query preparation: normalize, redact, truncate, and build a safe tsquery."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from safevoice_agent.knowledge.lexical import folded_terms
from safevoice_agent.knowledge.textnorm import clean_text

_EMAIL = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", re.UNICODE)
_URL = re.compile(r"(?i)\b(?:https?://|www\.)\S+")
_HANDLE = re.compile(r"(?<!\w)@[A-Za-z0-9_.]{2,}")
_PHONE = re.compile(r"(?<!\d)(?:\+?84|0)[\s.\-]?\d{2,3}[\s.\-]?\d{3}[\s.\-]?\d{3,4}(?!\d)")
_LONG_DIGITS = re.compile(r"\d{8,}")
# First-pass stoplist, no longer used for retrieval (see lexical.STOP_TERMS). Kept so that
# agent/evals/knowledge/diagnosis/diagnose_v1.py still imports.
STOPWORDS = frozenset(
    "la va cua co khong thi toi minh ban gi nhu the nao bi cho duoc khi mot cac "
    "nhung de o trong voi".split()
)
_UPPER = re.compile(r"[A-ZÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈĨÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸĐ]")


@dataclass(frozen=True, slots=True)
class PreparedQuery:
    embed_text: str
    tsquery: str | None
    empty: bool


def redact_identifiers(text: str) -> str:
    redacted = _EMAIL.sub(" ", text)
    redacted = _URL.sub(" ", redacted)
    redacted = _HANDLE.sub(" ", redacted)
    redacted = _PHONE.sub(" ", redacted)
    redacted = _LONG_DIGITS.sub(" ", redacted)
    return clean_text(redacted)


def truncate_words(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    clipped = text[:limit]
    if " " in clipped:
        clipped = clipped.rsplit(" ", 1)[0]
    return clipped.strip()


def lexical_tokens(text: str, *, limit: int = 16) -> list[str]:
    """Distinct information-bearing folded terms; see ``lexical.query_terms``."""
    return folded_terms(text, limit=limit)


def prepare_query(text: str, *, max_chars: int) -> PreparedQuery:
    normalized = clean_text(unicodedata.normalize("NFC", text)).casefold()
    redacted = redact_identifiers(normalized)
    clipped = truncate_words(redacted, max_chars)
    if not clipped:
        return PreparedQuery(embed_text="", tsquery=None, empty=True)
    tokens = lexical_tokens(clipped)
    tsquery = " | ".join(tokens) if tokens else None
    return PreparedQuery(embed_text=clipped, tsquery=tsquery, empty=False)


def split_sentences(text: str) -> list[str]:
    """Split after . ! ? when the next letter is uppercase, keeping abbreviations."""
    abbreviations = ("tp.", "q.", "p.", "ths.", "ts.", "gs.", "pgs.")
    parts: list[str] = []
    start = 0
    index = 0
    while index < len(text):
        char = text[index]
        if char in ".!?":
            token = text[start : index + 1].strip().lower()
            tail = token.split()[-1] if token.split() else token
            numbered = bool(re.fullmatch(r"\d+\.", tail))
            if tail in abbreviations or numbered:
                index += 1
                continue
            nxt = index + 1
            while nxt < len(text) and text[nxt].isspace():
                nxt += 1
            if nxt >= len(text) or _UPPER.match(text[nxt]):
                piece = text[start : index + 1].strip()
                if piece:
                    parts.append(piece)
                start = nxt
                index = nxt
                continue
        index += 1
    tail = text[start:].strip()
    if tail:
        parts.append(tail)
    return parts
