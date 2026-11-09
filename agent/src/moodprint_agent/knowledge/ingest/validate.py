"""Licence and snapshot gates. reference_only and unverified never become chunks."""

from __future__ import annotations

from moodprint_agent.knowledge.ingest.acquire import RawSnapshot
from moodprint_agent.knowledge.ingest.models import SourceSpec
from moodprint_agent.knowledge.ingest.topics import PUBLISHABLE

_MAGIC = {
    "html": (b"<!doctype", b"<html", b"<"),
    "pdf": (b"%PDF",),
    "markdown": (),
    "text": (),
}


def licence_allows_chunks(source: SourceSpec) -> bool:
    return (
        source.licence_class in PUBLISHABLE
        and source.acquire is not None
        or (source.licence_class == "authored")
    )


def reject_reference(source: SourceSpec) -> None:
    if source.licence_class not in PUBLISHABLE:
        raise ValueError("source licence cannot be embedded")
    if source.licence_class == "open_reuse" and not source.licence_quote:
        raise ValueError("open_reuse source is missing a licence quote")
    if source.licence_class == "open_reuse" and source.verified_on is None:
        raise ValueError("open_reuse source is missing verified_on")


def validate_snapshot(source: SourceSpec, snapshot: RawSnapshot) -> RawSnapshot:
    reject_reference(source)
    kind = source.acquire.kind if source.acquire else "text"
    prefix = snapshot.payload[:16].lstrip().lower()
    expected = _MAGIC.get(kind, ())
    if expected and not any(prefix.startswith(item) for item in expected):
        raise ValueError("payload magic bytes did not match the declared kind")
    if len(snapshot.payload) > 15 * 1024 * 1024:
        raise ValueError("snapshot is too large")
    return snapshot
