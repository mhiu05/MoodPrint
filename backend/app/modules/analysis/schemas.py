"""Public representation of an evidence analysis. The model's reading is data, never a verdict."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from moodprint_agent.evidence.models import EvidenceReading
from moodprint_shared.contracts.base import FrozenDTO
from pydantic import Field

Confidence = Literal["high", "medium", "low"]


class ConsentIn(FrozenDTO):
    version: str = Field(min_length=1, max_length=80)
    accepted: bool


class AnalysisCreate(FrozenDTO):
    id: UUID
    evidence_id: UUID
    consent: ConsentIn


class ExtractedTextRead(FrozenDTO):
    text: str
    confidence: Confidence
    region: str | None


class InferenceRead(FrozenDTO):
    text: str
    basis: str
    confidence: Confidence


class VisibleMetadataRead(FrozenDTO):
    timestamp_text: str | None
    platform_guess: str | None
    participants_as_shown: list[str]


class ReadingRead(FrozenDTO):
    """Four separate layers: what was read, what is visible, what the AI guesses, what is unsure."""

    extracted_text: list[ExtractedTextRead]
    visible_metadata: VisibleMetadataRead
    observations: list[str]
    inferences: list[InferenceRead]
    uncertainties: list[str]
    limitations: list[str]
    needs_user_review: Literal[True] = True


class AnalysisRead(FrozenDTO):
    id: UUID
    evidence_id: UUID
    status: Literal["running", "succeeded", "failed", "cancelled"]
    consent_version: str
    derivative_id: UUID | None
    error_code: str | None
    reading: ReadingRead | None
    started_at: datetime
    finished_at: datetime | None


def reading_read(reading: EvidenceReading) -> ReadingRead:
    return ReadingRead.model_validate(reading.model_dump(mode="python"))
