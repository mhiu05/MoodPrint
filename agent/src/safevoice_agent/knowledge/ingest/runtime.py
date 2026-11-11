"""Database publish path. Connections must be loopback; hosted targets are rejected."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
from datetime import date
from pathlib import Path
from typing import Any, cast

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from safevoice_agent.knowledge.embedder import HashingEmbedder
from safevoice_agent.knowledge.textnorm import fold_vietnamese

_LOOPBACK = {"127.0.0.1", "localhost", "::1"}
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE = re.compile(r"(?<!\d)(?:\+?84|0)\d{8,10}(?!\d)")
_LOCK_A = 8042
_LOCK_B = 2


def resolve_admin_url(target: str) -> str:
    if target != "test-env":
        raise ValueError("only the loopback test-env target is supported")
    for name in ("TEST_ADMIN_DATABASE_URL", "TEST_DATABASE_URL"):
        if os.environ.get(name):
            return _loopback(os.environ[name], name)
    stack = os.environ.get("SAFEVOICE_STACK_NAME", "kb")
    candidates = [
        Path(".local/stacks") / stack / "test.env",
        Path(".local/stacks/kb/test.env"),
        Path(".local/test.env"),
    ]
    for path in candidates:
        if not path.exists():
            continue
        values = _env_file(path)
        for name in ("TEST_ADMIN_DATABASE_URL", "TEST_DATABASE_URL"):
            if values.get(name):
                return _loopback(values[name], name)
    raise ValueError("loopback test database URL is not configured")


def _loopback(url: str, name: str) -> str:
    host = make_url(url).host
    if host not in _LOOPBACK:
        raise ValueError(f"{name} must use a loopback host")
    return url


def _env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"')
    return values


def engine_for(target: str) -> AsyncEngine:
    return create_async_engine(resolve_admin_url(target), hide_parameters=True)


async def store_records(
    engine: AsyncEngine,
    *,
    version: str,
    manifest_sha256: str,
    embedding_model: str,
    sources: list[dict[str, object]],
    documents: list[dict[str, object]],
    chunks: list[dict[str, object]],
    vectors: list[list[float]],
) -> None:
    if len(chunks) != len(vectors):
        raise ValueError("chunk and vector counts differ")
    async with engine.begin() as conn:
        await conn.execute(
            text("select pg_advisory_xact_lock(:a, :b)"), {"a": _LOCK_A, "b": _LOCK_B}
        )
        existing = (
            (
                await conn.execute(
                    text(
                        "select status, manifest_sha256 from knowledge.corpus_versions where version = :version"
                    ),
                    {"version": version},
                )
            )
            .mappings()
            .first()
        )
        if existing:
            if existing["manifest_sha256"] != manifest_sha256:
                raise ValueError("published corpus version is immutable")
            if existing["status"] != "building":
                return
        if existing is None:
            await conn.execute(
                text(
                    "insert into knowledge.corpus_versions"
                    "(version, status, embedding_model, embedding_dims, manifest_sha256, builder)"
                    " values (:version, 'building', :model, 1024, :digest, 'knowledge-base')"
                ),
                {"version": version, "model": embedding_model, "digest": manifest_sha256},
            )
        for source in sources:
            source = {
                **source,
                "verified_on": _as_date(source.get("verified_on")),
                "retrieved_on": _as_date(source.get("retrieved_on")),
            }
            await conn.execute(
                text(
                    "insert into knowledge.sources (source_id, kind, publisher, title, url, language,"
                    " country_scope, authority_tier, licence_class, licence_quote, verified_on, retrieved_on)"
                    " values (:source_id, :kind, :publisher, :title, :url, :language, :country_scope,"
                    " :authority_tier, :licence_class, :licence_quote, :verified_on, :retrieved_on)"
                    " on conflict (source_id) do nothing"
                ),
                source,
            )
            await conn.execute(
                text(
                    "insert into knowledge.source_confidential (source_id, licence_note)"
                    " values (:source_id, :licence_note) on conflict (source_id) do nothing"
                ),
                source,
            )
        for document in documents:
            document = {
                **document,
                "published_at": _as_date(document.get("published_at")),
                "last_reviewed": _as_date(document.get("last_reviewed")),
                "derived_from": json.dumps(document.get("derived_from") or [], ensure_ascii=False),
            }
            await conn.execute(
                text(
                    "insert into knowledge.documents (corpus_version, document_id, source_id,"
                    " source_licence_class, licence_class, title, language, country_scope, topics,"
                    " age_bands, published_at, last_reviewed, applicability, primary_url, derived_from,"
                    " legacy_article_id, content_sha256)"
                    " values (:corpus_version, :document_id, :source_id, :source_licence_class,"
                    " :licence_class, :title, :language, :country_scope, :topics, :age_bands,"
                    " :published_at, :last_reviewed, :applicability, :primary_url,"
                    " cast(:derived_from as jsonb), :legacy_article_id, :content_sha256)"
                    " on conflict (corpus_version, document_id) do nothing"
                ),
                {**document, "corpus_version": version},
            )
    for start in range(0, len(chunks), 200):
        async with engine.begin() as conn:
            for chunk, vector in zip(
                chunks[start : start + 200], vectors[start : start + 200], strict=True
            ):
                folded = fold_vietnamese(f"{chunk['heading']} {chunk['text']}")
                await conn.execute(
                    text(
                        "insert into knowledge.chunks (corpus_version, document_id, chunk_id, ordinal,"
                        " heading, section_path, text, heading_norm, fts, embedding, char_start, char_end,"
                        " token_estimate, content_sha256, parser, oversize)"
                        " values (:corpus_version, :document_id, :chunk_id, :ordinal, :heading, :section_path,"
                        " :text, :heading_norm, to_tsvector('simple', :folded), cast(:embedding as vector),"
                        " :char_start, :char_end, :token_estimate, :content_sha256, :parser, :oversize)"
                        " on conflict (corpus_version, chunk_id) do nothing"
                    ),
                    {
                        **chunk,
                        "corpus_version": version,
                        "heading_norm": fold_vietnamese(str(chunk["heading"])),
                        "folded": folded,
                        "embedding": "[" + ",".join(f"{value:.8f}" for value in vector) + "]",
                    },
                )


async def validate_version(
    engine: AsyncEngine, version: str, *, allow_support: bool = False
) -> None:
    async with engine.begin() as conn:
        counts = (
            await conn.execute(
                text(
                    "select (select count(*) from knowledge.documents where corpus_version = :version),"
                    " (select count(*) from knowledge.chunks where corpus_version = :version),"
                    " (select count(*) from knowledge.chunks where corpus_version = :version and fts = ''::tsvector)"
                ),
                {"version": version},
            )
        ).one()
        if counts[0] == 0 or counts[1] == 0 or counts[2]:
            raise ValueError("corpus failed structural validation")
        bad = (
            await conn.execute(
                text(
                    "select count(*) from knowledge.documents d"
                    " where d.corpus_version = :version and d.licence_class not in ('open_reuse', 'authored')"
                ),
                {"version": version},
            )
        ).scalar_one()
        if bad:
            raise ValueError("corpus contains a forbidden licence class")
        weak = (
            await conn.execute(
                text(
                    "select count(*) from knowledge.chunks where corpus_version = :version"
                    " and abs(sqrt((embedding <#> embedding) * -1) - 1) > 0.001"
                ),
                {"version": version},
            )
        ).scalar_one()
        if weak:
            raise ValueError("embedding norm is outside the accepted range")
        stale = (
            await conn.execute(
                text(
                    "select count(*) from knowledge.documents where corpus_version = :version"
                    " and (applicability = '' or last_reviewed > current_date)"
                ),
                {"version": version},
            )
        ).scalar_one()
        if stale:
            raise ValueError("document review metadata is invalid")
        texts = (
            await conn.execute(
                text("select text from knowledge.chunks where corpus_version = :version"),
                {"version": version},
            )
        ).scalars()
        if any(_EMAIL.search(value) or _PHONE.search(value) for value in texts):
            raise ValueError("corpus failed the personal-data scan")
        if not allow_support:
            topics = (
                await conn.execute(
                    text(
                        "select topic, count(distinct document_id) from knowledge.documents d,"
                        " unnest(d.topics) as topic where d.corpus_version = :version group by topic"
                    ),
                    {"version": version},
                )
            ).all()
            counts = {str(topic): int(count) for topic, count in topics}
            missing = [
                topic
                for topic in (
                    "definition",
                    "physical",
                    "verbal-social",
                    "exclusion",
                    "cyber",
                    "evidence",
                    "help-seeking",
                    "school-procedure-vn",
                    "legal-vn",
                    "bystander",
                    "emotional-impact",
                    "parents-teachers",
                    "platform-reporting",
                    "urgent-safety",
                )
                if counts.get(topic, 0) == 0
            ]
            if missing:
                raise ValueError("corpus is missing a core topic")
        await conn.execute(
            text(
                "update knowledge.corpus_versions set status = 'validated', validated_at = now()"
                " where version = :version and status = 'building'"
            ),
            {"version": version},
        )


async def publish_version(engine: AsyncEngine, version: str) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text("select pg_advisory_xact_lock(:a, :b)"), {"a": _LOCK_A, "b": _LOCK_B}
        )
        await conn.execute(text("select version from knowledge.corpus_versions for update"))
        status = (
            await conn.execute(
                text("select status from knowledge.corpus_versions where version = :version"),
                {"version": version},
            )
        ).scalar_one_or_none()
        if status is None:
            raise ValueError("corpus version was not found")
        if status == "published":
            return
        if status != "validated":
            raise ValueError("only a validated corpus can be published")
        await conn.execute(
            text(
                "update knowledge.corpus_versions set status = 'retired', retired_at = now()"
                " where status = 'published'"
            )
        )
        await conn.execute(
            text(
                "update knowledge.corpus_versions set status = 'published', published_at = now()"
                " where version = :version"
            ),
            {"version": version},
        )


async def rollback_version(engine: AsyncEngine, version: str) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text("select pg_advisory_xact_lock(:a, :b)"), {"a": _LOCK_A, "b": _LOCK_B}
        )
        await conn.execute(text("select version from knowledge.corpus_versions for update"))
        status = (
            await conn.execute(
                text("select status from knowledge.corpus_versions where version = :version"),
                {"version": version},
            )
        ).scalar_one_or_none()
        if status is None:
            raise ValueError("rollback target was not found")
        if status != "retired":
            raise ValueError("rollback target must be retired")
        await conn.execute(
            text(
                "update knowledge.corpus_versions set status = 'retired', retired_at = now()"
                " where status = 'published'"
            )
        )
        await conn.execute(
            text(
                "update knowledge.corpus_versions set status = 'published', published_at = now(),"
                " retired_at = null where version = :version"
            ),
            {"version": version},
        )


def seed_synthetic(target: str) -> int:
    root = Path("agent/ingestion/synthetic/contract_corpus.json")
    loaded = cast(object, json.loads(root.read_text(encoding="utf-8")))
    if not isinstance(loaded, dict):
        raise ValueError("synthetic corpus is not an object")
    digest = hashlib.sha256(root.read_bytes()).hexdigest()
    payload = {str(key): value for key, value in cast(dict[object, object], loaded).items()}
    return asyncio.run(seed_corpus(target, payload, digest))


async def seed_corpus(target: str, payload: dict[str, Any], digest: str) -> int:
    chunks = cast(list[object], payload["chunks"]) if isinstance(payload["chunks"], list) else []
    if not chunks:
        raise ValueError("synthetic chunks are missing")
    texts: list[str] = []
    for chunk in chunks:
        if isinstance(chunk, dict):
            texts.append(str(cast(dict[str, object], chunk)["text"]))
    vectors = await HashingEmbedder().embed_documents(texts)
    engine = engine_for(target)
    version = str(payload["version"])
    try:
        await store_records(
            engine,
            version=version,
            manifest_sha256=digest,
            embedding_model="hashing",
            sources=cast(list[dict[str, object]], payload["sources"]),
            documents=cast(list[dict[str, object]], payload["documents"]),
            chunks=cast(list[dict[str, object]], chunks),
            vectors=vectors,
        )
        status = await _version_status(engine, version)
        if status == "published":
            return 0
        if status == "retired":
            await rollback_version(engine, version)
            return 0
        if status == "building":
            await validate_version(engine, version, allow_support=True)
        await publish_version(engine, version)
    finally:
        await engine.dispose()
    return 0


async def _version_status(engine: AsyncEngine, version: str) -> str:
    async with engine.connect() as conn:
        status = (
            await conn.execute(
                text("select status from knowledge.corpus_versions where version = :version"),
                {"version": version},
            )
        ).scalar_one()
    return str(status)


def dispatch(args: argparse.Namespace) -> int:
    from safevoice_agent.knowledge.ingest.commands import dispatch as run_command

    return run_command(args)


def _as_date(value: object) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))
