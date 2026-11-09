"""Authenticated read models for the Knowledge Hub."""

from __future__ import annotations

from datetime import date

from moodprint_shared.contracts.base import FrozenDTO
from pydantic import RootModel


class CitationRead(FrozenDTO):
    source_id: str
    document_id: str
    title: str
    publisher: str
    url: str | None
    section: str | None
    published_at: date | None
    last_reviewed: date | None
    applicability: str
    country_scope: list[str]


class ChunkRead(FrozenDTO):
    chunk_id: str
    text: str
    score: float
    match_kind: str
    citation: CitationRead


class SearchRead(FrozenDTO):
    status: str
    corpus_version: str
    mode: str
    degraded: bool
    latency_ms: int
    chunks: list[ChunkRead]


class SectionRead(FrozenDTO):
    heading: str
    text: str


class DocumentRead(FrozenDTO):
    document_id: str
    title: str
    sections: list[SectionRead]
    citation: CitationRead
    derived_from: list[dict[str, str]]


class SourceRead(FrozenDTO):
    source_id: str
    publisher: str
    title: str
    url: str | None
    verified_on: date
    country_scope: list[str]
    licence_class: str


class SourceList(RootModel[list[SourceRead]]):
    pass


class CorpusRead(FrozenDTO):
    version: str
    documents: int
    chunks: int
    published_at: date | None
