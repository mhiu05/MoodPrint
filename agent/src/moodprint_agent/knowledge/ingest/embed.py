"""Embed a built corpus into ``vectors.f32`` with a content-addressed cache."""

from __future__ import annotations

import hashlib
import json
import struct
from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path
from typing import cast

from moodprint_agent.knowledge.embedder import EmbeddingCache

EmbedBatch = Callable[[list[str]], Awaitable[list[list[float]]]]


def _content_digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def read_jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    raw = path.read_text(encoding="utf-8")
    if not raw.strip():
        return rows
    for line in raw.splitlines():
        if not line.strip():
            continue
        loaded = json.loads(line)
        if not isinstance(loaded, dict):
            raise ValueError(f"{path.name} row is not an object")
        rows.append({str(key): value for key, value in cast(dict[object, object], loaded).items()})
    return rows


def load_chunks(build_dir: Path) -> list[dict[str, object]]:
    path = build_dir / "chunks.jsonl"
    if not path.is_file():
        raise ValueError("chunks.jsonl is missing")
    rows = read_jsonl(path)
    if not rows:
        raise ValueError("chunks.jsonl is empty")
    for row in rows:
        if not isinstance(row.get("text"), str) or not isinstance(row.get("chunk_id"), str):
            raise ValueError("chunk row is missing text or chunk_id")
    return rows


async def embed_missing(
    texts: Sequence[str],
    embed_batch: EmbedBatch,
    cache: EmbeddingCache,
    *,
    model: str,
    dims: int,
    input_type: str,
    batch_size: int,
) -> tuple[list[list[float]], int]:
    """Return vectors aligned with ``texts`` and the number of cache hits.

    Completed batches are cached before the next batch starts, so a later run
    resumes after a partial failure.
    """

    if batch_size < 1:
        raise ValueError("batch size must be positive")
    output: list[list[float] | None] = [None] * len(texts)
    missing: list[int] = []
    for index, text in enumerate(texts):
        cached = cache.get(model, dims, input_type, _content_digest(text))
        if cached is None:
            missing.append(index)
        elif len(cached) != dims:
            missing.append(index)
        else:
            output[index] = cached
    hits = len(texts) - len(missing)
    for start in range(0, len(missing), batch_size):
        indexes = missing[start : start + batch_size]
        vectors = await embed_batch([texts[index] for index in indexes])
        if len(vectors) != len(indexes):
            raise ValueError("embedder returned the wrong number of vectors")
        for index, vector in zip(indexes, vectors, strict=True):
            if len(vector) != dims:
                raise ValueError("embedding dimensions did not match")
            cache.put(model, dims, input_type, _content_digest(texts[index]), vector)
            output[index] = vector
    if any(row is None for row in output):
        raise ValueError("embedding batch did not cover every chunk")
    return [row for row in output if row is not None], hits


def write_vectors(path: Path, vectors: Sequence[Sequence[float]]) -> None:
    blob = bytearray()
    for vector in vectors:
        blob.extend(struct.pack(f"<{len(vector)}f", *vector))
    path.write_bytes(blob)


def read_vectors(path: Path, count: int, dims: int) -> list[list[float]]:
    raw = path.read_bytes()
    expected = count * dims * 4
    if len(raw) != expected:
        raise ValueError("vectors.f32 does not match the chunk count")
    vectors: list[list[float]] = []
    for index in range(count):
        offset = index * dims * 4
        vectors.append(list(struct.unpack_from(f"<{dims}f", raw, offset)))
    return vectors
