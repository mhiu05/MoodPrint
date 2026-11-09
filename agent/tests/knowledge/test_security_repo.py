"""Repository-level gates: no committed secrets, and no document that cannot be published (P2-14 d, f)."""

from __future__ import annotations

import re
import subprocess
import tomllib
from pathlib import Path

from moodprint_agent.knowledge.ingest.manifest import load_manifest
from moodprint_agent.knowledge.ingest.topics import PUBLISHABLE

REPO = Path(__file__).resolve().parents[3]
MANIFEST = REPO / "agent" / "ingestion" / "corpus" / "manifest.toml"

# Patterns are assembled from parts so this file does not match itself.
SECRET_PATTERNS = {
    "voyage key": re.compile(r"(?<![A-Za-z0-9])pa" + r"-[A-Za-z0-9_\-]{30,}"),
    "openai-style key": re.compile(r"(?<![A-Za-z0-9])sk" + r"-[A-Za-z0-9_\-]{24,}"),
    "supabase secret": re.compile("sb_" + r"secret_[A-Za-z0-9_\-]{10,}"),
    "jwt": re.compile("eyJ" + r"[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{10,}"),
    "private key": re.compile("-----BEGIN " + r"(?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}
SKIP_SUFFIXES = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".woff",
    ".woff2",
    ".lock",
}


def _tracked_files() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout
    return [REPO / line for line in out.splitlines() if line]


def test_no_tracked_file_contains_a_credential() -> None:
    hits: list[str] = []
    for path in _tracked_files():
        if path.suffix.lower() in SKIP_SUFFIXES or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                hits.append(f"{path.relative_to(REPO)} ({label})")
    assert hits == [], hits


def test_env_files_are_not_tracked() -> None:
    names = [p.name for p in _tracked_files()]
    assert ".env" not in names
    assert not any(n.startswith(".env.") and n != ".env.example" for n in names)


def test_every_manifest_document_has_a_publishable_licence_and_a_verified_source() -> None:
    manifest, _ = load_manifest(MANIFEST)
    sources = {source.source_id: source for source in manifest.sources}
    assert manifest.documents, "the manifest must not be empty"
    for document in manifest.documents:
        assert document.licence_class in PUBLISHABLE, document.document_id
        source = sources[document.source_id]
        assert source.licence_class != "unverified", document.document_id
        assert source.verified_on is not None, document.document_id
        if document.licence_class == "open_reuse":
            assert source.licence_class == "open_reuse", document.document_id
            assert source.licence_quote, document.document_id


def test_authored_cards_only_derive_from_verified_registered_sources() -> None:
    manifest, _ = load_manifest(MANIFEST)
    sources = {source.source_id: source for source in manifest.sources}
    for document in manifest.documents:
        if document.licence_class != "authored":
            continue
        raw = tomllib.loads(
            Path(document.path or "")
            .read_text(encoding="utf-8")
            .replace("\r\n", "\n")
            .split("\n+++", 1)[0]
            .removeprefix("+++")
        )
        derived = raw.get("derived_from", [])
        assert derived, f"{document.document_id} has no derived_from"
        for item in derived:
            source = sources[item["source_id"]]
            assert source.verified_on is not None, (document.document_id, item["source_id"])
            assert item["locator"].strip(), document.document_id


def test_no_card_repeats_boilerplate_across_the_corpus() -> None:
    """The first-pass corpus had four sentences in 345 chunks; a repeat now means padding."""
    manifest, _ = load_manifest(MANIFEST)
    seen: dict[str, set[str]] = {}
    for document in manifest.documents:
        body = Path(document.path or "").read_text(encoding="utf-8").replace("\r\n", "\n")
        body = body.split("\n+++", 1)[-1]
        for sentence in re.split(r"(?<=[.!?])\s+", body):
            key = sentence.strip().casefold()
            if len(key) > 60:
                seen.setdefault(key, set()).add(document.document_id)
    repeated = {s[:60]: sorted(d) for s, d in seen.items() if len(d) > 2}
    assert repeated == {}, repeated
