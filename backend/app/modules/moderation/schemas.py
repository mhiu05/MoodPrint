from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.contracts import DTO, ShortText, VersionInput

IdentityKind = Literal["displayName", "gender"]


class IdentityEdit(VersionInput):
    field: IdentityKind
    value: str = Field(min_length=1, max_length=40)


class IdentityView(DTO):
    field: IdentityKind
    value: str
    version: int


class RevealInput(DTO):
    field: IdentityKind
    owner_side: Literal["self", "peer"]
    expected_identity_version: int = Field(ge=0)


class RevealDecision(VersionInput):
    preview_digest: str = Field(min_length=1, max_length=64)


class RevealView(DTO):
    id: UUID
    field: IdentityKind
    owner_side: Literal["self", "peer"]
    status: str
    version: int
    identity_version: int
    expires_at: datetime
    preview_value: str | None = None
    preview_digest: str | None = None


class ReportInput(DTO):
    peer_ref: UUID
    reason: ShortText
    selected_message_ids: list[UUID] = Field(default_factory=list, max_length=2)


class ReportView(DTO):
    id: UUID
    status: str
    created_at: datetime


class PeerReferenceView(DTO):
    peer_ref: UUID
