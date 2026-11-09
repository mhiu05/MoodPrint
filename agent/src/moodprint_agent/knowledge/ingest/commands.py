"""Executable ingestion commands. Hosted databases are never a target."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from datetime import date
from pathlib import Path
from typing import cast
from urllib.parse import urlparse

from moodprint_shared.config import KnowledgeConfig
from moodprint_shared.contracts.errors import KnowledgeUnavailable
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from moodprint_agent.knowledge.embedder import (
    EmbeddingCache,
    HashingEmbedder,
    VoyageEmbedder,
    estimate_tokens,
)
from moodprint_agent.knowledge.ingest.acquire import fetch_source
from moodprint_agent.knowledge.ingest.budget import (
    BudgetBlocked,
    commit,
    release,
    reserve,
)
from moodprint_agent.knowledge.ingest.embed import (
    embed_missing,
    embedding_input,
    load_chunks,
    read_jsonl,
    read_vectors,
    write_vectors,
)
from moodprint_agent.knowledge.ingest.manifest import load_manifest
from moodprint_agent.knowledge.ingest.models import SourceSpec
from moodprint_agent.knowledge.ingest.runtime import (
    engine_for,
    publish_version,
    rollback_version,
    store_records,
    validate_version,
)
from moodprint_agent.knowledge.ingest.topics import CORE_TOPICS, PUBLISHABLE

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE = re.compile(r"(?<!\d)(?:\+?84|0)\d{8,10}(?!\d)")
_VERSION = re.compile(r"^kb-\d{8}-\d{2}$")
_CACHE = Path(".local/corpus-cache/embeddings.sqlite")
_ACQUIRE_INDEX = Path(".local/corpus-cache/index.json")


def dispatch(args: argparse.Namespace) -> int:
    command = str(args.command)
    if command == "acquire":
        return acquire(args)
    if command == "embed":
        return asyncio.run(embed_build(args))
    if command == "store":
        return asyncio.run(store_build(args))
    if command == "validate":
        return asyncio.run(_validate(args))
    if command == "publish":
        return asyncio.run(_publish(args))
    if command == "rollback":
        return asyncio.run(_rollback(args))
    if command == "status":
        return asyncio.run(_status(str(args.target or "test-env")))
    if command == "verify-citations":
        return asyncio.run(_verify(args))
    raise ValueError("command is not available")


def acquire(args: argparse.Namespace) -> int:
    if args.manifest is None:
        raise ValueError("acquire requires --manifest")
    manifest, _digest = load_manifest(args.manifest)
    chosen = [
        source
        for source in manifest.sources
        if source.licence_class == "open_reuse" and source.acquire is not None
    ]
    if args.only:
        chosen = [source for source in chosen if source.source_id == args.only]
        if not chosen:
            raise ValueError("requested source is not an open_reuse acquire target")
    report = asyncio.run(_acquire(chosen, offline=bool(args.offline)))
    index = report.pop("index", None)
    if isinstance(index, dict):
        _ACQUIRE_INDEX.parent.mkdir(parents=True, exist_ok=True)
        _ACQUIRE_INDEX.write_text(json.dumps(index, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if not report["failed"] else 1


async def _acquire(sources: list[SourceSpec], *, offline: bool) -> dict[str, object]:
    index = _read_index()
    acquired: list[str] = []
    skipped: list[str] = []
    failed: list[dict[str, str]] = []
    cache = Path(".local/corpus-cache/blobs")
    if offline:
        for source in sources:
            digest = index.get(source.source_id)
            blob = cache / digest if digest else None
            if blob is not None and blob.is_file():
                acquired.append(source.source_id)
            else:
                failed.append({"source_id": source.source_id, "reason": "cache_miss"})
        return {"acquired": acquired, "failed": failed, "skipped": skipped, "offline": True}
    import httpx

    async with httpx.AsyncClient(timeout=30) as client:
        for source in sources:
            spec = source.acquire
            if spec is None:
                continue
            try:
                snapshot_row = await fetch_source(
                    source.source_id,
                    spec.url,
                    spec.allow_hosts,
                    client=client,
                    cache=cache,
                    expected_sha256=spec.expected_sha256,
                )
            except (OSError, ValueError) as exc:
                failed.append({"source_id": source.source_id, "reason": type(exc).__name__})
                continue
            if snapshot_row is None:
                skipped.append(source.source_id)
                continue
            index[source.source_id] = snapshot_row.sha256
            acquired.append(source.source_id)
    return {
        "acquired": acquired,
        "failed": failed,
        "index": index,
        "offline": False,
        "skipped": skipped,
    }


def _read_index() -> dict[str, str]:
    if not _ACQUIRE_INDEX.exists():
        return {}
    loaded = json.loads(_ACQUIRE_INDEX.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        return {}
    return {str(key): str(value) for key, value in cast(dict[object, object], loaded).items()}


async def embed_build(args: argparse.Namespace) -> int:
    if args.build is None:
        raise ValueError("embed requires --build")
    embedder_name = str(args.embedder or "hashing")
    chunks = load_chunks(args.build)
    titles = {
        str(row["document_id"]): str(row.get("title") or "")
        for row in read_jsonl(args.build / "documents.jsonl")
    }
    texts = [
        embedding_input(
            titles.get(str(row["document_id"]), ""), str(row["heading"]), str(row["text"])
        )
        for row in chunks
    ]
    if (
        args.budget_tokens is not None
        and sum(estimate_tokens(text) for text in texts) > args.budget_tokens
    ):
        raise BudgetBlocked("estimated tokens exceed --budget-tokens")
    cfg = KnowledgeConfig()
    model = "hashing" if embedder_name == "hashing" else cfg.embedding_model
    cache = EmbeddingCache(_CACHE)
    reservation: str | None = None
    voyage: VoyageEmbedder | None = None
    settled = False
    try:
        if embedder_name == "voyage":
            estimated = sum(estimate_tokens(text) for text in texts)
            reservation = reserve(max(estimated, 1))
            voyage = VoyageEmbedder(_voyage_key(), cfg, cache=cache)
            batch_size = cfg.ingest_batch_size

            async def _batch(batch: list[str]) -> list[list[float]]:
                assert voyage is not None
                return await voyage.embed_documents(batch)

            vectors, hits = await embed_missing(
                texts,
                _batch,
                cache,
                model=model,
                dims=cfg.embedding_dims,
                input_type="document",
                batch_size=batch_size,
            )
            commit(reservation, voyage.usage.total_tokens)
            settled = True
            tokens = voyage.usage.total_tokens
            usd = voyage.usage.usd
        else:
            hasher = HashingEmbedder(cfg.embedding_dims)

            async def _hash_batch(batch: list[str]) -> list[list[float]]:
                return await hasher.embed_documents(batch)

            vectors, hits = await embed_missing(
                texts,
                _hash_batch,
                cache,
                model=model,
                dims=cfg.embedding_dims,
                input_type="document",
                batch_size=1,
            )
            tokens = 0
            usd = 0.0
        write_vectors(args.build / "vectors.f32", vectors)
        report = {
            "cache_hits": hits,
            "complete": True,
            "dims": cfg.embedding_dims,
            "embedded": len(vectors),
            "embedding_input": "title + heading + text",
            "input_type": "document",
            "model": model,
            "sha256": [str(row["content_sha256"]) for row in chunks],
            "tokens": tokens,
            "usd": usd,
        }
        (args.build / "embed.json").write_text(
            json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps({"embedded": len(vectors), "cache_hits": hits, "model": model}))
        return 0
    except KnowledgeUnavailable as exc:
        await _settle_voyage_error(reservation, exc)
        settled = True
        status = exc.details.get("status")
        reason = exc.details.get("reason")
        print(f"voyage_{_voyage_class(status, reason)}", file=sys.stderr)
        return 1
    finally:
        if reservation is not None and not settled:
            release(reservation)
        cache.close()
        if voyage is not None:
            await voyage.aclose()


def _voyage_class(status: object, reason: object) -> str:
    if status in {401, 403}:
        return "auth"
    if status == 400:
        return "bad_request"
    if status == 429:
        return "rate_limit"
    if reason == "embed_http":
        return "network"
    return "rejected"


async def _settle_voyage_error(reservation: str | None, exc: KnowledgeUnavailable) -> None:
    if reservation is None:
        return
    status = exc.details.get("status")
    if status in {401, 403, 400}:
        release(reservation)
        return
    commit(reservation, None)


def _voyage_key() -> str:
    if os.environ.get("APP_ENV") == "test":
        key = os.environ.get("VOYAGE_API_KEY", "").strip()
        if not key:
            raise ValueError("VOYAGE_API_KEY is not in the test process environment")
        return key
    from moodprint_shared.env import get_settings

    secret = get_settings().voyage_api_key
    if secret is None or not secret.get_secret_value().strip():
        raise ValueError("VOYAGE_API_KEY is not available from the development settings")
    return secret.get_secret_value().strip()


async def store_build(args: argparse.Namespace) -> int:
    if args.build is None or args.manifest is None:
        raise ValueError("store requires --build and --manifest")
    version = _require_version(args.version)
    manifest, digest = load_manifest(args.manifest)
    report = json.loads((args.build / "report.json").read_text(encoding="utf-8"))
    if report.get("manifest_sha256") != digest:
        raise ValueError("build manifest hash does not match the manifest")
    documents = read_jsonl(args.build / "documents.jsonl")
    chunks = load_chunks(args.build)
    embed_meta = json.loads((args.build / "embed.json").read_text(encoding="utf-8"))
    if not embed_meta.get("complete"):
        raise ValueError("embeddings are incomplete")
    vectors = read_vectors(args.build / "vectors.f32", len(chunks), int(embed_meta["dims"]))
    sources = _source_rows(manifest.sources, documents)
    prepared = [_document_row(row, sources) for row in documents]
    engine = engine_for(str(args.target or "test-env"))
    try:
        await store_records(
            engine,
            version=version,
            manifest_sha256=digest,
            embedding_model=str(embed_meta["model"]),
            sources=sources,
            documents=prepared,
            chunks=chunks,
            vectors=vectors,
        )
        await _record(engine, version, "store", "succeeded")
    finally:
        await engine.dispose()
    print(json.dumps({"stored": version, "documents": len(prepared), "chunks": len(chunks)}))
    return 0


def _objects(value: object) -> list[object]:
    if not isinstance(value, list):
        return []
    return list(cast(list[object], value))


def _require_version(value: object) -> str:
    version = str(value or "")
    if not _VERSION.fullmatch(version):
        raise ValueError("version must look like kb-YYYYMMDD-NN")
    return version


def _source_rows(
    sources: list[SourceSpec], documents: list[dict[str, object]]
) -> list[dict[str, object]]:
    needed = {str(row["source_id"]) for row in documents}
    for row in documents:
        for item in _objects(row.get("derived_from") or []):
            if isinstance(item, dict):
                source_id = cast(dict[object, object], item).get("source_id")
                if source_id:
                    needed.add(str(source_id))
    rows: list[dict[str, object]] = []
    by_id = {source.source_id: source for source in sources}
    for source_id in sorted(needed):
        source = by_id.get(source_id)
        if source is None:
            raise ValueError("document cites a source that is not in the manifest")
        if source.licence_class == "unverified":
            raise ValueError("unverified sources cannot be stored")
        if source.verified_on is None:
            raise ValueError("stored sources need verified_on")
        if source.licence_class not in {"open_reuse", "authored", "reference_only"}:
            raise ValueError("source licence cannot be stored")
        rows.append(
            {
                "source_id": source.source_id,
                "kind": source.kind,
                "publisher": source.publisher,
                "title": source.title,
                "url": source.url,
                "language": source.language,
                "country_scope": source.country_scope,
                "authority_tier": source.authority_tier,
                "licence_class": source.licence_class,
                "licence_quote": source.licence_quote,
                "licence_note": source.licence_note,
                "verified_on": source.verified_on.isoformat(),
                "retrieved_on": None
                if source.retrieved_on is None
                else source.retrieved_on.isoformat(),
            }
        )
    return rows


def _document_row(row: dict[str, object], sources: list[dict[str, object]]) -> dict[str, object]:
    by_id = {str(source["source_id"]): source for source in sources}
    source = by_id[str(row["source_id"])]
    licence = str(row.get("licence_class") or "authored")
    if licence not in PUBLISHABLE:
        raise ValueError("document licence cannot be published")
    return {**row, "source_licence_class": source["licence_class"], "licence_class": licence}


async def _validate(args: argparse.Namespace) -> int:
    version = _require_version(args.version)
    engine = engine_for(str(args.target or "test-env"))
    try:
        await validate_version(engine, version)
        await _record(engine, version, "validate", "succeeded")
    finally:
        await engine.dispose()
    print(json.dumps({"validated": version}))
    return 0


async def _publish(args: argparse.Namespace) -> int:
    version = _require_version(args.version)
    engine = engine_for(str(args.target or "test-env"))
    try:
        await publish_version(engine, version)
        await _record(engine, version, "publish", "succeeded")
    finally:
        await engine.dispose()
    print(json.dumps({"published": version}))
    return 0


async def _rollback(args: argparse.Namespace) -> int:
    version = _require_version(args.to or args.version)
    engine = engine_for(str(args.target or "test-env"))
    try:
        await rollback_version(engine, version)
        await _record(engine, version, "rollback", "succeeded")
    finally:
        await engine.dispose()
    print(json.dumps({"published": version}))
    return 0


async def _status(target: str) -> int:
    engine = engine_for(target)
    try:
        async with engine.connect() as conn:
            rows = (
                (
                    await conn.execute(
                        text(
                            "select v.version, v.status, v.embedding_model,"
                            " (select count(*) from knowledge.documents d where d.corpus_version = v.version) as documents,"
                            " (select count(*) from knowledge.chunks c where c.corpus_version = v.version) as chunks"
                            " from knowledge.corpus_versions v order by v.version"
                        )
                    )
                )
                .mappings()
                .all()
            )
    finally:
        await engine.dispose()
    print(json.dumps([dict(row) for row in rows], ensure_ascii=False))
    return 0


async def _verify(args: argparse.Namespace) -> int:
    version = _require_version(args.version)
    allow_hosts = _allow_hosts(args.manifest) if args.manifest else None
    engine = engine_for(str(args.target or "test-env"))
    try:
        problems = await _citation_problems(engine, version, allow_hosts)
        links: list[dict[str, object]] = []
        if args.link_check:
            links = await _link_check(engine, version)
    finally:
        await engine.dispose()
    broken_links = [row for row in links if row.get("ok") is not True]
    print(
        json.dumps(
            {"problems": problems, "links": links, "version": version},
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    if problems or broken_links:
        return 1
    return 0


def _allow_hosts(manifest_path: Path) -> set[str]:
    manifest, _digest = load_manifest(manifest_path)
    hosts: set[str] = set()
    for source in manifest.sources:
        if source.url:
            host = urlparse(source.url).hostname
            if host:
                hosts.add(host.lower())
        if source.acquire:
            hosts.update(host.lower() for host in source.acquire.allow_hosts)
    return hosts


async def _citation_problems(
    engine: AsyncEngine, version: str, allow_hosts: set[str] | None
) -> list[str]:
    async with engine.connect() as conn:
        rows = (
            (
                await conn.execute(
                    text(
                        "select c.chunk_id, d.document_id, d.source_id, d.primary_url, d.last_reviewed,"
                        " d.applicability, d.licence_class, d.derived_from, s.url as source_url,"
                        " s.verified_on, c.text"
                        " from knowledge.chunks c"
                        " join knowledge.documents d on d.corpus_version = c.corpus_version"
                        " and d.document_id = c.document_id"
                        " join knowledge.sources s on s.source_id = d.source_id"
                        " where c.corpus_version = :version"
                    ),
                    {"version": version},
                )
            )
            .mappings()
            .all()
        )
        known = set((await conn.execute(text("select source_id from knowledge.sources"))).scalars())
    problems: list[str] = []
    today = date.today()
    if not rows:
        problems.append("no_chunks")
    for row in rows:
        reviewed = row["last_reviewed"]
        if not isinstance(reviewed, date) or reviewed > today:
            problems.append("last_reviewed")
        if not str(row["applicability"] or "").strip():
            problems.append("applicability")
        if _EMAIL.search(str(row["text"])) or _PHONE.search(str(row["text"])):
            problems.append("personal_data")
        for label, raw in (("primary_url", row["primary_url"]), ("source_url", row["source_url"])):
            if not raw:
                continue
            host = urlparse(str(raw)).hostname
            if allow_hosts is not None and (host is None or host.lower() not in allow_hosts):
                problems.append(f"{label}_host")
        if row["licence_class"] == "authored":
            items = _objects(row["derived_from"])
            if not items:
                problems.append("derived_from")
            for item in items:
                if not isinstance(item, dict):
                    problems.append("derived_source")
                    continue
                source_id = str(cast(dict[object, object], item).get("source_id") or "")
                if source_id not in known or not await _verified(engine, source_id):
                    problems.append("derived_source")
    return sorted(set(problems))


async def _verified(engine: AsyncEngine, source_id: str) -> bool:
    async with engine.connect() as conn:
        value = (
            await conn.execute(
                text("select verified_on from knowledge.sources where source_id = :source_id"),
                {"source_id": source_id},
            )
        ).scalar_one_or_none()
    return value is not None


async def _link_check(engine: AsyncEngine, version: str) -> list[dict[str, object]]:
    import httpx

    async with engine.connect() as conn:
        urls = (
            await conn.execute(
                text(
                    "select distinct primary_url from knowledge.documents"
                    " where corpus_version = :version and primary_url is not null"
                ),
                {"version": version},
            )
        ).scalars()
        targets = [str(url) for url in urls]
    results: list[dict[str, object]] = []
    async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
        for url in targets:
            try:
                response = await client.head(url)
                results.append(
                    {
                        "url_host": urlparse(url).hostname,
                        "status": response.status_code,
                        "ok": response.status_code < 400,
                    }
                )
            except httpx.HTTPError:
                results.append({"url_host": urlparse(url).hostname, "status": 0, "ok": False})
    return results


async def _record(engine: AsyncEngine, version: str, command: str, status: str) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "insert into knowledge.ingestion_runs (corpus_version, command, status, detail)"
                " values (:version, :command, :status, '{}'::jsonb)"
            ),
            {"version": version, "command": command, "status": status},
        )


def scan_personal_data(text_value: str) -> bool:
    return _EMAIL.search(text_value) is not None or _PHONE.search(text_value) is not None


def core_topic_gap(counts: dict[str, int]) -> list[str]:
    return [topic for topic in CORE_TOPICS if counts.get(topic, 0) == 0]
