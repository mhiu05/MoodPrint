"""Provider transports for the explicitly authorized local live MVP checks.

OpenAI is composed with the existing evaluation GuardedTransport. Voyage uses
its existing, separate cumulative ledger. No new spending ledger is created.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent"))

from evals.budget import decode_body  # noqa: E402
from safevoice_agent.knowledge.ingest.budget import commit, release, reserve  # noqa: E402


class VoyageTransport(httpx.AsyncBaseTransport):
    def __init__(self, ledger: Path, *, inner: httpx.AsyncBaseTransport | None = None):
        if not ledger.is_file():
            raise ValueError("The existing cumulative Voyage ledger is required")
        self.ledger = ledger
        self.inner = inner or httpx.AsyncHTTPTransport(trust_env=False)

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if str(request.url) != "https://api.voyageai.com/v1/embeddings":
            raise ValueError("Only the authorized Voyage embeddings endpoint is permitted")
        payload = json.loads(await request.aread())
        inputs = payload.get("input")
        if (
            payload.get("model") != "voyage-4"
            or payload.get("output_dimension") != 1024
            or not isinstance(inputs, list)
            or not inputs
            or not all(isinstance(value, str) for value in inputs)
        ):
            raise ValueError("Only voyage-4 with 1024-dimensional text embeddings is authorized")
        # UTF-8 byte length plus overhead is a conservative token upper bound;
        # every provider retry is independently reserved at this HTTP boundary.
        maximum = sum(len(value.encode("utf-8")) for value in inputs) + 64
        reservation = reserve(maximum, ledger=self.ledger)
        try:
            response = await self.inner.handle_async_request(request)
            await response.aread()
        except BaseException:
            commit(reservation, None, ledger=self.ledger)
            raise
        if response.status_code in {400, 401, 403}:
            release(reservation, ledger=self.ledger)
        else:
            usage = None
            if response.is_success:
                try:
                    value = response.json().get("usage", {}).get("total_tokens")
                    if type(value) is int and 0 <= value <= maximum:
                        usage = value
                except (ValueError, AttributeError):
                    pass
            commit(reservation, usage, ledger=self.ledger)
        return response

    async def aclose(self):
        await self.inner.aclose()


class _RecordingStream(httpx.AsyncByteStream):
    def __init__(self, inner, path, request_id, status, encoding):
        self.inner, self.path = inner, path
        self.request_id, self.status, self.encoding = request_id, status, encoding
        self.body = bytearray()
        self.recorded = False

    async def __aiter__(self):
        try:
            async for chunk in self.inner:
                if len(self.body) < 8 * 1024 * 1024:
                    self.body.extend(chunk)
                yield chunk
        finally:
            self.record()

    def record(self):
        if self.recorded:
            return
        self.recorded = True
        raw = decode_body(bytes(self.body), self.encoding)
        response = None
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                response = parsed
        except ValueError:
            for line in raw.decode("utf-8", errors="replace").splitlines():
                if not line.startswith("data:"):
                    continue
                try:
                    event = json.loads(line[5:].strip())
                    if event.get("type") in {"response.completed", "response.incomplete"}:
                        response = event.get("response")
                except (ValueError, AttributeError):
                    continue
        selected = (
            {
                key: response.get(key)
                for key in ("id", "model", "status", "usage", "output", "incomplete_details")
            }
            if isinstance(response, dict)
            else None
        )
        row = {
            "at": datetime.now(UTC).isoformat(),
            "request_id": self.request_id,
            "http_status": self.status,
            "response": selected,
            "response_body_sha256": hashlib.sha256(raw).hexdigest(),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    async def aclose(self):
        try:
            await self.inner.aclose()
        finally:
            self.record()


class RecordingTransport(httpx.AsyncBaseTransport):
    def __init__(self, inner: httpx.AsyncBaseTransport, path: Path):
        self.inner, self.path = inner, path

    async def handle_async_request(self, request):
        response = await self.inner.handle_async_request(request)
        return httpx.Response(
            response.status_code,
            headers=response.headers,
            stream=_RecordingStream(
                response.stream,
                self.path,
                response.headers.get("x-request-id"),
                response.status_code,
                response.headers.get("content-encoding"),
            ),
            extensions=response.extensions,
        )

    async def aclose(self):
        await self.inner.aclose()


class DefaultTierTransport(httpx.AsyncBaseTransport):
    """Make the verified standard processing tier explicit before reservation."""

    def __init__(self, inner):
        self.inner = inner

    async def handle_async_request(self, request):
        payload = json.loads(await request.aread())
        if payload.get("service_tier") not in {None, "default"}:
            raise ValueError("Only the verified default OpenAI processing tier is authorized")
        if request.url.path.rstrip("/") == "/v1/responses":
            payload["service_tier"] = "default"
            request = httpx.Request(
                request.method,
                request.url,
                headers={k: v for k, v in request.headers.items() if k.lower() != "content-length"},
                content=json.dumps(payload, ensure_ascii=False).encode(),
                extensions=request.extensions,
            )
        return await self.inner.handle_async_request(request)

    async def aclose(self):
        await self.inner.aclose()
