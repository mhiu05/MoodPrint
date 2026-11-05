"""Offline-first, single-host campaign ledger; no provider client or paid CLI command.

All reservations are permanent. Transport adapters must enforce the declared input
bound and issue exactly one physical gpt-6-luna request without SDK retries/tools.
This module is not application-wide accounting or proof of account attestations.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal, localcontext
from pathlib import Path

CAP = Decimal(3)
MODEL = "gpt-6-luna"


def _money(value):
    # Never accept binary floats, scientific notation, NaN or excessive precision.
    if not isinstance(value, str) or not re.fullmatch(
        r"\d{1,12}(?:\.\d{1,18})?", value
    ):
        raise ValueError("USD values require finite nonnegative decimal strings")
    return Decimal(value)


def _text(value):
    return (
        format(value, "f").rstrip("0").rstrip(".")
        if "." in format(value, "f")
        else str(value)
    )


def _validate(attestation, now):
    try:
        if any(
            attestation.get(key) != value
            for key, value in {
                "environment": "staging",
                "model": MODEL,
                "currency": "USD",
            }.items()
        ):
            raise ValueError("only staging gpt-6-luna USD campaigns are supported")
        for key in (
            "model_access_verified",
            "account_pricing_verified",
            "quota_verified",
        ):
            if attestation.get(key) is not True:
                raise ValueError(f"unverified precondition: {key}")
        for key in ("rpm", "tpm"):
            if type(attestation.get(key)) is not int or attestation[key] <= 0:
                raise ValueError(f"unverified quota: {key}")
        if (
            not isinstance(attestation.get("pricing_version"), str)
            or not attestation["pricing_version"].strip()
        ):
            raise ValueError("pricing version required")
        if not re.fullmatch(r"[a-f0-9]{64}", attestation.get("evidence_sha256", "")):
            raise ValueError("sanitized account evidence hash required")
        for key in (
            "input_per_million",
            "cache_write_per_million",
            "output_per_million",
        ):
            rate = _money(attestation[key])
            if rate <= 0 or rate.as_tuple().exponent < -12:
                raise ValueError(
                    "positive verified maximum rates with at most 12 decimal places required"
                )
        expiry = datetime.fromisoformat(attestation["expires_at"])
        if expiry.tzinfo is None or expiry <= now():
            raise ValueError("account/pricing attestation expired")
    except (KeyError, TypeError) as exc:
        raise ValueError("incomplete account/pricing attestation") from exc


class Campaign:
    """Durable cumulative cap for cooperating processes using ONE canonical ledger.

    The injected transport is intentionally trusted, not a sandbox. No live adapter
    is supplied while account pricing, quota and exact-count semantics are unknown.
    """

    def __init__(self, path, now=None):
        self.path = Path(path).resolve()
        self.now = now or (lambda: datetime.now(UTC))

    @classmethod
    def create(cls, path, attestation):
        _validate(attestation, lambda: datetime.now(UTC))
        campaign = cls(path)
        # Never truncate/reinitialize an existing campaign or recover a broken one
        # as an empty ledger. Interrupted initialization remains fail-closed.
        descriptor = os.open(campaign.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(descriptor)
        with campaign._db() as db:
            db.execute(
                "CREATE TABLE config (id INTEGER PRIMARY KEY CHECK(id=1), attestation TEXT NOT NULL, frozen INTEGER NOT NULL DEFAULT 0)"
            )
            db.execute(
                "CREATE TABLE attempts (attempt_id TEXT PRIMARY KEY, reserved_usd TEXT NOT NULL, input_tokens INTEGER NOT NULL, max_output_tokens INTEGER NOT NULL, state TEXT NOT NULL, actual_usd TEXT)"
            )
            db.execute(
                "INSERT INTO config(id, attestation) VALUES (1, ?)",
                (json.dumps(attestation, sort_keys=True),),
            )
            db.execute("PRAGMA user_version=1")
        return campaign

    @classmethod
    def open(cls, path, now=None):
        campaign = cls(path, now)
        with campaign._db() as db:
            campaign._config(db)
        return campaign

    @contextmanager
    def _db(self):
        if not self.path.is_file():
            raise FileNotFoundError(self.path)
        # mode=rw prevents accidental reset after deletion between existence check
        # and connect. SQLite rollback journal + FULL protects committed holds.
        db = sqlite3.connect(
            self.path.as_uri() + "?mode=rw", uri=True, timeout=30, isolation_level=None
        )
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def _config(self, db, *, fresh=False):
        if db.execute("PRAGMA user_version").fetchone()[0] != 1:
            raise ValueError("uninitialized or unsupported campaign ledger")
        row = db.execute("SELECT attestation, frozen FROM config WHERE id=1").fetchone()
        if row is None:
            raise ValueError("missing campaign configuration")
        attestation = json.loads(row["attestation"])
        if fresh:
            _validate(attestation, self.now)
            if row["frozen"]:
                raise ValueError("campaign frozen after accounting mismatch")
        return attestation, bool(row["frozen"])

    def reserve(self, attempt_id, *, input_tokens, max_output_tokens):
        if not isinstance(attempt_id, str) or not re.fullmatch(
            r"[A-Za-z0-9_.:-]{1,128}", attempt_id
        ):
            raise ValueError("sanitized unique physical attempt ID required")
        if type(input_tokens) is not int or not 0 <= input_tokens <= 64000:
            raise ValueError("input bound must be an integer at most 64000")
        if type(max_output_tokens) is not int or not 1 <= max_output_tokens <= 1200:
            raise ValueError("output bound must be an integer from 1 to 1200")
        with self._db() as db, localcontext() as ctx:
            ctx.prec = 60
            attestation, _ = self._config(db, fresh=True)
            rate = max(
                _money(attestation["input_per_million"]),
                _money(attestation["cache_write_per_million"]),
            )
            cost = (
                input_tokens * rate
                + max_output_tokens * _money(attestation["output_per_million"])
            ) / Decimal(1000000)
            held = sum(
                (
                    _money(row[0])
                    for row in db.execute("SELECT reserved_usd FROM attempts")
                ),
                Decimal(0),
            )
            if held + cost > CAP:
                raise ValueError("cumulative campaign cap of USD 3 exceeded")
            try:
                db.execute(
                    "INSERT INTO attempts VALUES (?, ?, ?, ?, 'reserved', NULL)",
                    (attempt_id, _text(cost), input_tokens, max_output_tokens),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError(
                    "physical attempt ID already reserved; retries need a new hold"
                ) from exc
        return {"attempt_id": attempt_id, "reserved_usd": _text(cost)}

    def dispatch(self, attempt_id, transport):
        # The durable claim commits BEFORE invoking any caller-owned wire code.
        with self._db() as db:
            self._config(db, fresh=True)
            row = db.execute(
                "SELECT * FROM attempts WHERE attempt_id=?", (attempt_id,)
            ).fetchone()
            if row is None or row["state"] != "reserved":
                raise ValueError("attempt is not dispatchable")
            db.execute(
                "UPDATE attempts SET state='dispatching' WHERE attempt_id=?",
                (attempt_id,),
            )
            request = {
                "model": MODEL,
                "max_output_tokens": row["max_output_tokens"],
                "service_tier": "default",
                "store": False,
            }
        try:
            result = transport(request)
        except BaseException:
            self._finish(attempt_id, "unknown")
            raise
        self._finish(attempt_id, "completed")
        return result

    def _finish(self, attempt_id, state):
        with self._db() as db:
            db.execute(
                "UPDATE attempts SET state=? WHERE attempt_id=? AND state='dispatching'",
                (state, attempt_id),
            )

    def cancel(self, attempt_id):
        # Even a known pre-wire cancellation keeps its full hold. There is no
        # release/refund API, so uncertain usage cannot accidentally become credit.
        with self._db() as db:
            changed = db.execute(
                "UPDATE attempts SET state='cancelled' WHERE attempt_id=? AND state='reserved'",
                (attempt_id,),
            ).rowcount
            if changed != 1:
                raise ValueError("only an undispatched reservation may be cancelled")

    def record_actual(self, attempt_id, usd):
        amount = _money(usd)
        exceeded = False
        with self._db() as db:
            row = db.execute(
                "SELECT * FROM attempts WHERE attempt_id=?", (attempt_id,)
            ).fetchone()
            if row is None or row["state"] not in {
                "completed",
                "unknown",
                "dispatching",
            }:
                raise ValueError("actual requires a dispatched physical attempt")
            if row["actual_usd"] is not None:
                raise ValueError("actual is immutable once recorded")
            exceeded = amount > _money(row["reserved_usd"])
            db.execute(
                "UPDATE attempts SET actual_usd=? WHERE attempt_id=?",
                (_text(amount), attempt_id),
            )
            if exceeded:
                db.execute("UPDATE config SET frozen=1 WHERE id=1")
        # Freeze must commit before surfacing the error.
        if exceeded:
            raise ValueError("actual cost exceeds reservation; campaign frozen")

    def status(self):
        with self._db() as db, localcontext() as ctx:
            ctx.prec = 60
            attestation, frozen = self._config(db)
            attempts = [
                dict(row) for row in db.execute("SELECT * FROM attempts ORDER BY rowid")
            ]
            held = sum((_money(row["reserved_usd"]) for row in attempts), Decimal(0))
            if held > CAP:
                raise ValueError("ledger liability exceeds campaign cap")
            return {
                "currency": "USD",
                "cap_usd": "3",
                "held_usd": _text(held),
                "remaining_usd": _text(CAP - held),
                "frozen": frozen,
                "model": MODEL,
                "pricing_version": attestation["pricing_version"],
                "attempts": attempts,
            }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["status"])
    parser.add_argument("ledger", type=Path)
    args = parser.parse_args()
    print(json.dumps(Campaign.open(args.ledger).status(), indent=2))


if __name__ == "__main__":
    main()
