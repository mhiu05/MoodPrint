"""Deterministic offline build: parse, normalize, dedupe, chunk."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import cast

from safevoice_agent.knowledge.ingest.chunk import chunk_document
from safevoice_agent.knowledge.ingest.dedupe import DedupeItem, dedupe
from safevoice_agent.knowledge.ingest.manifest import load_manifest
from safevoice_agent.knowledge.ingest.models import DerivedFrom, DocumentSpec, ParsedDocument
from safevoice_agent.knowledge.ingest.normalize import normalize_blocks
from safevoice_agent.knowledge.ingest.parse import parse_markdown
from safevoice_agent.knowledge.textnorm import fold_vietnamese


def _document_from_card(spec: DocumentSpec) -> tuple[DocumentSpec, ParsedDocument, str]:
    payload = Path(spec.path or "").read_text(encoding="utf-8")
    meta, parsed = parse_markdown(spec.document_id, payload)
    raw_derived = meta.get("derived_from")
    derived_items: list[object]
    if isinstance(raw_derived, dict):
        derived_items = [raw_derived]
    elif isinstance(raw_derived, list):
        derived_items = [item for item in cast(list[object], raw_derived)]
    else:
        derived_items = []
    derived = [DerivedFrom.model_validate(item) for item in derived_items]
    updated = spec.model_copy(
        update={
            "title": str(meta.get("title") or spec.title),
            "topics": _strings(meta.get("topics"), spec.topics),
            "age_bands": _strings(meta.get("age_bands"), spec.age_bands),
            "applicability": str(meta.get("applicability") or spec.applicability),
            "language": str(meta.get("language") or spec.language),
            "country_scope": _strings(meta.get("country_scope"), spec.country_scope),
            "primary_url": meta.get("primary_url") or spec.primary_url,
            "legacy_article_id": meta.get("legacy_article_id") or spec.legacy_article_id,
            "source_id": str(meta.get("source_id") or spec.source_id),
            "derived_from": derived,
            "last_reviewed": meta.get("last_reviewed") or spec.last_reviewed,
        }
    )
    text = "\n".join(block.text for block in parsed.blocks)
    return updated, parsed, hashlib.sha256(fold_vietnamese(text).encode()).hexdigest()


def build_corpus(manifest_path: Path, out_dir: Path) -> dict[str, object]:
    manifest, digest = load_manifest(manifest_path)
    sources = {source.source_id: source for source in manifest.sources}
    built: list[tuple[DocumentSpec, ParsedDocument, str]] = []
    for spec in manifest.documents:
        built.append(_document_from_card(spec))
    decisions = dedupe(
        [
            DedupeItem(
                document_id=spec.document_id,
                text="\n".join(block.text for block in parsed.blocks),
                authority_tier=sources[spec.source_id].authority_tier,
            )
            for spec, parsed, _digest in built
            if spec.source_id in sources
        ]
    )
    kept = set(decisions.kept)
    documents_out: list[dict[str, object]] = []
    chunks_out: list[dict[str, object]] = []
    for spec, parsed, content_sha in built:
        if spec.document_id not in kept:
            continue
        normalized = normalize_blocks(parsed)
        chunks = chunk_document(normalized, manifest.params, "markdown")
        document_row = {str(key): value for key, value in spec.model_dump(mode="json").items()}
        document_row["content_sha256"] = content_sha
        document_row["duplicate_of"] = decisions.duplicate_of.get(spec.document_id)
        documents_out.append(document_row)
        for chunk in chunks:
            chunks_out.append(
                {str(key): value for key, value in chunk.model_dump(mode="json").items()}
            )
    documents_out.sort(key=lambda item: str(item["document_id"]))
    chunks_out.sort(key=lambda item: str(item["chunk_id"]))
    report: dict[str, object] = {
        "manifest_sha256": digest,
        "documents": len(documents_out),
        "chunks": len(chunks_out),
        "duplicate_of": dict(decisions.duplicate_of),
        "exclusions": [dict(item) for item in manifest.exclusions],
        "parsers": {"markdown": "safevoice", "html": "beautifulsoup4", "pdf": "pypdf"},
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    _write(out_dir / "documents.jsonl", documents_out)
    _write(out_dir / "chunks.jsonl", chunks_out)
    (out_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def _write(path: Path, rows: list[dict[str, object]]) -> None:
    lines = [
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for row in rows
    ]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _strings(value: object, fallback: list[str]) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in cast(list[object], value)]
    return fallback
