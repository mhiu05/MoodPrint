"""Model-facing check-in outputs and the business validator (phase-1/05 §6)."""

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, Field, model_validator

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
ALLOWED_CARDS = {"nhip": {"mood_form"}, "caunoi": {"discovery"}}
_LINK = re.compile(r"\]\s*\(|https?://|www\.|javascript:|data:", re.I)
_YESTERDAY = re.compile(r"\bhom qua\b")
_MATCH_CLAIM = re.compile(
    r"\d+\s*%|phan tram|da ket noi|loi moi da (?:duoc )?gui|da gui loi moi|da tim (?:thay|duoc)"
    r"|(?:rat|cuc|hoan toan) (?:hop|tuong hop)"
)


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
    if bot_id == "nhip":
        return NhipProactiveReply
    if bot_id == "rure":
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
    if any(has_journal_link(text) or _LINK.search(text) for text in texts):
        raise InvalidOutput("link_in_text")
    cards = [card for bubble in output.messages for card in bubble.cards]
    if len(cards) > 1 or any(card.kind not in ALLOWED_CARDS.get(bot_id, set()) for card in cards):
        raise InvalidOutput("card_not_allowed")
    sources: tuple[UUID, ...] = ()
    if bot_id == "nhip":
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
            sources = tuple(claimed)
    if bot_id == "caunoi" and any(_MATCH_CLAIM.search(text) for text in folded):
        raise InvalidOutput("matching_claim")
    kind = getattr(output, "challenge_kind", None)
    if bot_id == "rure" and kind in payload.avoid_kinds:
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
