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


def _sections(document: ParsedDocument) -> list[tuple[str, list[str], str]]:
    """(heading, heading path, body text) per heading; text before any heading has heading ""."""
    sections: list[tuple[str, list[str], str]] = []
    path: list[str] = []
    heading = ""
    bucket: list[str] = []

    def close() -> None:
        text = " ".join(bucket).strip()
        if text:
            sections.append((heading, list(path), text))
        bucket.clear()

    for block in document.blocks:
        if block.kind == "heading":
            close()
            heading = block.text
            path = path[: max(block.level - 1, 0)] + [block.text]
            continue
        bucket.append(block.text)
    close()
    return sections


def _inline_heading(heading: str) -> str:
    return heading.rstrip(" .:;,") + "."


def _merge_groups(
    sections: list[tuple[str, list[str], str]], params: ChunkParams
) -> list[list[tuple[str, list[str], str]]]:
    """Group neighbouring short sections so a chunk reaches the target size.

    A group only grows while it is below ``target_min`` and the merged text stays within
    ``target_max``. Legal articles (Điều/Khoản headings) are hard boundaries so a citation keeps
    pointing at one provision.
    """
    groups: list[list[tuple[str, list[str], str]]] = []
    for section in sections:
        heading, _path, text = section
        if groups:
            last = groups[-1]
            last_len = sum(len(part[2]) for part in last) + sum(
                len(_inline_heading(part[0])) + 2 for part in last[1:]
            )
            joined = last_len + len(_inline_heading(heading)) + len(text) + 2
            mergeable = (
                last_len < params.target_min
                and joined <= params.target_max
                and not _ARTICLE.match(heading)
                and not _ARTICLE.match(last[0][0])
                and bool(heading)
            )
            if mergeable:
                last.append(section)
                continue
        groups.append([section])
    return groups


def chunk_document(document: ParsedDocument, params: ChunkParams, parser: str) -> list[ChunkDraft]:
    drafts: list[ChunkDraft] = []
    cursor = 0
    for group in _merge_groups(_sections(document), params):
        heading, path, first_text = group[0]
        if len(group) == 1:
            legal = bool(_ARTICLE.match(heading))
            units = (
                [first_text]
                if legal and len(first_text) <= params.oversize_max
                else split_sentences(first_text)
            )
            packed = _pack(units or [first_text], params)
        else:
            merged = [first_text] + [f"{_inline_heading(part[0])} {part[2]}" for part in group[1:]]
            packed = [(" ".join(merged), False)]
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
    if not drafts and document.blocks:
        text = " ".join(block.text for block in document.blocks if block.kind != "heading").strip()
        if len(text) >= params.short_min:
            drafts.append(_draft(document.document_id, 0, "", [], text, 0, parser, params))
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
