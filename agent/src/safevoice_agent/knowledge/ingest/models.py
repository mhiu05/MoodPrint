"""Frozen ingest records."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class AcquireSpec(Frozen):
    url: str
    allow_hosts: list[str]
    expected_sha256: str | None = None
    kind: str = "html"


class SourceSpec(Frozen):
    source_id: str
    kind: str
    publisher: str
    title: str
    url: str | None = None
    language: str
    country_scope: list[str]
    authority_tier: int = Field(ge=1, le=4)
    licence_class: str
    licence_note: str
    licence_quote: str | None = None
    verified_on: date | None = None
    retrieved_on: date | None = None
    acquire: AcquireSpec | None = None
    authority: int = 0
    relevance: int = 0
    licence: int = 0
    language_score: int = 0
    applicability_score: int = 0
    freshness: int = 0
    evidence: str = ""


class DerivedFrom(Frozen):
    source_id: str
    locator: str


class DocumentSpec(Frozen):
    document_id: str
    source_id: str
    title: str
    topics: list[str]
    age_bands: list[str] = Field(default_factory=list)
    published_at: date | None = None
    last_reviewed: date
    applicability: str
    derived_from: list[DerivedFrom] = Field(default_factory=lambda: list[DerivedFrom]())
    legacy_article_id: str | None = None
    primary_url: str | None = None
    language: str = "vi"
    country_scope: list[str] = Field(default_factory=lambda: ["VN"])
    path: str | None = None
    licence_class: str = "authored"


class ChunkParams(Frozen):
    target_min: int = 600
    target_max: int = 1100
    hard_max: int = 1400
    oversize_max: int = 1800
    short_min: int = 40
    preferred_min: int = 200


class Block(Frozen):
    kind: str
    text: str
    level: int = 0
    page: int | None = None


class ParsedDocument(Frozen):
    document_id: str
    blocks: list[Block]
    meta: dict[str, str] = Field(default_factory=dict)


class ChunkDraft(Frozen):
    chunk_id: str
    document_id: str
    ordinal: int
    heading: str
    section_path: list[str]
    text: str
    char_start: int
    char_end: int
    token_estimate: int
    content_sha256: str
    parser: str
    oversize: bool = False
    short: bool = False


class CorpusManifest(Frozen):
    version_label: str = ""
    sources: list[SourceSpec]
    documents: list[DocumentSpec]
    params: ChunkParams = Field(default_factory=ChunkParams)
    exclusions: list[dict[str, str]] = Field(default_factory=lambda: list[dict[str, str]]())
