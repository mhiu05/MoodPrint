"""Heading-aware chunker for Vietnamese guidance and legal articles."""

from __future__ import annotations

import hashlib
import math

from moodprint_agent.knowledge.ingest.models import Block, ChunkDraft, ChunkParams, ParsedDocument
from moodprint_agent.knowledge.query import split_sentences

_ARTICLE = __import__("re").compile(r"^(Điều\s+\d+|Khoản\s+\d+)")


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _draft(
    document_id: str,
    ordinal: int,
    heading: str,
    section_path: list[str],
    text: str,
    start: int,
    parser: str,
    params: ChunkParams,
) -> ChunkDraft:
    oversize = len(text) > params.hard_max
    short = len(text) < params.preferred_min
    return ChunkDraft(
        chunk_id=f"{document_id}#{ordinal:03d}-{_sha(text)[:8]}",
        document_id=document_id,
        ordinal=ordinal,
        heading=heading,
        section_path=section_path,
        text=text,
        char_start=start,
        char_end=start + len(text),
        token_estimate=max(1, math.ceil(len(text) / 3)),
        content_sha256=_sha(text),
        parser=parser,
        oversize=oversize,
        short=short,
    )


def _pack(units: list[str], params: ChunkParams) -> list[tuple[str, bool]]:
    chunks: list[tuple[str, bool]] = []
    current: list[str] = []
    size = 0

    def flush() -> None:
        nonlocal current, size
        if current:
            chunks.append((" ".join(current), False))
            current = []
            size = 0

    for unit in units:
        if len(unit) > params.oversize_max:
            flush()
            for start in range(0, len(unit), params.oversize_max):
                chunks.append((unit[start : start + params.oversize_max], True))
            continue
        if len(unit) > params.hard_max:
            flush()
            chunks.append((unit, True))
            continue
        if current and size + 1 + len(unit) > params.target_max:
            flush()
        current.append(unit)
        size = len(" ".join(current))
        if size >= params.target_min:
            overlap = split_sentences(current[-1])[-1] if current else ""
            flush()
            if overlap and overlap != unit:
                current = [overlap]
                size = len(overlap)
    flush()
    return [(text, flag) for text, flag in chunks if text.strip()]


def chunk_document(document: ParsedDocument, params: ChunkParams, parser: str) -> list[ChunkDraft]:
    path: list[str] = []
    heading = ""
    bucket: list[str] = []
    drafts: list[ChunkDraft] = []
    cursor = 0

    def emit() -> None:
        nonlocal bucket, cursor
        if not bucket:
            return
        text = " ".join(bucket).strip()
        bucket = []
        if not text:
            return
        legal = bool(_ARTICLE.match(heading))
        units = [text] if legal and len(text) <= params.oversize_max else split_sentences(text)
        if not units:
            units = [text]
        packed = _pack(units, params)
        for piece, oversize in packed:
            if len(piece) < params.short_min:
                continue
            draft = _draft(
                document.document_id,
                len(drafts),
                heading,
                list(path),
                piece,
                cursor,
                parser,
                params,
            )
            if oversize:
                draft = draft.model_copy(update={"oversize": True})
            drafts.append(draft)
            cursor += len(piece)

    for block in document.blocks:
        if block.kind == "heading":
            emit()
            heading = block.text
            path = path[: max(block.level - 1, 0)] + [block.text]
            continue
        bucket.append(block.text)
    emit()
    if not drafts and document.blocks:
        text = " ".join(block.text for block in document.blocks if block.kind != "heading").strip()
        if len(text) >= params.short_min:
            drafts.append(_draft(document.document_id, 0, heading, path, text, 0, parser, params))
    return drafts


def blocks_from_markdown(body: str) -> list[Block]:
    blocks: list[Block] = []
    paragraph: list[str] = []

    def flush() -> None:
        if paragraph:
            blocks.append(Block(kind="paragraph", text=" ".join(paragraph)))
            paragraph.clear()

    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            flush()
            continue
        if stripped.startswith("#"):
            flush()
            marks = len(stripped) - len(stripped.lstrip("#"))
            blocks.append(Block(kind="heading", text=stripped[marks:].strip(), level=marks))
            continue
        paragraph.append(stripped)
    flush()
    return blocks
