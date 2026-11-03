from typing import Literal

from pydantic import Field, field_validator

from app.ai.schemas import Card, public_https_url
from app.contracts import DTO


class SearchSource(DTO):
    source_id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=200)
    url: str = Field(max_length=2048)
    excerpt: str = Field(default="", max_length=600)

    @field_validator("url")
    @classmethod
    def safe_url(cls, value):
        return public_https_url(value)


class GroundedSegment(DTO):
    text: str = Field(min_length=1, max_length=1500)
    source_ids: list[str] = Field(default_factory=list, max_length=8)


class GroundedBubble(DTO):
    segments: list[GroundedSegment] = Field(min_length=1, max_length=12)
    cards: list[Card] = Field(default_factory=list, max_length=3)


class GroundedReply(DTO):
    messages: list[GroundedBubble] = Field(min_length=1, max_length=4)


class WebSearchResult(DTO):
    status: Literal["completed", "empty", "unavailable", "needs_query", "unsupported_topic"]
    text: str = Field(default="", max_length=6000)
    sources: list[SearchSource] = Field(default_factory=list, max_length=8)
    calls: int = Field(default=0, ge=0, le=1)
    input_tokens: int = Field(default=0, ge=0)
    cached_input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
