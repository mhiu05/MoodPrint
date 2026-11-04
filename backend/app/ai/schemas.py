import ipaddress
import re
from datetime import date, datetime, timedelta
from typing import Annotated, Literal
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.contracts import DTO, BotId, MessageText, ShortText, VersionInput


class NavigateCard(DTO):
    kind: Literal["navigate_bot"]
    bot_id: BotId


class MoodCard(DTO):
    kind: Literal["mood_form"]


class DiscoveryCard(DTO):
    kind: Literal["discovery"]


class MapsSearchCard(DTO):
    kind: Literal["maps_search"]
    search_id: UUID


class PlaceResult(DTO):
    place_id: str | None = Field(default=None, max_length=200)
    name: str = Field(min_length=1, max_length=200)
    category: str | None = Field(default=None, max_length=100)
    address: str = Field(max_length=300)
    rating: float | None = Field(default=None, ge=0, le=5)
    rating_count: int | None = Field(default=None, ge=0)
    opening_hours: list[str] | None = Field(default=None, max_length=7)
    maps_url: str = Field(max_length=2048)
    fetched_at: datetime
    provider: Literal["apify"] = "apify"

    @field_validator("maps_url")
    @classmethod
    def safe_maps_url(cls, value):
        value = public_https_url(value)
        if urlsplit(value).hostname != "www.google.com" or not urlsplit(value).path.startswith("/maps/"):
            raise ValueError("invalid Maps URL")
        return value


class PlacesCard(DTO):
    kind: Literal["places"]
    places: list[PlaceResult] = Field(min_length=1, max_length=5)


Card = Annotated[NavigateCard | MoodCard | DiscoveryCard | MapsSearchCard | PlacesCard, Field(discriminator="kind")]


def public_https_url(value: str) -> str:
    if len(value) > 2048 or any(ord(c) < 33 or c in "\\" for c in value):
        raise ValueError("invalid source URL")
    url = urlsplit(value)
    host = (url.hostname or "").lower().rstrip(".")
    if (url.scheme != "https" or not host or url.username or url.password
            or url.port not in (None, 443) or "." not in host
            or host == "localhost" or host.endswith((".localhost", ".local", ".internal"))):
        raise ValueError("source must be public HTTPS")
    if not re.fullmatch(r"[a-z0-9.-]+", host) or all(re.fullmatch(r"(?:0x[0-9a-f]+|[0-9]+)", label) for label in host.split(".")):
        raise ValueError("invalid or alternative numeric source host")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        # Numeric/hex and bracket forms are not public DNS names.
        if all(c.isdigit() or c == "." for c in host) or ":" in host:
            raise ValueError("invalid source host") from None
    else:
        if not address.is_global:
            raise ValueError("private source host")
    return urlunsplit(("https", host, url.path or "/", url.query, ""))


class Citation(DTO):
    source_id: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    title: str = Field(min_length=1, max_length=200)
    url: str = Field(max_length=2048)
    start: int = Field(ge=0)
    end: int = Field(gt=0)

    @field_validator("url")
    @classmethod
    def safe_url(cls, value: str) -> str:
        return public_https_url(value)


SkillId = Literal["hangout", "learn-new-thing", "weekly-review", "mood-patterns", "guided-journal", "reframe-thought"]


class PromptOptions(DTO):
    skill_id: SkillId | None = None
    tools: list[Literal["web_search", "maps_search"]] = Field(default_factory=list, max_length=8)
    area: str | None = Field(default=None, min_length=2, max_length=120)
    maps_search_id: UUID | None = None

    @field_validator("tools")
    @classmethod
    def unique_tools(cls, value):
        return sorted(set(value))

    @field_validator("area", mode="before")
    @classmethod
    def normalized_area(cls, value):
        return " ".join(value.split()) if isinstance(value, str) else value


class AiOutput(DTO):
    text: str = Field(min_length=1, max_length=6000)
    cards: list[Card] = Field(default_factory=list, max_length=3)
    citations: list[Citation] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def citation_ranges(self):
        if any(c.start >= c.end or c.end > len(self.text) for c in self.citations):
            raise ValueError("citation outside visible text")
        return self


def drop_retired_cards(parts: list[AiOutput], bot_id: str) -> list[AiOutput]:
    from app.ai.agents import V3_IDS

    if bot_id not in V3_IDS:
        return parts
    return [part.model_copy(update={"cards": [card for card in part.cards if card.kind != "discovery"]})
            for part in parts]


MAX_BUBBLES = 4
MAX_BUBBLE_CHARS = 1500
# SSE v1 joins bubbles with "\n\n" and old clients reject a final text above 6000 chars.
MAX_REPLY_CHARS = 5900


class Bubble(DTO):
    """Model-facing: one short chat message of a multi-bubble reply."""

    text: str = Field(min_length=1, max_length=MAX_BUBBLE_CHARS)
    cards: list[Card] = Field(default_factory=list, max_length=3)

    @field_validator("text")
    @classmethod
    def visible(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("bubble must contain visible text")
        return value.strip()


class CompanionReply(DTO):
    """Model-facing: one turn is 1–4 bubbles, by default one. Not a public DTO."""

    messages: list[Bubble] = Field(min_length=1, max_length=MAX_BUBBLES)

    @model_validator(mode="after")
    def bounded(self):
        joined = sum(len(bubble.text) for bubble in self.messages) + 2 * (len(self.messages) - 1)
        if joined > MAX_REPLY_CHARS:
            raise ValueError("reply too long")
        if sum(len(bubble.cards) for bubble in self.messages) > 3:
            raise ValueError("at most 3 cards per reply")
        texts = [bubble.text.casefold() for bubble in self.messages]
        if len(set(texts)) != len(texts):
            raise ValueError("duplicate bubbles")
        return self


class AiReply(DTO):
    """Validated, backend-rendered reply: the parts persisted as one bubble each."""

    parts: list[AiOutput] = Field(min_length=1, max_length=MAX_BUBBLES)

    @model_validator(mode="after")
    def bounded(self):
        if sum(len(p.text) for p in self.parts) + 2 * (len(self.parts) - 1) > MAX_REPLY_CHARS:
            raise ValueError("reply too long")
        if sum(len(p.cards) for p in self.parts) > 3 or sum(len(p.citations) for p in self.parts) > 12:
            raise ValueError("reply exceeds cards/citations limit")
        if len({c.url for p in self.parts for c in p.citations}) > 8:
            raise ValueError("too many source URLs")
        return self

    def joined(self) -> AiOutput:
        """The ai-events-v1 / legacy single-message representation."""
        return AiOutput(
            text="\n\n".join(part.text for part in self.parts),
            cards=[card for part in self.parts for card in part.cards],
        )


class ConversationInput(DTO):
    bot_id: BotId
    persistent: bool | None = None


class AgentReturnInput(DTO):
    """V3: return a handed-over conversation to its own agent."""

    agent: Literal["dieuphoi"]
    expected_version: int = Field(ge=1)


class ConversationRename(DTO):
    title: str = Field(min_length=1, max_length=100)

    @field_validator("title")
    @classmethod
    def visible_title(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("title must contain visible text")
        return value


class ConversationHeader(DTO):
    conversation_id: UUID
    bot_id: BotId
    version: int
    expires_at: datetime
    persistent: bool = False
    title: str = "Cuộc trò chuyện mới"
    created_at: datetime | None = None
    updated_at: datetime | None = None
    # V3: the companion is one of the five legacy companions (history may be read-only).
    legacy: bool = False
    # V3 handoff: the specialist currently answering this conversation (None = bot_id).
    active_agent: Literal["dieuphoi", "nhatky", "hoatdong"] | None = None


class CollaborationSummary(DTO):
    """Public line of a completed, used consultation. ``summary`` is a backend template chosen
    by (edge, rule); never model text (ADR-11)."""

    kind: Literal["nhip_energy_for_rure", "nhip_habit_for_may", "rure_activity_for_guong"]
    companions: list[BotId] = Field(min_length=2, max_length=2)
    summary: str = Field(min_length=1, max_length=200)


class ReplyStep(DTO):
    """A receipt-backed specialist step of one reply (consulted or handed over)."""

    kind: Literal["consult", "handoff"]
    companion: Literal["nhatky", "hoatdong"]


class AIMessage(DTO):
    id: UUID
    actor: Literal["self", "bot"]
    text: str
    cards: list[Card] = Field(default_factory=list, max_length=3)
    citations: list[Citation] = Field(default_factory=list, max_length=8)
    source_backed: bool = False
    created_at: datetime | None = None
    run_id: UUID | None = None
    status: str | None = None
    # Bubble position within its run (legacy rows: part 0 of 1).
    part_index: int = Field(default=0, ge=0, le=MAX_BUBBLES - 1)
    part_count: int = Field(default=1, ge=1, le=MAX_BUBBLES)
    origin: Literal["user", "proactive"] = "user"
    proactive_slot: Literal["morning", "evening"] | None = None
    # Phase 2: backend-rendered line, only on part 0 of a run whose receipt is completed and used.
    collaboration: CollaborationSummary | None = None
    # V3: the companion whose run produced this bubble (handoff/group); None for the user.
    speaker: BotId | None = None
    # V3: on part 0 only — specialist steps that actually ran and were used for this reply.
    steps: list[ReplyStep] | None = None


class ConversationView(ConversationHeader):
    messages: list[AIMessage]
    active_run_id: UUID | None
    active_run_version: int | None = None
    has_more_messages: bool = False


class AiPreferenceInput(DTO):
    history_enabled: bool
    semantic_memory_enabled: bool
    expected_version: int = Field(ge=1)
    policy_version: Literal["ai-data-v1"]


class AiPreferenceView(DTO):
    history_enabled: bool
    semantic_memory_enabled: bool
    version: int
    policy_version: str
    retention_days: int
    history_available: bool
    semantic_memory_available: bool


class MoodReadScope(DTO):
    from_date: date
    to_date: date

    @model_validator(mode="after")
    def bounded_range(self):
        if not timedelta(0) <= self.to_date - self.from_date <= timedelta(days=89):
            raise ValueError("Select between one and 90 consecutive days")
        return self


class StartRunInput(DTO):
    text: MessageText
    client_message_id: UUID
    expected_conversation_version: int = Field(ge=1)
    mood_scope: MoodReadScope | None = None
    prompt_options: PromptOptions = Field(default_factory=PromptOptions)
    response_protocol: Literal[2, 3] = 2


def idempotency_input(body: StartRunInput) -> str:
    """Digest input of one send. A default (protocol 2, no options) send keeps the pre-search
    shape, so a retry spanning the rollout still matches its original turn."""
    fields = {"text", "mood_scope"}
    if body.prompt_options != PromptOptions() or body.response_protocol != 2:
        fields |= {"prompt_options", "response_protocol"}
    return body.model_dump_json(include=fields)


class AIRunAccepted(DTO):
    run_id: UUID
    conversation_id: UUID
    version: int
    run_version: int = 1
    events_url: str


class AIEvent(DTO):
    version: Literal["ai-events-v1", "ai-events-v2", "ai-events-v3"] = "ai-events-v1"
    seq: str = Field(pattern=r"^[1-9][0-9]*$")
    type: Literal["progress", "final", "completed", "failed", "cancelled"]
    data: dict


class AIReplyBubble(DTO):
    """One validated bubble of an ai-events-v2 final event."""

    message_id: UUID
    part_index: int = Field(ge=0, le=MAX_BUBBLES - 1)
    text: str
    cards: list[Card] = Field(default_factory=list, max_length=3)


class AIFinalV2(DTO):
    """ai-events-v2 final data; v1 receives the bubbles joined as {text, cards}."""

    part_count: int = Field(ge=1, le=MAX_BUBBLES)
    messages: list[AIReplyBubble] = Field(min_length=1, max_length=MAX_BUBBLES)


def final_v2(bubbles: list[tuple[UUID, str, list]], citations: list[list] | None = None, *, source_marked=False) -> dict:
    """Normalized final payload from (message id, text, JSON cards) in part order."""
    result = AIFinalV2(
        part_count=len(bubbles),
        messages=[
            AIReplyBubble(message_id=identity, part_index=index, text=text, cards=cards)
            for index, (identity, text, cards) in enumerate(bubbles)
        ],
    ).model_dump(mode="json", by_alias=True)
    if citations is not None and any(citations):
        for message, sources in zip(result["messages"], citations, strict=True):
            message["citations"] = sources
    if source_marked:
        for message in result["messages"]:
            message["sourceBacked"] = True  # Internal negotiation marker, removed below.
    return result


SEARCH_REFRESH = "Hãy tải lại ứng dụng để xem câu trả lời có nguồn."


def source_backed(data: dict) -> bool:
    return bool(data.get("sourceBacked") or data.get("citations") or any(c.get("kind") in ("maps_search", "places") for c in data.get("cards", [])))


def history_protocol(messages: list[AIMessage], protocol: int) -> list[AIMessage]:
    if protocol >= 3:
        return messages
    return [m.model_copy(update={"text": SEARCH_REFRESH, "cards": [], "citations": []})
            if m.source_backed or m.citations or any(c.kind in ("maps_search", "places") for c in m.cards) else m for m in messages]


def as_protocol(event: AIEvent, protocol: int, final: dict | None = None) -> AIEvent:
    """Render one stored event for the requested SSE protocol (default v1).

    ``final`` is the v2 final data of a live (temporary) run whose stored event is v1.
    """
    if event.type == "final":
        data = final if "messages" not in event.data and final is not None else event.data
        if "messages" in data:
            data = {**data, "messages": [dict(m) for m in data["messages"]]}
            if protocol < 3 and any(source_backed(m) for m in data["messages"]):
                data["messages"] = [{**m, "text": SEARCH_REFRESH, "cards": []} for m in data["messages"]]
            for m in data["messages"]:
                m.pop("sourceBacked", None)
                if protocol < 3:
                    m.pop("citations", None)
                else:
                    m.setdefault("citations", [])
        elif source_backed(data) and protocol < 3:
            data = {"text": SEARCH_REFRESH, "cards": []}
        event = event.model_copy(update={"data": data})
    if protocol >= 2:
        update: dict = {"version": f"ai-events-v{protocol}"}
        if event.type == "final" and "messages" not in event.data:
            if final is None:
                raise ValueError("v2 final requires its bubbles")
            update["data"] = final
        return event.model_copy(update=update)
    if event.type == "final" and "messages" in event.data:
        messages = event.data["messages"]
        joined = {
            "text": "\n\n".join(message["text"] for message in messages),
            "cards": [card for message in messages for card in message["cards"]],
        }
        return event.model_copy(update={"data": joined})
    return event.model_copy(update={"version": "ai-events-v1", "data": {k: v for k, v in event.data.items() if k != "citations"}})


class ProposalConfirm(VersionInput):
    edited_text: ShortText | None = None


class MemoryDTO(DTO):
    id: UUID
    bot_id: BotId
    text: str
    version: int
    status: str


class MemoryEdit(VersionInput):
    text: ShortText
