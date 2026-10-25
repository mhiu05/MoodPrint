from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.contracts import DTO, MessageText, VersionInput
from app.modules.matching.scoring import _GOALS, _INTERESTS, _LANGUAGES, _STYLES, _VALUES


class PublicProfile(DTO):
    interests: list[str] = Field(default_factory=list, max_length=20)
    values: list[str] = Field(default_factory=list, max_length=20)
    style: str = "balanced"
    goal: str = "friendship"
    languages: list[str] = Field(default_factory=list, max_length=5)

    @field_validator("interests", "values", "languages")
    @classmethod
    def known_unique_tags(cls, value: list[str], info):
        allowed = {"interests": _INTERESTS, "values": _VALUES, "languages": _LANGUAGES}[
            info.field_name
        ]
        if len(value) != len(set(value)) or any(tag not in allowed for tag in value):
            raise ValueError("Unknown or duplicate taxonomy tag")
        return value

    @field_validator("style", "goal")
    @classmethod
    def known_option(cls, value: str, info):
        if value not in (_STYLES if info.field_name == "style" else _GOALS):
            raise ValueError("Unknown taxonomy option")
        return value


class DraftInput(PublicProfile, VersionInput):
    pass


class DraftView(DTO):
    profile: PublicProfile
    version: int
    published_version: int = 0


class PreviewView(DTO):
    profile: PublicProfile
    draft_version: int
    preview_digest: str


class PublishInput(DTO):
    draft_version: int = Field(ge=1)
    preview_digest: str = Field(min_length=1, max_length=64)
    expected_published_version: int = Field(ge=0)


class PublishedView(DTO):
    id: UUID
    profile: PublicProfile
    version: int
    # needs_republish: kept for review but invisible to matching until published again
    # (e.g. after MATCH consent was withdrawn and restored). Never republished implicitly.
    state: Literal["live", "needs_republish"] = "live"
    # The version withdraw/publish must send as expectedVersion.
    profile_version: int


class CandidateCardDTO(DTO):
    candidate_ref: UUID
    alias: str
    avatar_seed: str
    profile: PublicProfile
    reasons: list[str] = Field(max_length=3)
    scoring_version: Literal["rules-v1-id"] = "rules-v1-id"
    profile_version: int
    peer_version: int


class CandidateListDTO(DTO):
    candidates: list[CandidateCardDTO] = Field(max_length=5)


class CandidateInput(DTO):
    candidate_ref: UUID


class BlockInput(DTO):
    peer_ref: UUID


class PeerCardDTO(DTO):
    """The counterpart's public card on a pending request (DR-07); never private data."""

    alias: str
    avatar_seed: str
    profile: PublicProfile
    reasons: list[str] = Field(max_length=3)
    match_label: Literal["many", "some"]


class RequestView(DTO):
    id: UUID
    status: str
    version: int
    direction: Literal["incoming", "outgoing"]
    expires_at: datetime
    connection_id: UUID | None = None
    # Only while the request is pending and the pair is still eligible.
    peer: PeerCardDTO | None = None


class ConnectionView(DTO):
    id: UUID
    alias: str
    status: str
    version: int
    high_water_seq: str


class MessageInput(DTO):
    client_message_id: UUID
    text: MessageText


class MessageView(DTO):
    id: UUID
    connection_id: UUID
    client_message_id: UUID
    sender: Literal["self", "peer"]
    text: str
    seq: str
    accepted_at: datetime


class MessagePage(DTO):
    messages: list[MessageView]
    high_water_seq: str
