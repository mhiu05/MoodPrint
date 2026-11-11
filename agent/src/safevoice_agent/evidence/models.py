"""Structured evidence reading. Observation, interpretation and uncertainty stay separate.

Nothing here is a verified fact: ``extracted_text`` is what the model *read*, ``inferences`` are
labelled guesses and ``needs_user_review`` is always true. The user's own correction lives in a
different place (``evidence_items.user_edited_text``) and never overwrites this reading.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Confidence = Literal["high", "medium", "low"]
TEXT_CAP = 700
LIST_CAP = 12


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ExtractedText(_Frozen):
    text: str = Field(max_length=2000)
    confidence: Confidence
    region: str | None


class Inference(_Frozen):
    text: str = Field(max_length=600)
    basis: str = Field(max_length=400)
    confidence: Confidence


class VisibleMetadata(_Frozen):
    timestamp_text: str | None
    platform_guess: str | None
    participants_as_shown: list[str]


class EvidenceReading(_Frozen):
    extracted_text: list[ExtractedText]
    visible_metadata: VisibleMetadata
    observations: list[str]
    inferences: list[Inference]
    uncertainties: list[str]
    limitations: list[str]
    needs_user_review: Literal[True]


def reading_summary(reading: EvidenceReading) -> dict[str, Any]:
    """Text-only view for the Companion: no bytes, bounded, every guess still labelled."""
    return {
        "label": "Kết quả AI đọc ảnh — chưa được người dùng xác nhận",
        "extractedText": [
            {"text": item.text[:TEXT_CAP], "confidence": item.confidence}
            for item in reading.extracted_text[:LIST_CAP]
        ],
        "observations": [item[:300] for item in reading.observations[:LIST_CAP]],
        "aiGuesses": [
            {"text": item.text[:300], "confidence": item.confidence}
            for item in reading.inferences[:LIST_CAP]
        ],
        "uncertainties": [item[:300] for item in reading.uncertainties[:LIST_CAP]],
        "limitations": [item[:300] for item in reading.limitations[:LIST_CAP]],
        "needsUserReview": True,
    }
