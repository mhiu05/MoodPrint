from pathlib import Path

from safevoice_agent.knowledge.ingest.manifest import load_manifest
from safevoice_agent.knowledge.ingest.topics import LICENCE_CLASSES


def test_source_registry_keeps_licence_classes_and_blocks_restricted_acquire() -> None:
    manifest, digest = load_manifest(Path("agent/ingestion/corpus/manifest.toml"))
    assert len(digest) == 64
    assert len(manifest.sources) >= 12
    assert len(manifest.documents) >= 40
    for source in manifest.sources:
        assert source.licence_class in LICENCE_CLASSES
        if source.licence_class == "open_reuse":
            assert source.licence_quote
            assert source.verified_on is not None
        if source.licence_class in {"reference_only", "unverified"}:
            assert source.acquire is None
    assert any(source.licence_class == "authored" for source in manifest.sources)
    assert any(source.licence_class == "reference_only" for source in manifest.sources)
    assert any(source.licence_class == "unverified" for source in manifest.sources)
