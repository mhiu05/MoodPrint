from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.contracts import DTO, MessageText, VersionInput
from app.modules.profiles.taxonomy import (
    ACTIVITIES,
    AVAILABILITY,
    GOALS,
    INTERESTS,
    LANGUAGES,
    LIMITS,
    STYLES,
    VALUES,
)


class PublicProfile(DTO):
    """The only data another member can see or be matched on (taxonomy v2 tags).

    v1 payloads (without activities, availability, strictGoal) remain valid.
    Maximums apply to drafts; minimums are enforced when publishing.
    """

    interests: list[str] = Field(default_factory=list, max_length=LIMITS["interests"][1])
    values: list[str] = Field(default_factory=list, max_length=LIMITS["values"][1])
    style: str = "balanced"
    goal: str = "friendship"
    languages: list[str] = Field(default_factory=list, max_length=LIMITS["languages"][1])
    activities: list[str] = Field(default_factory=list, max_length=LIMITS["activities"][1])
    availability: list[str] = Field(default_factory=list, max_length=LIMITS["availability"][1])
    # Only show people with the same goal (applied to both sides).
    strict_goal: bool = False

    @field_validator("interests", "values", "languages", "activities", "availability")
    @classmethod
    def known_unique_tags(cls, value: list[str], info):
        allowed = {
            "interests": INTERESTS,
            "values": VALUES,
            "languages": LANGUAGES,
            "activities": ACTIVITIES,
            "availability": AVAILABILITY,
        }[info.field_name]
        if len(value) != len(set(value)) or any(tag not in allowed for tag in value):
            raise ValueError("Unknown or duplicate taxonomy tag")
        return value

    @field_validator("style", "goal")
    @classmethod
    def known_option(cls, value: str, info):
        if value not in (STYLES if info.field_name == "style" else GOALS):
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
    # stale: published more than 180 days ago, hidden from discovery until reconfirmed.
    state: Literal["live", "needs_republish", "stale"] = "live"
    # The version withdraw/publish must send as expectedVersion.
    profile_version: int


class CandidateCardDTO(DTO):
    candidate_ref: UUID
    alias: str
    avatar_seed: str
    profile: PublicProfile
    reasons: list[str] = Field(max_length=3)
    # Qualitative only: never a score or percentage (DR-05).
    match_label: Literal["many", "some"] = "some"
    shared_activities: list[str] = Field(default_factory=list, max_length=4)
    scoring_version: Literal["rules-v1", "rules-v2"] = "rules-v1"
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
    created_at: datetime | None = None
    # Inbox signals for the viewer only (read markers are never shown to the peer).
    unread_count: int = 0
    last_message_at: datetime | None = None
    last_message_preview: str | None = Field(default=None, max_length=80)
    last_message_sender: Literal["self", "peer"] | None = None
    # Kind of the room's invited/active/paused shared activity, if any.
    active_activity: Literal["icebreaker", "coop_quiz", "focus"] | None = None


class ReadInput(DTO):
    seq: str = Field(pattern=r"^\d{1,19}$")


class ReadView(DTO):
    last_read_seq: str


class SocialSummaryView(DTO):
    pending_incoming_requests: int = 0
    unread_connections: int = 0
    activity_invites: int = 0


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
