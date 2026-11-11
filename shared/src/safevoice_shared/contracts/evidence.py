from datetime import datetime
from typing import Literal, Protocol
from uuid import UUID

from pydantic import Field, JsonValue

from .auth import AuthContext
from .base import FrozenDTO

ReadPurpose = Literal["user_download", "user_preview", "evidence_analysis", "school_share"]
EvidenceKind = Literal["image", "audio", "video", "document", "text_note", "other"]
DerivativeKind = Literal["thumbnail", "ocr_text", "transcript", "ai_analysis"]


class EvidenceMeta(FrozenDTO):
    id: UUID
    owner_id: UUID
    case_id: UUID | None = None
    kind: EvidenceKind
    origin: Literal["user_upload", "user_entered"]
    original_filename: str | None = None
    declared_mime_type: str | None = None
    stored_mime_type: str | None = None
    byte_size: int | None = Field(default=None, ge=0)
    client_sha256: str | None = None
    original_text: str | None = None
    shown_timestamp: str = ""
    captured_at_label: str = ""
    user_edited_text: str | None = None
    review_status: Literal["unreviewed", "corrected", "confirmed", "rejected"] = "unreviewed"
    limitations: list[str] = Field(default_factory=list[str])
    upload_status: Literal["pending", "uploaded", "failed", "deleting"]
    created_at: datetime
    updated_at: datetime


class SignedRead(FrozenDTO):
    url: str
    expires_at: datetime


class DerivativeCreate(FrozenDTO):
    id: UUID
    kind: DerivativeKind
    content: JsonValue = None
    storage_key: str | None = None
    generator: str
    generator_version: str
    source_sha256: str | None = None


class EvidenceDerivative(DerivativeCreate):
    evidence_id: UUID
    owner_id: UUID
    created_at: datetime


class EvidenceService(Protocol):
    async def list_for_case(self, auth: AuthContext, case_id: UUID) -> list[EvidenceMeta]: ...
    async def get(self, auth: AuthContext, evidence_id: UUID) -> EvidenceMeta: ...
    async def open_read_url(
        self, auth: AuthContext, evidence_id: UUID, purpose: ReadPurpose
    ) -> SignedRead: ...
    async def add_derivative(
        self, auth: AuthContext, evidence_id: UUID, data: DerivativeCreate
    ) -> EvidenceDerivative: ...
