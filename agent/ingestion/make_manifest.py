"""Write corpus/manifest.toml from the front matter of every card.

Cards under ``authored/`` are ``licence_class = "authored"``. Cards under ``legal/`` are
transcriptions of official legal text and are ``open_reuse``; their source row must carry the
reuse evidence (``load_source`` enforces it). The manifest is derived, never edited by hand:
rerun this after adding or changing a card.

    uv run python agent/ingestion/make_manifest.py
"""

from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CORPUS = ROOT / "corpus"
EXCLUSION_REASON = "Bài format scenario hoặc quiz là hoạt động tương tác, không đưa vào truy hồi."


def _front_matter(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n").lstrip("﻿")
    if not text.startswith("+++"):
        raise ValueError(f"{path.name} has no TOML front matter")
    end = text.find("\n+++", 3)
    if end < 0:
        raise ValueError(f"{path.name} has unterminated front matter")
    return tomllib.loads(text[3:end])


def _q(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _arr(values: list[str]) -> str:
    return "[" + ", ".join(_q(v) for v in values) + "]"


def build() -> str:
    lines = [
        'version_label = "kb-authored"',
        "",
        "[[exclusion]]",
        'legacy_article_id = "scenario-or-quiz"',
        f"reason = {_q(EXCLUSION_REASON)}",
        "",
    ]
    entries: list[tuple[str, list[str]]] = []
    for folder, licence in (("authored", "authored"), ("legal", "open_reuse")):
        for path in sorted((ROOT / folder).glob("*.md")):
            meta = _front_matter(path)
            document_id = str(meta["document_id"])
            if document_id != path.stem and folder == "authored":
                raise ValueError(f"{path.name}: document_id must match the file name")
            block = [
                "[[document]]",
                f"document_id = {_q(document_id)}",
                f"source_id = {_q(str(meta['source_id']))}",
                f"path = {_q(f'../{folder}/{path.name}')}",
                f"topics = {_arr([str(t) for t in meta['topics']])}",  # type: ignore[union-attr]
                f"last_reviewed = {meta['last_reviewed']}",
                f"licence_class = {_q(licence)}",
                "",
            ]
            entries.append((document_id, block))
    for _document_id, block in sorted(entries):
        lines.extend(block)
    return "\n".join(lines)


if __name__ == "__main__":
    target = CORPUS / "manifest.toml"
    target.write_text(build(), encoding="utf-8", newline="\n")
    print("wrote", target.relative_to(ROOT.parent.parent))
