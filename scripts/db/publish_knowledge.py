"""Publish the approved cached corpus atomically to the exact audited hosted project.

The existing test-env ingestion target remains loopback-only. This explicit
admin operation requires a reviewed dry-run bound to HEAD, migration history,
the complete curated source manifest and the immutable offline payload.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import re
import subprocess
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from safety import PROJECT_REF, ROOT, check_history, committed_migrations, load_hosted_env
from safevoice_agent.knowledge.ingest.build import build_corpus
from safevoice_agent.knowledge.ingest.commands import (
    _allow_hosts,
    _citation_problems,
    _document_row,
    _source_rows,
)
from safevoice_agent.knowledge.ingest.embed import load_chunks, read_jsonl, read_vectors
from safevoice_agent.knowledge.ingest.manifest import load_manifest
from safevoice_agent.knowledge.ingest.runtime import (
    publish_version,
    store_records,
    validate_version,
)
from safevoice_agent.knowledge.textnorm import fold_vietnamese
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine


def _canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def _portable(rows):
    return [{k: v for k, v in row.items() if k != "path"} for row in rows]


def load_bundle(build: Path, manifest_path: Path) -> dict:
    manifest, digest = load_manifest(manifest_path)
    report = json.loads((build / "report.json").read_text(encoding="utf-8"))
    if report.get("manifest_sha256") != digest:
        raise ValueError("Build does not match the current curated manifest")
    documents = read_jsonl(build / "documents.jsonl")
    chunks = load_chunks(build)
    # Rebuild without network: reject modified text, citation metadata and licence
    # declarations even if someone retained the old report/hash in a build folder.
    with tempfile.TemporaryDirectory(prefix="safevoice-corpus-audit-") as directory:
        rebuilt = Path(directory)
        build_corpus(manifest_path, rebuilt)
        if _portable(documents) != _portable(read_jsonl(rebuilt / "documents.jsonl")):
            raise ValueError("Built documents differ from the approved source")
        if chunks != load_chunks(rebuilt):
            raise ValueError("Built chunks differ from the approved source")
    meta = json.loads((build / "embed.json").read_text(encoding="utf-8"))
    if (
        meta.get("complete") is not True
        or meta.get("model") != "voyage-4"
        or meta.get("dims") != 1024
        or meta.get("embedding_input") != "context"
        or meta.get("input_type") != "document"
        or meta.get("embedded") != len(chunks)
        or meta.get("sha256") != [c["content_sha256"] for c in chunks]
    ):
        raise ValueError("Cached embedding provenance is incompatible")
    vectors = read_vectors(build / "vectors.f32", len(chunks), 1024)
    if any(
        not all(math.isfinite(v) for v in vector)
        or abs(math.sqrt(sum(v * v for v in vector)) - 1) > 0.001
        for vector in vectors
    ):
        raise ValueError("Cached vectors must be finite normalized 1024-dimensional vectors")
    sources = _source_rows(manifest.sources, documents)
    prepared = [_document_row(row, sources) for row in documents]
    payload = {
        "manifest_sha256": digest,
        "embedding_model": "voyage-4",
        "sources": sources,
        "documents": _portable(prepared),
        "chunks": chunks,
        "vectors_sha256": hashlib.sha256((build / "vectors.f32").read_bytes()).hexdigest(),
    }
    return {
        **payload,
        "payload_sha256": hashlib.sha256(_canonical(payload)).hexdigest(),
        "vectors": vectors,
        "allow_hosts": _allow_hosts(manifest_path),
    }


class TransactionEngine:
    """Bind existing ingestion operations to one admin transaction and one lock.

    The local ingestion helpers normally own multiple transactions. For hosted
    initialization, a failed validation/citation check must roll back every row.
    """

    def __init__(self, connection):
        self.connection = connection

    @asynccontextmanager
    async def begin(self):
        yield self.connection

    @asynccontextmanager
    async def connect(self):
        yield self.connection


def hosted_engine(database_url: str):
    """Preserve TLS while adapting a libpq URL for SQLAlchemy's asyncpg dialect."""
    url = make_url(database_url).set(drivername="postgresql+asyncpg")
    mode = url.query.get("sslmode", "require")
    if set(url.query) - {"sslmode"} or mode not in {"require", "verify-ca", "verify-full"}:
        raise ValueError("Hosted corpus connection requires TLS without endpoint query overrides")
    return create_async_engine(
        url.difference_update_query(["sslmode"]),
        hide_parameters=True,
        connect_args={"ssl": mode, "statement_cache_size": 0},
    )


DOCUMENT_COLUMNS = (
    "document_id",
    "source_id",
    "source_licence_class",
    "licence_class",
    "title",
    "language",
    "country_scope",
    "topics",
    "age_bands",
    "published_at",
    "last_reviewed",
    "applicability",
    "primary_url",
    "derived_from",
    "legacy_article_id",
    "content_sha256",
)
CHUNK_COLUMNS = (
    "chunk_id",
    "document_id",
    "ordinal",
    "heading",
    "section_path",
    "text",
    "char_start",
    "char_end",
    "token_estimate",
    "content_sha256",
    "parser",
    "oversize",
)


def compare_stored(bundle: dict, stored: dict) -> None:
    if stored["embedding_model"] != bundle["embedding_model"]:
        raise ValueError("Stored embedding model differs from the immutable payload")
    for kind, key, columns in (
        ("documents", "document_id", DOCUMENT_COLUMNS),
        ("chunks", "chunk_id", CHUNK_COLUMNS),
    ):
        expected = {r[key]: {c: r.get(c) for c in columns} for r in bundle[kind]}
        actual = {r[key]: {c: r.get(c) for c in columns} for r in stored[kind]}
        if len(stored[kind]) != len(expected) or actual != expected:
            raise ValueError("Stored " + kind + " differ from the immutable payload")
    expected_sources = {r["source_id"]: r for r in bundle["sources"]}
    if {r["source_id"]: r for r in stored["sources"]} != expected_sources:
        raise ValueError("Stored source/license metadata differs from the approved payload")
    if len(stored["vectors"]) != len(bundle["vectors"]):
        raise ValueError("Stored vector inventory differs from the immutable payload")
    for actual, expected in zip(stored["vectors"], bundle["vectors"], strict=True):
        # The shared writer prints eight decimal places and pgvector stores float4.
        if len(actual) != 1024 or any(
            not math.isfinite(a) or abs(a - float(f"{b:.8f}")) > 2e-8
            for a, b in zip(actual, expected, strict=True)
        ):
            raise ValueError("Stored vector values differ from the approved cached embeddings")


async def _verify_stored(connection, bundle: dict, version: str) -> None:
    documents = (
        (
            await connection.execute(
                text(
                    "select to_jsonb(d)-'corpus_version' from knowledge.documents d where corpus_version=:v order by document_id"
                ),
                {"v": version},
            )
        )
        .scalars()
        .all()
    )
    rows = (
        (
            await connection.execute(
                text(
                    "select to_jsonb(c)-'corpus_version'-'fts'-'embedding' as data,embedding::text as vector from knowledge.chunks c where corpus_version=:v order by chunk_id"
                ),
                {"v": version},
            )
        )
        .mappings()
        .all()
    )
    sources = (
        (
            await connection.execute(
                text(
                    "select to_jsonb(s)||jsonb_build_object('licence_note',c.licence_note) from knowledge.sources s join knowledge.source_confidential c using(source_id) where s.source_id=any(:ids) order by s.source_id"
                ),
                {"ids": [s["source_id"] for s in bundle["sources"]]},
            )
        )
        .scalars()
        .all()
    )
    model = await connection.scalar(
        text("select embedding_model from knowledge.corpus_versions where version=:v"),
        {"v": version},
    )
    compare_stored(
        bundle,
        {
            "documents": documents,
            "chunks": [r["data"] for r in rows],
            "vectors": [json.loads(r["vector"]) for r in rows],
            "sources": sources,
            "embedding_model": model,
        },
    )
    expected_chunks = {c["chunk_id"]: c for c in bundle["chunks"]}
    if any(
        r["data"]["heading_norm"]
        != fold_vietnamese(str(expected_chunks[r["data"]["chunk_id"]]["heading"]))
        for r in rows
    ):
        raise ValueError("Stored search headings differ from the approved payload")
    expected_fts = [
        {"chunk_id": c["chunk_id"], "folded": fold_vietnamese(f"{c['heading']} {c['text']}")}
        for c in bundle["chunks"]
    ]
    mismatches = await connection.scalar(
        text(
            "select count(*) from knowledge.chunks c join jsonb_to_recordset(cast(:expected as jsonb)) e(chunk_id text,folded text) using(chunk_id) "
            "where c.corpus_version=:v and c.fts<>to_tsvector('simple',e.folded)"
        ),
        {"v": version, "expected": json.dumps(expected_fts)},
    )
    if mismatches:
        raise ValueError("Stored search index differs from the approved payload")


async def publish_bundle(
    engine,
    bundle: dict,
    version: str,
    head: str,
    *,
    reviewed_history=None,
    reviewed_versions=None,
    verify_source=None,
) -> dict:
    if not re.fullmatch(r"kb-\d{8}-\d{2}", version):
        raise ValueError("An explicit immutable kb-YYYYMMDD-NN version is required")
    async with engine.begin() as connection:
        await connection.execute(text("select pg_advisory_xact_lock(8042,2)"))

        async def check_reviewed_state():
            if verify_source is not None:
                verify_source()
            if reviewed_history is not None:
                current = (
                    await connection.execute(
                        text(
                            "select version,name from supabase_migrations.schema_migrations order by version"
                        )
                    )
                ).all()
                if [list(r) for r in current] != reviewed_history:
                    raise ValueError("Migration history changed after the reviewed corpus dry-run")

        await check_reviewed_state()
        current_user = await connection.scalar(text("select current_user"))
        if current_user != "postgres":
            raise ValueError("Hosted corpus writes require the audited postgres admin role")
        versions = (
            (
                await connection.execute(
                    text(
                        "select version,status,manifest_sha256,stats from knowledge.corpus_versions for update"
                    )
                )
            )
            .mappings()
            .all()
        )
        if (
            reviewed_versions is not None
            and sorted([[r["version"], r["status"]] for r in versions]) != reviewed_versions
        ):
            raise ValueError("Corpus versions changed after the reviewed dry-run")
        if any(r["status"] == "published" and r["version"] != version for r in versions):
            raise ValueError(
                "A different corpus is already published; initialization refuses replacement"
            )
        existing = next((r for r in versions if r["version"] == version), None)
        if existing and (
            existing["manifest_sha256"] != bundle["manifest_sha256"]
            or existing["stats"].get("payload_sha256") != bundle["payload_sha256"]
            or existing["status"] != "published"
        ):
            raise ValueError("Existing corpus version is immutable or needs explicit recovery")
        bound = TransactionEngine(connection)
        if existing is None:
            # Shared source IDs are immutable too: never silently reuse conflicting
            # source/license metadata through the local helper's ON CONFLICT.
            for source in bundle["sources"]:
                stored = await connection.scalar(
                    text("select to_jsonb(s) from knowledge.sources s where source_id=:id"),
                    {"id": source["source_id"]},
                )
                expected = {k: v for k, v in source.items() if k != "licence_note"}
                if stored is not None and stored != expected:
                    raise ValueError("Existing source registry conflicts with the approved payload")
            await store_records(
                bound,
                version=version,
                manifest_sha256=bundle["manifest_sha256"],
                embedding_model=bundle["embedding_model"],
                sources=bundle["sources"],
                documents=bundle["documents"],
                chunks=bundle["chunks"],
                vectors=bundle["vectors"],
            )
            await connection.execute(
                text(
                    "update knowledge.corpus_versions set stats=cast(:stats as jsonb) where version=:v"
                ),
                {"v": version, "stats": json.dumps({"payload_sha256": bundle["payload_sha256"]})},
            )
        await _verify_stored(connection, bundle, version)
        await validate_version(bound, version)
        problems = await _citation_problems(bound, version, bundle["allow_hosts"])
        if problems:
            raise ValueError("Corpus citation validation failed: " + ",".join(problems))
        await publish_version(bound, version)
        if existing is None:
            await connection.execute(
                text(
                    "insert into knowledge.ingestion_runs(corpus_version,command,status,detail,git_commit,finished_at)"
                    " values(:v,'publish','succeeded',cast(:detail as jsonb),:head,now())"
                ),
                {
                    "v": version,
                    "head": head,
                    "detail": json.dumps(
                        {"payload_sha256": bundle["payload_sha256"], "atomic": True}
                    ),
                },
            )
        await check_reviewed_state()
    return {
        "version": version,
        "published": True,
        "idempotent": existing is not None,
        "documents": len(bundle["documents"]),
        "chunks": len(bundle["chunks"]),
        "citation_problems": [],
        "embedding_model": bundle["embedding_model"],
        "payload_sha256": bundle["payload_sha256"],
    }


async def run(build: Path, manifest: Path, version: str, *, apply: bool) -> None:
    from urllib.parse import urlsplit

    env = load_hosted_env()
    status = await asyncio.to_thread(
        subprocess.check_output, ["git", "status", "--porcelain"], cwd=ROOT, text=True
    )
    if status.strip():
        raise ValueError("Commit source changes before the hosted corpus dry-run")
    head = (
        await asyncio.to_thread(
            subprocess.check_output, ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        )
    ).strip()
    bundle = await asyncio.to_thread(load_bundle, build, manifest)

    def verify_source():
        current = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        dirty = subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=ROOT, text=True
        ).strip()
        if current != head or dirty:
            raise ValueError("Source changed after the reviewed corpus dry-run")

    verify_source()
    paths = committed_migrations()
    engine = hosted_engine(env["SUPABASE_DB_URL"])
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SET TRANSACTION READ ONLY"))
            rows = (
                await conn.execute(
                    text(
                        "select version,name from supabase_migrations.schema_migrations order by version"
                    )
                )
            ).all()
            if check_history(paths, [tuple(r) for r in rows]):
                raise ValueError(
                    "Complete the guarded schema migrations before corpus initialization"
                )
            versions = (
                await conn.execute(
                    text("select version,status from knowledge.corpus_versions order by version")
                )
            ).all()
        plan = {
            "project_ref": PROJECT_REF,
            "head": head,
            "version": version,
            "manifest_sha256": bundle["manifest_sha256"],
            "payload_sha256": bundle["payload_sha256"],
            "database_hostname": urlsplit(env["SUPABASE_DB_URL"]).hostname,
            "migration_history": [list(r) for r in rows],
            "existing_versions": [list(r) for r in versions],
            "documents": len(bundle["documents"]),
            "chunks": len(bundle["chunks"]),
        }
        receipt = ROOT / ".local/hosted-knowledge-dry-run.json"
        if not apply:
            receipt.parent.mkdir(parents=True, exist_ok=True)
            receipt.write_text(json.dumps(plan, indent=2), encoding="utf-8")
            print(json.dumps({"dry_run": True, **plan}))
            return
        if not receipt.exists() or json.loads(receipt.read_text(encoding="utf-8")) != plan:
            raise ValueError("A matching reviewed hosted corpus dry-run is required")
        result = await publish_bundle(
            engine,
            bundle,
            version,
            head,
            reviewed_history=plan["migration_history"],
            reviewed_versions=plan["existing_versions"],
            verify_source=verify_source,
        )
        (ROOT / ".local/hosted-knowledge-published.json").write_text(
            json.dumps({**plan, **result}, indent=2), encoding="utf-8"
        )
        print(json.dumps(result))
    finally:
        await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--version", required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        asyncio.run(run(args.build, args.manifest, args.version, apply=args.apply))
    except Exception as exc:
        parser.exit(
            1, f"Hosted corpus operation failed ({type(exc).__name__}); credentials suppressed.\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
