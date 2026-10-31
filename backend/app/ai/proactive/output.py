"""Model-facing check-in outputs and the business validator (phase-1/05 §6)."""

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, Field, model_validator

from app.ai.agents import caps
from app.ai.journal import _JOURNAL_CLAIM, has_journal_link
from app.ai.proactive.safety import distress_screen
from app.ai.provider import _DURABLE_CLAIM
from app.ai.schemas import AiOutput, Bubble, CompanionReply

CHALLENGE_KINDS = (
    "word_play", "riddle", "mini_fact", "drawing", "observation", "gentle_movement", "music",
    "tiny_skill",
)
ChallengeKind = Literal[
    "word_play", "riddle", "mini_fact", "drawing", "observation", "gentle_movement", "music",
    "tiny_skill",
]
MAX_PROACTIVE_BUBBLES = 3
MAX_PROACTIVE_CHARS = 1200
# Only these navigation cards fit a check-in; none performs an action.
ALLOWED_CARDS = {"nhip": {"mood_form"}, "nhatky": {"mood_form"}, "caunoi": {"discovery"}}
_LINK = re.compile(r"\]\s*\(|https?://|www\.|javascript:|data:", re.I)
_YESTERDAY = re.compile(r"\bhom qua\b")
# Quoting yesterday's entry as if written today ("Sáng nay, bạn đã ghi…") misdates the user's words.
_WRONG_DAY = re.compile(
    r"\b(?:sang nay|hom nay|toi nay|chieu nay|vua roi)\b[^.!?\n]{0,24}\b(?:da|co|vua) ghi"
)
_MATCH_CLAIM = re.compile(
    r"\d+\s*%|phan tram|da ket noi|loi moi da (?:duoc )?gui|da gui loi moi|da tim (?:thay|duoc)"
    r"|(?:rat|cuc|hoan toan) (?:hop|tuong hop)"
)


# Folded keywords of kinds whose content is easy to recognise; a label cannot hide a repeat.
_KIND_HINTS = {
    "drawing": re.compile(r"\b(?:ve|to mau|to nguech ngoac|net but|phac thao|doodle)\b"),
    "music": re.compile(r"\b(?:nghe (?:mot |vai )?(?:bai )?nhac|bai hat|ngan nga|huyt sao|nhac cu|hat (?:mot|vai|theo))\b"),
    "gentle_movement": re.compile(r"\b(?:vuon vai|duoi nguoi|di bo|gian co|xoay vai|tha long vai)\b"),
    "riddle": re.compile(r"\bcau do\b"),
    "tiny_skill": re.compile(r"\b(?:gap giay|gap mot|thuyen giay|may bay giay|hac giay)\b"),
}


# Meta-remarks about replying add nothing; the message itself must already feel optional.
_FILLER = re.compile(
    r"\bkhong (?:can|phai|nhat thiet)(?: phai)? (?:tra loi|rep|hoi am)\b|\bkhong tra loi cung duoc\b"
    r"|\b(?:co the|thi|cu) bo qua\b|\bbo qua (?:cau hoi|tin|loi hoi tham) nay\b"
)


def has_filler(text: str) -> bool:
    return bool(_FILLER.search(fold(text)))


class ProactiveReply(CompanionReply):
    model_config = ConfigDict(alias_generator=None)
    messages: list[Bubble] = Field(min_length=1, max_length=MAX_PROACTIVE_BUBBLES)

    @model_validator(mode="after")
    def short(self):
        if sum(len(bubble.text) for bubble in self.messages) > MAX_PROACTIVE_CHARS:
            raise ValueError("check-in too long")
        return self


class RureProactiveReply(ProactiveReply):
    challenge_kind: ChallengeKind


class NhipProactiveReply(ProactiveReply):
    source_entry_ids: list[UUID] = Field(default_factory=list, max_length=3)


def output_type(bot_id: str) -> type[ProactiveReply]:
    if caps(bot_id).journal:
        return NhipProactiveReply
    if caps(bot_id).challenges:
        return RureProactiveReply
    return ProactiveReply


class InvalidOutput(Exception):
    """Schema-valid but violates check-in rules; one regeneration is allowed."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class GuardrailBlocked(Exception):
    """Unsafe or unreceipted content: never shown, never retried."""


@dataclass(frozen=True)
class Validated:
    parts: list[AiOutput]
    source_ids: tuple[UUID, ...] = ()
    challenge_kind: str | None = None


def fold(text: str) -> str:
    lowered = text.lower().replace("đ", "d")
    return "".join(c for c in unicodedata.normalize("NFD", lowered) if not unicodedata.combining(c))


def validate_proactive(output: ProactiveReply, payload) -> Validated:
    """Every rule the model can break, checked on every bubble before anything is saved."""
    bot_id = payload.bot_id
    texts = [bubble.text for bubble in output.messages]
    folded = [fold(text) for text in texts]
    if any(_DURABLE_CLAIM.search(text) for text in texts) or distress_screen(texts):
        raise GuardrailBlocked()
    if sum(text.count("?") for text in texts) > 1:
        raise InvalidOutput("too_many_questions")
    if any(has_filler(text) for text in texts):
        raise InvalidOutput("filler")
    if any(has_journal_link(text) or _LINK.search(text) for text in texts):
        raise InvalidOutput("link_in_text")
    cards = [card for bubble in output.messages for card in bubble.cards]
    if len(cards) > 1 or any(card.kind not in ALLOWED_CARDS.get(bot_id, set()) for card in cards):
        raise InvalidOutput("card_not_allowed")
    sources: tuple[UUID, ...] = ()
    if caps(bot_id).journal:
        claimed = list(dict.fromkeys(getattr(output, "source_entry_ids", [])))
        digests = {digest.entry_id: digest for digest in payload.digests}
        if not digests:
            if claimed:
                raise InvalidOutput("unsupported_source")
            if any(_YESTERDAY.search(text) or _JOURNAL_CLAIM.search(text) for text in folded):
                # No saved entry was provided: any "yesterday you…" is invented.
                raise InvalidOutput("invented_journal")
        else:
            if not claimed or any(identity not in digests for identity in claimed):
                raise InvalidOutput("unsupported_source")
            if any(_WRONG_DAY.search(text) for text in folded):
                raise InvalidOutput("wrong_day")
            sources = tuple(claimed)
    if caps(bot_id).connection and any(_MATCH_CLAIM.search(text) for text in folded):
        raise InvalidOutput("matching_claim")
    kind = getattr(output, "challenge_kind", None)
    if caps(bot_id).challenges:
        content = " ".join(folded)
        if kind in payload.avoid_kinds or any(
            avoided != kind and avoided in _KIND_HINTS and _KIND_HINTS[avoided].search(content)
            for avoided in payload.avoid_kinds
        ):
            raise InvalidOutput("repeated_challenge")
    parts = [AiOutput(text=bubble.text, cards=bubble.cards) for bubble in output.messages]
    if sources:
        digests = {digest.entry_id: digest for digest in payload.digests}
        links = " · ".join(
            f"[{digests[identity].local_date:%d/%m/%Y}](/self/entry/{identity})" for identity in sources
        )
        last = parts[-1]
        parts[-1] = AiOutput(text=last.text + "\n\nBài viết đã tham khảo: " + links, cards=last.cards)
    return Validated(parts=parts, source_ids=sources, challenge_kind=kind)
