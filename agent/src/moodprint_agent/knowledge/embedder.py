"""Voyage REST embeddings, a deterministic hashing embedder, and a corpus cache."""

from __future__ import annotations

import hashlib
import logging
import math
import random
import sqlite3
from collections.abc import Awaitable, Callable, Mapping
from pathlib import Path
from typing import Protocol, cast

import httpx
from moodprint_shared.config import KnowledgeConfig
from moodprint_shared.contracts.errors import KnowledgeTimeout, KnowledgeUnavailable

from moodprint_agent.knowledge.textnorm import fold_vietnamese

log = logging.getLogger("moodprint.knowledge.embed")
VOYAGE_URL = "https://api.voyageai.com/v1/embeddings"
_MAX_ATTEMPTS = 5


class _RedactHttpFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        if "authorization" in message.casefold() or "bearer " in message.casefold():
            record.msg = "http client log redacted"
            record.args = ()
        return True


def _install_redactor() -> None:
    redactor = _RedactHttpFilter()
    for name in ("httpx", "httpcore"):
        logger = logging.getLogger(name)
        if not any(isinstance(item, _RedactHttpFilter) for item in logger.filters):
            logger.addFilter(redactor)


_install_redactor()


class QueryEmbedder(Protocol):
    async def embed_query(self, text: str) -> list[float]: ...


class DocumentEmbedder(Protocol):
    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...


class EmbedUsage:
    def __init__(self) -> None:
        self.total_tokens = 0
        self.calls = 0

    def add(self, tokens: int) -> None:
        self.total_tokens += tokens
        self.calls += 1

    @property
    def usd(self) -> float:
        return self.total_tokens * 0.06 / 1_000_000


def _normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        zero = [0.0] * len(vector)
        zero[0] = 1.0
        return zero
    return [value / norm for value in vector]


class HashingEmbedder:
    """Deterministic 1024-d vectors for CI and E2E. Not a quality model."""

    def __init__(self, dims: int = 1024) -> None:
        self.dims = dims
        self.usage = EmbedUsage()

    def _vector(self, text: str) -> list[float]:
        folded = fold_vietnamese(text) or " "
        values = [0.0] * self.dims
        grams = f"  {folded}  "
        for index in range(len(grams) - 2):
            digest = hashlib.blake2s(grams[index : index + 3].encode(), digest_size=8).digest()
            bucket = int.from_bytes(digest[:2], "little") % self.dims
            sign = 1.0 if digest[2] & 1 else -1.0
            values[bucket] += sign
        for token in folded.split():
            digest = hashlib.blake2s(token.encode(), digest_size=8).digest()
            bucket = int.from_bytes(digest[:2], "little") % self.dims
            sign = 1.0 if digest[2] & 1 else -1.0
            values[bucket] += 3.0 * sign
        return _normalize(values)

    async def embed_query(self, text: str) -> list[float]:
        return self._vector(text)

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]


class EmbeddingCache:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = path
        self._db = sqlite3.connect(path)
        self._db.execute(
            "create table if not exists embeddings ("
            "model text, dims integer, input_type text, sha256 text, vector blob, "
            "primary key (model, dims, input_type, sha256))"
        )

    def get(self, model: str, dims: int, input_type: str, digest: str) -> list[float] | None:
        row = self._db.execute(
            "select vector from embeddings where model=? and dims=? and input_type=? and sha256=?",
            (model, dims, input_type, digest),
        ).fetchone()
        if row is None:
            return None
        raw = row[0]
        count = len(raw) // 4
        return list(__import__("struct").unpack(f"<{count}f", raw))

    def put(self, model: str, dims: int, input_type: str, digest: str, vector: list[float]) -> None:
        import struct

        blob = struct.pack(f"<{len(vector)}f", *vector)
        self._db.execute(
            "insert or replace into embeddings values (?,?,?,?,?)",
            (model, dims, input_type, digest, blob),
        )
        self._db.commit()

    def close(self) -> None:
        self._db.close()


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def estimate_tokens(text: str) -> int:
    return max(1, math.ceil(len(text) / 3))


class VoyageEmbedder:
    def __init__(
        self,
        api_key: str,
        cfg: KnowledgeConfig,
        *,
        client: httpx.AsyncClient | None = None,
        cache: EmbeddingCache | None = None,
        sleeper: Callable[[float], Awaitable[None]] | None = None,
        rng: random.Random | None = None,
    ) -> None:
        self.api_key = api_key
        self.cfg = cfg
        self.cache = cache
        self.usage = EmbedUsage()
        self._client = client
        self._owns_client = client is None
        self._sleep = sleeper or _async_sleep
        self._rng = rng or random.Random(0)

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()

    async def embed_query(self, text: str) -> list[float]:
        rows = await self._embed([text], "query", self.cfg.resolved_query_model(), use_cache=False)
        return rows[0]

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = self.cfg.embedding_model
        output: list[list[float] | None] = [None] * len(texts)
        missing: list[int] = []
        for index, text in enumerate(texts):
            cached = None
            if self.cache is not None:
                cached = self.cache.get(model, self.cfg.embedding_dims, "document", _digest(text))
            if cached is None:
                missing.append(index)
            else:
                output[index] = cached
        if missing:
            fresh = await self._embed(
                [texts[index] for index in missing], "document", model, use_cache=True
            )
            for index, vector in zip(missing, fresh, strict=True):
                output[index] = vector
        return [row for row in output if row is not None]

    async def _embed(
        self, texts: list[str], input_type: str, model: str, *, use_cache: bool
    ) -> list[list[float]]:
        vectors: list[list[float]] = []
        for batch in _batches(texts, self.cfg):
            payload = {
                "model": model,
                "input": batch,
                "input_type": input_type,
                "output_dimension": self.cfg.embedding_dims,
                "truncation": False,
                "output_dtype": "float",
            }
            body = await self._post(payload)
            data = body.get("data")
            rows = cast(list[object], data) if isinstance(data, list) else []
            if len(rows) != len(batch):
                raise KnowledgeUnavailable(
                    "Embedding response was incomplete.",
                    details={"reason": "embed_config"},
                )
            usage = body.get("usage")
            tokens = 0
            if isinstance(usage, dict):
                raw_tokens = cast(dict[str, object], usage).get("total_tokens")
                if isinstance(raw_tokens, int):
                    tokens = raw_tokens
            self.usage.add(tokens)
            log.info(
                "embed_batch",
                extra={"count": len(batch), "tokens": tokens, "input_type": input_type},
            )
            for text, item in zip(batch, rows, strict=True):
                if not isinstance(item, dict):
                    raise KnowledgeUnavailable(
                        "Embedding item was not an object.",
                        details={"reason": "embed_config"},
                    )
                embedding = cast(dict[str, object], item).get("embedding")
                values = cast(list[object], embedding) if isinstance(embedding, list) else []
                if len(values) != self.cfg.embedding_dims:
                    raise KnowledgeUnavailable(
                        "Embedding dimensions did not match.",
                        details={"reason": "embed_config"},
                    )
                vector = [_as_float(value) for value in values]
                if use_cache and self.cache is not None:
                    self.cache.put(
                        model, self.cfg.embedding_dims, input_type, _digest(text), vector
                    )
                vectors.append(vector)
        return vectors

    async def _post(self, payload: Mapping[str, object]) -> dict[str, object]:
        client = self._client or httpx.AsyncClient(timeout=self.cfg.embed_request_timeout_s)
        self._client = client
        delay = 0.2
        last_status = 0
        for attempt in range(_MAX_ATTEMPTS):
            try:
                response = await client.post(
                    VOYAGE_URL,
                    json=payload,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=self.cfg.embed_request_timeout_s,
                )
            except httpx.TimeoutException as exc:
                if attempt + 1 == _MAX_ATTEMPTS:
                    raise KnowledgeTimeout() from exc
                await self._sleep(delay + self._rng.random() * 0.05)
                delay = min(delay * 2, 8)
                continue
            except httpx.HTTPError as exc:
                raise KnowledgeUnavailable(
                    "Embedding service is unavailable.",
                    details={"reason": "embed_http"},
                ) from exc
            last_status = response.status_code
            if response.status_code == 200:
                parsed = response.json()
                if isinstance(parsed, dict):
                    return {
                        str(key): value for key, value in cast(dict[object, object], parsed).items()
                    }
                raise KnowledgeUnavailable(
                    "Embedding response was not an object.",
                    details={"reason": "embed_config"},
                )
            if response.status_code in {400, 401, 403}:
                raise KnowledgeUnavailable(
                    "Embedding configuration was rejected.",
                    details={"reason": "embed_config", "status": response.status_code},
                )
            if response.status_code not in {429, 500, 502, 503, 504}:
                raise KnowledgeUnavailable(
                    "Embedding request failed.",
                    details={"reason": "embed_http", "status": response.status_code},
                )
            if attempt + 1 == _MAX_ATTEMPTS:
                break
            retry_after = response.headers.get("Retry-After")
            wait = delay
            if retry_after and retry_after.isdigit():
                wait = float(retry_after)
            await self._sleep(wait + self._rng.random() * 0.05)
            delay = min(delay * 2, 8)
        raise KnowledgeUnavailable(
            "Embedding service did not recover.",
            details={"reason": "embed_http", "status": last_status},
        )


def _batches(texts: list[str], cfg: KnowledgeConfig) -> list[list[str]]:
    batches: list[list[str]] = []
    current: list[str] = []
    tokens = 0
    for text in texts:
        cost = estimate_tokens(text)
        if current and (len(current) >= 128 or tokens + cost > 100_000):
            batches.append(current)
            current = []
            tokens = 0
        current.append(text)
        tokens += cost
    if current:
        batches.append(current)
    return batches


def _as_float(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    raise KnowledgeUnavailable(
        "Embedding value was not numeric.",
        details={"reason": "embed_config"},
    )


async def _async_sleep(seconds: float) -> None:
    import asyncio

    await asyncio.sleep(seconds)
