"""The hosted corpus boundary rejects stale or tampered offline artifacts."""

import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts/db"))


def module():
    path = Path(__file__).resolve().parents[1] / "publish_knowledge.py"
    assert path.exists(), "The guarded hosted knowledge publisher is missing"
    spec = importlib.util.spec_from_file_location("publish_knowledge", path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = result
    spec.loader.exec_module(result)
    return result


@pytest.fixture
def build(tmp_path):
    from safevoice_agent.knowledge.embedder import HashingEmbedder
    from safevoice_agent.knowledge.ingest.build import build_corpus
    from safevoice_agent.knowledge.ingest.embed import read_jsonl, write_vectors

    # Real curated source, tiny deterministic vectors at the offline test boundary.
    manifest = ROOT / "agent/ingestion/corpus/manifest.toml"
    build_corpus(manifest, tmp_path)
    chunks = read_jsonl(tmp_path / "chunks.jsonl")
    vectors = [HashingEmbedder()._vector(str(c["text"])) for c in chunks]
    write_vectors(tmp_path / "vectors.f32", vectors)
    (tmp_path / "embed.json").write_text(
        json.dumps(
            {
                "complete": True,
                "model": "voyage-4",
                "dims": 1024,
                "embedding_input": "context",
                "input_type": "document",
                "embedded": len(chunks),
                "sha256": [c["content_sha256"] for c in chunks],
            }
        )
    )
    return tmp_path, manifest


def test_validated_bundle_covers_curated_sources_and_cached_vectors(build):
    publisher = module()
    bundle = publisher.load_bundle(*build)
    assert len(bundle["documents"]) == 57
    assert len(bundle["chunks"]) == len(bundle["vectors"]) == 80
    assert bundle["embedding_model"] == "voyage-4"
    assert len(bundle["payload_sha256"]) == 64


@pytest.mark.parametrize("mutation", ["text", "document", "vector", "manifest", "model"])
def test_modified_build_cannot_reach_hosted_connection(build, mutation):
    publisher = module()
    folder, manifest = build
    if mutation == "text":
        path = folder / "chunks.jsonl"
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        rows[0]["text"] = "Invented content pretending to be an approved source."
        path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    elif mutation == "document":
        path = folder / "documents.jsonl"
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        rows[0]["derived_from"] = []
        path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    elif mutation == "vector":
        (folder / "vectors.f32").write_bytes(b"\0" * (80 * 1024 * 4))
    else:
        path = folder / ("report.json" if mutation == "manifest" else "embed.json")
        data = json.loads(path.read_text(encoding="utf-8"))
        data["manifest_sha256" if mutation == "manifest" else "model"] = "unapproved"
        path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        publisher.load_bundle(folder, manifest)


def test_bundle_digest_ignores_machine_specific_document_paths(build, tmp_path_factory):
    publisher = module()
    folder, manifest = build
    original = publisher.load_bundle(folder, manifest)
    copied = tmp_path_factory.mktemp("copied-build")
    shutil.copytree(folder, copied, dirs_exist_ok=True)
    path = copied / "documents.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    for row in rows:
        row["path"] = "/another-machine/approved-source.md"
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    assert publisher.load_bundle(copied, manifest)["payload_sha256"] == original["payload_sha256"]


@pytest.mark.parametrize("mutation", ["citation", "licence", "vector", "model"])
def test_idempotent_publish_rejects_database_content_drift(build, mutation):
    import copy

    publisher = module()
    bundle = publisher.load_bundle(*build)
    snapshot = copy.deepcopy(bundle)
    if mutation == "citation":
        snapshot["documents"][0]["title"] = "Different citation title"
    elif mutation == "licence":
        snapshot["sources"][0]["licence_note"] = "Different provenance"
    elif mutation == "vector":
        snapshot["vectors"][0][0], snapshot["vectors"][0][1] = (
            snapshot["vectors"][0][1],
            snapshot["vectors"][0][0],
        )
    else:
        snapshot["embedding_model"] = "hashing"
    assert hasattr(publisher, "compare_stored"), "Full persisted-payload verification is missing"
    with pytest.raises(ValueError):
        publisher.compare_stored(bundle, snapshot)


async def test_hosted_engine_translates_libpq_sslmode_before_asyncpg_connect():
    from sqlalchemy import event

    publisher = module()
    assert hasattr(publisher, "hosted_engine"), "Hosted SSL connection adaptation is missing"
    engine = publisher.hosted_engine(
        "postgresql://postgres:synthetic@db.example.supabase.co/postgres?sslmode=require"
    )
    seen = {}

    class StopBeforeNetwork(Exception):
        pass

    @event.listens_for(engine.sync_engine, "do_connect")
    def inspect_driver_args(dialect, record, args, kwargs):
        seen.update(kwargs)
        raise StopBeforeNetwork

    try:
        with pytest.raises(StopBeforeNetwork):
            async with engine.connect():
                pytest.fail("The probe must never connect")
        assert "sslmode" not in seen
        assert seen["ssl"] == "require"
        assert seen["host"] == "db.example.supabase.co"
    finally:
        await engine.dispose()
