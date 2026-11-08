"""Parsers for HTML, PDF, Markdown, and plain text. No network."""

from __future__ import annotations

from bs4 import BeautifulSoup
from pypdf import PdfReader

from moodprint_agent.knowledge.ingest.chunk import blocks_from_markdown
from moodprint_agent.knowledge.ingest.models import Block, ParsedDocument


def parse_html(document_id: str, payload: bytes) -> ParsedDocument:
    soup = BeautifulSoup(payload, "lxml")
    for tag in soup.find_all(["script", "style", "nav", "footer", "noscript", "form"]):
        tag.decompose()
    blocks: list[Block] = []
    for node in soup.find_all(["h1", "h2", "h3", "h4", "p", "li"]):
        text = node.get_text(" ", strip=True)
        if not text:
            continue
        if node.name.startswith("h"):
            blocks.append(Block(kind="heading", text=text, level=int(node.name[1])))
        else:
            blocks.append(Block(kind="paragraph", text=text))
    return ParsedDocument(document_id=document_id, blocks=blocks, meta={"parser": "html"})


def parse_pdf(document_id: str, payload: bytes) -> ParsedDocument:
    reader = PdfReader(__import__("io").BytesIO(payload))
    blocks: list[Block] = []
    for number, page in enumerate(reader.pages, start=1):
        raw = page.extract_text() or ""
        if raw.count("\ufffd") / max(len(raw), 1) > 0.005:
            raise ValueError("pdf replacement-character rate exceeded 0.5%")
        for paragraph in raw.split("\n\n"):
            text = paragraph.strip()
            if text:
                blocks.append(Block(kind="paragraph", text=text, page=number))
    return ParsedDocument(document_id=document_id, blocks=blocks, meta={"parser": "pdf"})


def parse_markdown(document_id: str, payload: str) -> tuple[dict[str, object], ParsedDocument]:
    meta, body = split_front_matter(payload)
    return meta, ParsedDocument(
        document_id=document_id,
        blocks=blocks_from_markdown(body),
        meta={"parser": "markdown"},
    )


def parse_text(document_id: str, payload: str) -> ParsedDocument:
    blocks = [Block(kind="paragraph", text=part) for part in payload.split("\n\n") if part.strip()]
    return ParsedDocument(document_id=document_id, blocks=blocks, meta={"parser": "text"})


def split_front_matter(payload: str) -> tuple[dict[str, object], str]:
    text = payload.lstrip("\ufeff")
    if text.startswith("+++"):
        end = text.find("\n+++", 3)
        if end < 0:
            raise ValueError("unterminated TOML front matter")
        import tomllib

        meta = tomllib.loads(text[3:end])
        body = text[end + 4 :]
        return meta, body.lstrip("\n")
    return {}, text
