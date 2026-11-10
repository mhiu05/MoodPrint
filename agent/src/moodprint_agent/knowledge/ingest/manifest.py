"""Load the curated manifest and source registry. No network and no database."""

from __future__ import annotations

import hashlib
import json
import tomllib
from datetime import date
from pathlib import Path

from moodprint_agent.knowledge.ingest.models import (
    AcquireSpec,
    ChunkParams,
    CorpusManifest,
    DocumentSpec,
    SourceSpec,
)
from moodprint_agent.knowledge.ingest.topics import LICENCE_CLASSES


def _date(value: object) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def load_source(path: Path) -> SourceSpec:
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    acquire = raw.pop("acquire", None)
    scores = raw.pop("scores", {})
    raw["verified_on"] = _date(raw.get("verified_on"))
    raw["retrieved_on"] = _date(raw.get("retrieved_on"))
    if acquire is not None:
        raw["acquire"] = AcquireSpec.model_validate(acquire)
    for key, field in (
        ("authority", "authority"),
        ("relevance", "relevance"),
        ("licence", "licence"),
        ("language", "language_score"),
        ("applicability", "applicability_score"),
        ("freshness", "freshness"),
    ):
        if key in scores:
            raw[field] = scores[key]
    source = SourceSpec.model_validate(raw)
    if source.licence_class not in LICENCE_CLASSES:
        raise ValueError(f"{source.source_id} has an unknown licence class")
    if source.licence_class in {"reference_only", "unverified"} and source.acquire is not None:
        raise ValueError(f"{source.source_id} cannot declare acquire")
    if source.licence_class == "open_reuse" and (
        not source.licence_quote or source.verified_on is None
    ):
        raise ValueError(f"{source.source_id} is missing open_reuse evidence")
    return source


def load_manifest(path: Path) -> tuple[CorpusManifest, str]:
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    root = path.parent
    sources = [load_source(item) for item in sorted((root / "sources").glob("*.toml"))]
    documents: list[DocumentSpec] = []
    for item in raw.get("document", []):
        card = root / item["path"] if not Path(item["path"]).is_absolute() else Path(item["path"])
        # Paths in the manifest are relative to the corpus directory.
        card = (
            (root / item["path"]).resolve()
            if not str(item["path"]).startswith("/")
            else Path(item["path"])
        )
        documents.append(
            DocumentSpec.model_validate(
                {
                    "document_id": item["document_id"],
                    "source_id": item["source_id"],
                    "title": item.get("title", item["document_id"]),
                    "topics": item.get("topics", []),
                    "age_bands": item.get("age_bands", ["11-13", "14-17"]),
                    "last_reviewed": item.get("last_reviewed", "2026-11-08"),
                    "applicability": item.get(
                        "applicability",
                        "Tóm tắt biên soạn của MoodPrint cho học sinh tại Việt Nam.",
                    ),
                    "legacy_article_id": item.get("legacy_article_id"),
                    "primary_url": item.get("primary_url"),
                    "path": str(card),
                    "language": item.get("language", "vi"),
                    "country_scope": item.get("country_scope", ["VN"]),
                    "licence_class": item.get("licence_class", "authored"),
                }
            )
        )
    exclusions = list(raw.get("exclusion", []))
    manifest = CorpusManifest(
        version_label=str(raw.get("version_label", "")),
        sources=sources,
        documents=documents,
        params=ChunkParams.model_validate(raw.get("params", {})),
        exclusions=[{str(key): str(value) for key, value in item.items()} for item in exclusions],
    )
    digest = manifest_digest(path, manifest)
    return manifest, digest


def manifest_digest(path: Path, manifest: CorpusManifest) -> str:
    root = path.parent
    files = [path, *sorted((root / "sources").glob("*.toml"))]
    for document in manifest.documents:
        if document.path:
            files.append(Path(document.path))
    hasher = hashlib.sha256()
    for item in files:
        hasher.update(item.name.encode())
        # CRLF and LF checkouts of the same card must give the same digest.
        hasher.update(item.read_bytes().replace(b"\r\n", b"\n"))
    hasher.update(json.dumps(manifest.params.model_dump(mode="json"), sort_keys=True).encode())
    return hasher.hexdigest()
