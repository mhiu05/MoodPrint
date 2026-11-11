"""Normalize parsed blocks to stable NFC text."""

from __future__ import annotations

import re

from safevoice_agent.knowledge.ingest.models import Block, ParsedDocument
from safevoice_agent.knowledge.textnorm import clean_text

_HYPHEN_BREAK = re.compile(r"(\w)-\n(\w)")
_NEWLINE_SPACE = re.compile(r"[ \t]*\n[ \t]*")


def normalize_blocks(document: ParsedDocument) -> ParsedDocument:
    blocks: list[Block] = []
    for block in document.blocks:
        text = block.text.replace("\u00ad", "")
        text = _HYPHEN_BREAK.sub(r"\1\2", text)
        text = _NEWLINE_SPACE.sub(" ", text)
        text = clean_text(text)
        if text:
            blocks.append(block.model_copy(update={"text": text}))
    return document.model_copy(update={"blocks": blocks})
