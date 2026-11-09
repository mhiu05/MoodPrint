"""Fail-closed Voyage spend ledger.

The ledger lives under ``.local/`` and must never be committed. The hard cap is
the owner's Phase 2 authorization of USD 1.00 cumulative, priced at the
voyage-4 rate published on https://docs.voyageai.com/docs/pricing
(USD 0.06 per million tokens, read 2026-11-09). Missing history is rebuilt
from the append-only spend log so a deleted state file cannot reset the total.
"""

from __future__ import annotations

import json
import os
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import cast
from uuid import uuid4

PRICE_USD_PER_MILLION = Decimal("0.06")
MAX_USD = Decimal("1.00")
_QUANT = Decimal("0.00000001")


class BudgetBlocked(RuntimeError):
    """Raised before a call that could exceed the authorized ceiling."""


def default_ledger_path() -> Path:
    return Path(".local/voyage-ledger.json")


def _money(value: Decimal | str | int) -> Decimal:
    return Decimal(str(value)).quantize(_QUANT, rounding=ROUND_HALF_UP)


def token_cost(tokens: int) -> Decimal:
    if tokens < 0:
        raise ValueError("token count cannot be negative")
    return _money(Decimal(tokens) * PRICE_USD_PER_MILLION / Decimal(1_000_000))


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _log_path(ledger: Path) -> Path:
    return ledger.with_suffix(".jsonl")


@contextmanager
def _locked(ledger: Path) -> Generator[None, None, None]:
    ledger.parent.mkdir(parents=True, exist_ok=True)
    handle = (ledger.parent / "voyage-ledger.lock").open("a+b")
    try:
        if handle.seek(0, os.SEEK_END) == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        if os.name == "nt":
            import msvcrt

            try:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
        handle.close()


def _spent_from_log(ledger: Path) -> Decimal:
    path = _log_path(ledger)
    if not path.exists():
        return Decimal("0")
    total = Decimal("0")
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = _as_state(json.loads(line))
        if row.get("kind") == "commit":
            total += _money(_text(row, "usd"))
    return _money(total)


def _append(ledger: Path, row: dict[str, object]) -> None:
    with _log_path(ledger).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _fresh(ledger: Path) -> dict[str, object]:
    spent = _spent_from_log(ledger)
    return {
        "schema": 1,
        "scope": "phase-2-voyage",
        "max_usd": str(MAX_USD),
        "price_usd_per_million_tokens": str(PRICE_USD_PER_MILLION),
        "price_source": "https://docs.voyageai.com/docs/pricing",
        "price_read_on": "2026-11-09",
        "model": "voyage-4",
        "authorization": "owner message 2026-11-09 hard cap USD 1.00 cumulative",
        "spent_usd": str(spent),
        "reserved_usd": "0",
        "reservations": {},
    }


def _as_state(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise BudgetBlocked("Voyage ledger is unreadable")
    return {str(key): item for key, item in cast(dict[object, object], value).items()}


def _text(state: dict[str, object], key: str) -> str:
    value = state.get(key, "0")
    if isinstance(value, (str, int, Decimal)):
        return str(value)
    raise BudgetBlocked("Voyage ledger field is unreadable")


def _reservation_map(state: dict[str, object]) -> dict[str, dict[str, object]]:
    raw = state.get("reservations")
    if not isinstance(raw, dict):
        raise BudgetBlocked("Voyage ledger reservations are unreadable")
    parsed: dict[str, dict[str, object]] = {}
    for key, value in cast(dict[object, object], raw).items():
        if not isinstance(key, str) or not isinstance(value, dict):
            raise BudgetBlocked("Voyage ledger reservations are unreadable")
        parsed[key] = {
            str(inner): item for inner, item in cast(dict[object, object], value).items()
        }
    state["reservations"] = parsed
    return parsed


def _read(ledger: Path) -> dict[str, object]:
    if not ledger.exists():
        state = _fresh(ledger)
        ledger.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        return state
    state = _as_state(json.loads(ledger.read_text(encoding="utf-8")))
    logged = _spent_from_log(ledger)
    if _money(_text(state, "spent_usd")) < logged:
        state["spent_usd"] = str(logged)
    if _money(_text(state, "max_usd")) != MAX_USD:
        raise BudgetBlocked("Voyage ledger cap does not match the authorized USD 1.00 ceiling")
    return state


def _write(ledger: Path, state: dict[str, object]) -> None:
    ledger.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def snapshot(ledger: Path | None = None) -> dict[str, str]:
    path = ledger or default_ledger_path()
    with _locked(path):
        state = _read(path)
    return {
        "spent_usd": str(state["spent_usd"]),
        "reserved_usd": str(state["reserved_usd"]),
        "max_usd": str(state["max_usd"]),
    }


def reserve(tokens: int, *, ledger: Path | None = None, buffer: Decimal = Decimal("1.25")) -> str:
    """Hold the maximum expected cost. Raises before any paid request if it cannot."""

    path = ledger or default_ledger_path()
    expected = token_cost(int(Decimal(tokens) * buffer) if tokens else 0)
    if expected <= 0:
        expected = token_cost(1)
    with _locked(path):
        state = _read(path)
        spent = _money(_text(state, "spent_usd"))
        reserved = _money(_text(state, "reserved_usd"))
        if spent + reserved + expected > MAX_USD:
            raise BudgetBlocked(
                "Voyage request refused: reserved cost would exceed the USD 1.00 cumulative cap"
            )
        reservation_id = uuid4().hex
        reservations = _reservation_map(state)
        reservations[reservation_id] = {"usd": str(expected), "tokens": tokens}
        state["reserved_usd"] = str(_money(reserved + expected))
        _write(path, state)
        _append(
            path,
            {
                "kind": "reserve",
                "id": reservation_id,
                "usd": str(expected),
                "tokens": tokens,
                "at": _now(),
            },
        )
        return reservation_id


def commit(reservation_id: str, actual_tokens: int | None, *, ledger: Path | None = None) -> None:
    """Record actual usage. Unknown usage keeps the full reservation."""

    path = ledger or default_ledger_path()
    with _locked(path):
        state = _read(path)
        reservations = _reservation_map(state)
        if reservation_id not in reservations:
            raise BudgetBlocked("Voyage reservation is missing; refusing to continue")
        held = reservations.pop(reservation_id)
        reserved_cost = _money(_text(held, "usd"))
        actual = reserved_cost if actual_tokens is None else token_cost(actual_tokens)
        if actual < 0:
            actual = reserved_cost
        spent = _money(_text(state, "spent_usd")) + actual
        reserved = _money(_text(state, "reserved_usd")) - reserved_cost
        if reserved < 0:
            reserved = Decimal("0")
        state["spent_usd"] = str(_money(spent))
        state["reserved_usd"] = str(_money(reserved))
        _write(path, state)
        _append(
            path,
            {
                "kind": "commit",
                "id": reservation_id,
                "usd": str(_money(actual)),
                "tokens": actual_tokens,
                "at": _now(),
            },
        )


def release(reservation_id: str, *, ledger: Path | None = None) -> None:
    """Drop a reservation after a refusal that was not billed (for example HTTP 401)."""

    path = ledger or default_ledger_path()
    with _locked(path):
        state = _read(path)
        reservations = _reservation_map(state)
        if reservation_id not in reservations:
            return
        held = reservations.pop(reservation_id)
        reserved = _money(_text(state, "reserved_usd")) - _money(_text(held, "usd"))
        state["reserved_usd"] = str(_money(reserved if reserved > 0 else Decimal("0")))
        _write(path, state)
        _append(
            path, {"kind": "release", "id": reservation_id, "usd": _text(held, "usd"), "at": _now()}
        )
