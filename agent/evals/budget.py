"""Owner-approved spending gate for every paid model request.

Nothing here trusts a listed price or an API key as permission to spend. A request is sent only
when a budget file approved by the owner is valid, unexpired, in scope, and the *worst case* of
this request still fits under every cap. The reservation is written to an append-only ledger
before the request leaves the process; usage reconciles it afterwards and an unknown outcome
keeps the conservative hold. Ledger lines never contain prompts, outputs, keys or URLs.
"""

import json
import os
import threading
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final, cast
from uuid import uuid4

import httpx

APPROVED_MODEL: Final = "gpt-6-luna"
PAID_HOST: Final = "api.openai.com"
PAID_PATH_PREFIX: Final = "/v1/responses"
DEFAULT_BUDGET_PATH: Final = Path(".local/eval-budget.json")
DEFAULT_LEDGER_PATH: Final = Path(".local/eval-spend.jsonl")
EXIT_BUDGET: Final = 3
_MAX_BODY_SCAN: Final = 8 * 1024 * 1024


class BudgetError(Exception):
    """A paid request must not be sent."""

    exit_code = EXIT_BUDGET


class BudgetInvalid(BudgetError):
    """The budget file is missing, malformed, expired, out of scope or not owner-approved."""


class BudgetExhausted(BudgetError):
    """This request would exceed an owner cap."""


@dataclass(frozen=True, slots=True)
class Prices:
    input_per_mtok: float
    cached_input_per_mtok: float
    output_per_mtok: float
    max_input_tokens: int
    service_tier: str
    verified_on: str


@dataclass(frozen=True, slots=True)
class Budget:
    approved_by: str
    approved_on: str
    model: str
    max_usd: float
    max_tokens_total: int
    max_tokens_per_run: int
    max_calls_total: int
    max_output_tokens_per_request: int
    scopes: tuple[str, ...]
    scope: str
    expires_on: datetime
    prices: Prices


@dataclass(frozen=True, slots=True)
class Reservation:
    id: str
    run_id: str
    tokens: int
    usd: float


def _number(doc: dict[str, Any], key: str, *, integer: bool, minimum: float = 0) -> float:
    value = doc.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BudgetInvalid(f"{key} must be filled in by the owner as a number")
    if integer and not isinstance(value, int):
        raise BudgetInvalid(f"{key} must be an integer")
    if value <= minimum:
        raise BudgetInvalid(f"{key} must be positive")
    return float(value)


def _text(doc: dict[str, Any], key: str) -> str:
    value = doc.get(key)
    if not isinstance(value, str) or not value.strip() or value.strip().startswith("<"):
        raise BudgetInvalid(f"{key} is missing or still a template placeholder")
    return value.strip()


def load_budget(path: Path, *, scope: str, now: datetime | None = None) -> Budget:
    if not path.is_file():
        raise BudgetInvalid("no owner-approved budget file; paid calls are blocked")
    try:
        raw: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise BudgetInvalid("budget file is not valid JSON") from error
    if not isinstance(raw, dict):
        raise BudgetInvalid("budget file must be a JSON object")
    doc = cast(dict[str, Any], raw)
    model = _text(doc, "model")
    if model != APPROVED_MODEL:
        raise BudgetInvalid(f"only {APPROVED_MODEL} may be budgeted")
    scopes_raw = doc.get("scopes")
    if not isinstance(scopes_raw, list) or not all(
        isinstance(item, str) for item in cast(list[Any], scopes_raw)
    ):
        raise BudgetInvalid("scopes must be a list of names")
    scopes = tuple(cast(list[str], scopes_raw))
    if scope not in scopes:
        raise BudgetInvalid(f"scope {scope!r} is not approved")
    expiry_text = _text(doc, "expires_on")
    try:
        expires_on = datetime.fromisoformat(expiry_text)
    except ValueError as error:
        raise BudgetInvalid("expires_on must be an ISO instant") from error
    if expires_on.tzinfo is None:
        raise BudgetInvalid("expires_on must carry an explicit UTC offset")
    if expires_on <= (now or datetime.now(UTC)):
        raise BudgetInvalid("budget has expired")
    pricing_raw = doc.get("pricing")
    if not isinstance(pricing_raw, dict):
        raise BudgetInvalid("pricing snapshot is required")
    pricing = cast(dict[str, Any], pricing_raw)
    table_raw = pricing.get("price_usd_per_mtok")
    if not isinstance(table_raw, dict):
        raise BudgetInvalid("price_usd_per_mtok is required")
    table = cast(dict[str, Any], table_raw)
    tier = _text(pricing, "service_tier")
    if tier != "default":
        raise BudgetInvalid("only the default service tier has a verified price table")
    prices = Prices(
        input_per_mtok=_number(table, "input", integer=False),
        cached_input_per_mtok=_number(table, "cached_input", integer=False),
        output_per_mtok=_number(table, "output", integer=False),
        max_input_tokens=int(_number(pricing, "max_input_tokens", integer=True)),
        service_tier=tier,
        verified_on=_text(pricing, "verified_on"),
    )
    return Budget(
        approved_by=_text(doc, "approved_by"),
        approved_on=_text(doc, "approved_on"),
        model=model,
        max_usd=_number(doc, "max_usd", integer=False),
        max_tokens_total=int(_number(doc, "max_tokens_total", integer=True)),
        max_tokens_per_run=int(_number(doc, "max_tokens_per_run", integer=True)),
        max_calls_total=int(_number(doc, "max_calls_total", integer=True)),
        max_output_tokens_per_request=int(
            _number(doc, "max_output_tokens_per_request", integer=True)
        ),
        scopes=scopes,
        scope=scope,
        expires_on=expires_on,
        prices=prices,
    )


@dataclass(slots=True)
class _Entry:
    run_id: str
    tokens: int
    usd: float
    state: str  # reserved | unknown | reconciled


class BudgetLedger:
    """Append-only JSONL ledger; state is rebuilt from disk so several processes share it."""

    def __init__(self, budget: Budget, path: Path = DEFAULT_LEDGER_PATH) -> None:
        self.budget = budget
        self.path = path
        self._thread_lock = threading.Lock()
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._locked():
            self._entries = self._replay()

    # -- derived totals -------------------------------------------------------------------
    @property
    def reserved_calls(self) -> int:
        return len(self._entries)

    @property
    def unknown_calls(self) -> int:
        return sum(1 for e in self._entries.values() if e.state == "unknown")

    @property
    def reserved_tokens(self) -> int:
        return sum(e.tokens for e in self._entries.values() if e.state != "reconciled")

    @property
    def spent_tokens(self) -> int:
        return sum(e.tokens for e in self._entries.values() if e.state == "reconciled")

    @property
    def committed_usd(self) -> float:
        return sum(e.usd for e in self._entries.values())

    # -- public API -----------------------------------------------------------------------
    def reserve(
        self, *, model: str, input_tokens: int, max_output_tokens: int, run_id: str
    ) -> Reservation:
        budget = self.budget
        if model != budget.model:
            raise BudgetError("model is not the approved model")
        if max_output_tokens < 1 or max_output_tokens > budget.max_output_tokens_per_request:
            raise BudgetError("max output tokens must be set and within the owner cap")
        if input_tokens < 0 or input_tokens > budget.prices.max_input_tokens:
            raise BudgetError("input exceeds the verified short-context price table")
        if budget.expires_on <= datetime.now(UTC):
            raise BudgetInvalid("budget has expired")
        tokens = input_tokens + max_output_tokens
        # Worst case: nothing cached, every output token produced.
        usd = (
            input_tokens * budget.prices.input_per_mtok
            + max_output_tokens * budget.prices.output_per_mtok
        ) / 1_000_000
        with self._locked():
            self._entries = self._replay()
            if tokens > budget.max_tokens_per_run:
                raise BudgetExhausted("request exceeds the per-run token cap")
            if len(self._entries) + 1 > budget.max_calls_total:
                raise BudgetExhausted("call cap reached")
            if self.spent_tokens + self.reserved_tokens + tokens > budget.max_tokens_total:
                raise BudgetExhausted("token cap reached")
            run_tokens = sum(e.tokens for e in self._entries.values() if e.run_id == run_id)
            if run_tokens + tokens > budget.max_tokens_per_run:
                raise BudgetExhausted("per-run token cap reached")
            if self.committed_usd + usd > budget.max_usd + 1e-12:
                raise BudgetExhausted("USD cap reached")
            reservation = Reservation(uuid4().hex, run_id, tokens, usd)
            self._append(
                {
                    "kind": "reserve",
                    "id": reservation.id,
                    "run_id": run_id,
                    "tokens": tokens,
                    "usd": usd,
                    "scope": budget.scope,
                    "model": model,
                }
            )
            self._entries[reservation.id] = _Entry(run_id, tokens, usd, "reserved")
            return reservation

    def reconcile(
        self,
        reservation: Reservation,
        *,
        input_tokens: int,
        output_tokens: int,
        cached_input_tokens: int = 0,
    ) -> None:
        prices = self.budget.prices
        cached = min(cached_input_tokens, input_tokens)
        usd = (
            (input_tokens - cached) * prices.input_per_mtok
            + cached * prices.cached_input_per_mtok
            + output_tokens * prices.output_per_mtok
        ) / 1_000_000
        tokens = input_tokens + output_tokens
        with self._locked():
            self._append({"kind": "reconcile", "id": reservation.id, "tokens": tokens, "usd": usd})
            entry = self._entries.get(reservation.id)
            if entry is not None:
                entry.tokens, entry.usd, entry.state = tokens, usd, "reconciled"

    def mark_unknown(self, reservation: Reservation) -> None:
        """Timeout, transport error or missing usage: keep the conservative hold."""
        with self._locked():
            self._append({"kind": "unknown", "id": reservation.id})
            entry = self._entries.get(reservation.id)
            if entry is not None and entry.state == "reserved":
                entry.state = "unknown"

    # -- persistence ----------------------------------------------------------------------
    def _append(self, record: dict[str, Any]) -> None:
        record["at"] = datetime.now(UTC).isoformat()
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, separators=(",", ":")) + "\n")

    def _replay(self) -> dict[str, _Entry]:
        entries: dict[str, _Entry] = {}
        if not self.path.is_file():
            return entries
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = cast(dict[str, Any], json.loads(line))
            entry = entries.get(str(record.get("id")))
            kind = record.get("kind")
            if kind == "reserve":
                entries[str(record["id"])] = _Entry(
                    str(record["run_id"]), int(record["tokens"]), float(record["usd"]), "reserved"
                )
            elif kind == "reconcile" and entry is not None:
                entry.tokens, entry.usd, entry.state = (
                    int(record["tokens"]),
                    float(record["usd"]),
                    "reconciled",
                )
            elif kind == "unknown" and entry is not None and entry.state == "reserved":
                entry.state = "unknown"
        return entries

    def _locked(self) -> "_FileLock":
        return _FileLock(self.path.with_suffix(self.path.suffix + ".lock"), self._thread_lock)


class _FileLock:
    """Cross-process mutex via exclusive file creation (also serialises threads)."""

    def __init__(self, path: Path, thread_lock: threading.Lock) -> None:
        self._path, self._thread_lock = path, thread_lock

    def __enter__(self) -> None:
        self._thread_lock.acquire()
        deadline = time.monotonic() + 30
        while True:
            try:
                os.close(os.open(self._path, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
                return
            except FileExistsError:
                if time.monotonic() > deadline:
                    try:  # a crashed holder; the lock only guards a tiny critical section
                        self._path.unlink()
                    except OSError:
                        pass
                time.sleep(0.01)

    def __exit__(self, *_: object) -> None:
        try:
            self._path.unlink()
        finally:
            self._thread_lock.release()


# -- HTTP guard -------------------------------------------------------------------------------
def estimate_input_tokens(body: bytes) -> int:
    """Deliberately high: one token per 3 bytes of the whole JSON body."""
    return max(1, len(body) // 3 + 1)


def _usage_from_payload(payload: Any) -> tuple[int, int, int] | None:
    if not isinstance(payload, dict):
        return None
    data = cast(dict[str, Any], payload)
    response = data.get("response")
    usage_raw = (
        cast(dict[str, Any], response).get("usage")
        if isinstance(response, dict)
        else data.get("usage")
    )
    if not isinstance(usage_raw, dict):
        return None
    usage = cast(dict[str, Any], usage_raw)
    input_tokens, output_tokens = usage.get("input_tokens"), usage.get("output_tokens")
    if not isinstance(input_tokens, int) or not isinstance(output_tokens, int):
        return None
    details = usage.get("input_tokens_details")
    cached = 0
    if isinstance(details, dict):
        value = cast(dict[str, Any], details).get("cached_tokens")
        cached = value if isinstance(value, int) else 0
    return input_tokens, output_tokens, cached


def parse_usage(body: bytes) -> tuple[int, int, int] | None:
    """Usage from a JSON response or the final ``response.completed`` SSE event."""
    text = body.decode("utf-8", errors="replace").strip()
    if not text:
        return None
    if text.startswith(("event:", "data:")):
        found: tuple[int, int, int] | None = None
        for line in text.splitlines():
            if line.startswith("data:") and "usage" in line:
                try:
                    parsed = _usage_from_payload(json.loads(line[5:].strip()))
                except ValueError:
                    continue
                found = parsed or found
        return found
    try:
        return _usage_from_payload(json.loads(text))
    except ValueError:
        return None


class _MeteredStream(httpx.AsyncByteStream):
    def __init__(
        self, inner: httpx.AsyncByteStream, ledger: BudgetLedger, reservation: Reservation, ok: bool
    ) -> None:
        self._inner, self._ledger, self._reservation, self._ok = inner, ledger, reservation, ok
        self._body = bytearray()
        self._settled = False

    async def __aiter__(self) -> AsyncIterator[bytes]:
        try:
            async for chunk in self._inner:
                if len(self._body) < _MAX_BODY_SCAN:
                    self._body.extend(chunk)
                yield chunk
        except BaseException:
            self._settle(None)
            raise
        self._settle(parse_usage(bytes(self._body)) if self._ok else None)

    async def aclose(self) -> None:
        try:
            await self._inner.aclose()
        finally:
            self._settle(None)

    def _settle(self, usage: tuple[int, int, int] | None) -> None:
        if self._settled:
            return
        self._settled = True
        if usage is None:
            self._ledger.mark_unknown(self._reservation)
        else:
            self._ledger.reconcile(
                self._reservation,
                input_tokens=usage[0],
                output_tokens=usage[1],
                cached_input_tokens=usage[2],
            )


class GuardedTransport(httpx.AsyncBaseTransport):
    """Wrap any httpx transport so a Responses request is reserved before it is sent.

    Every HTTP attempt (including SDK retries, compaction, vision and coach calls) passes through
    here, so ``max_calls_total`` counts real requests. Requests that are not to the paid Responses
    endpoint, use another model, ask the provider to store the response, or omit an output cap
    are refused without being sent.
    """

    def __init__(self, inner: httpx.AsyncBaseTransport, ledger: BudgetLedger, *, run_id: str):
        self._inner, self._ledger, self._run_id = inner, ledger, run_id

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if request.url.host != PAID_HOST or not request.url.path.startswith(PAID_PATH_PREFIX):
            raise BudgetError("only the Responses endpoint is budgeted; request refused")
        body = await request.aread()
        try:
            parsed: Any = json.loads(body)
        except ValueError as error:
            raise BudgetError("request body is not JSON; refused") from error
        if not isinstance(parsed, dict):
            raise BudgetError("request body must be an object")
        payload = cast(dict[str, Any], parsed)
        if payload.get("store") is not False:
            raise BudgetError("store=False is mandatory; request refused")
        model = payload.get("model")
        output_cap = payload.get("max_output_tokens")
        if not isinstance(model, str) or isinstance(output_cap, bool):
            raise BudgetError("model and max_output_tokens are required; request refused")
        if not isinstance(output_cap, int):
            raise BudgetError("max_output_tokens is required; request refused")
        reservation = self._ledger.reserve(
            model=model,
            input_tokens=estimate_input_tokens(body),
            max_output_tokens=output_cap,
            run_id=self._run_id,
        )
        try:
            response = await self._inner.handle_async_request(request)
        except BaseException:
            self._ledger.mark_unknown(reservation)
            raise
        stream = cast(httpx.AsyncByteStream, response.stream)
        return httpx.Response(
            status_code=response.status_code,
            headers=response.headers,
            stream=_MeteredStream(stream, self._ledger, reservation, response.is_success),
            extensions=response.extensions,
        )
