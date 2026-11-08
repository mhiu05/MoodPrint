"""Immutable proposal model shared by the propose_* and save_* tools.

A proposal is created by the server, never by the model. The model can only ever send a
``proposal_id`` to a write tool; the writer re-reads the stored payload, re-checks its hash and
applies exactly what the user saw in the approval dialog.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final, Literal
from uuid import UUID, uuid5

ProposalKind = Literal["case_event", "action_plan"]
ProposalStatus = Literal["proposed", "approved", "rejected", "applied", "expired", "failed"]

# Fixed namespace: the case-event UUID is a pure function of (owner, proposal).
EVENT_NAMESPACE: Final = UUID("6f1c9c1e-6d0b-4d9a-9a52-4d6f6f6f7001")

_ALLOWED: Final[dict[ProposalStatus, frozenset[ProposalStatus]]] = {
    "proposed": frozenset({"approved", "rejected", "expired", "failed"}),
    "approved": frozenset({"applied", "failed", "expired"}),
    "rejected": frozenset(),
    "applied": frozenset(),
    "expired": frozenset(),
    "failed": frozenset(),
}


@dataclass(frozen=True, slots=True)
class StoredProposal:
    id: UUID
    owner_id: UUID
    conversation_id: UUID
    run_id: UUID
    kind: ProposalKind
    target_case_id: UUID | None
    payload: dict[str, Any]
    payload_sha256: str
    preview: dict[str, Any]
    base_version: int | None
    request_key: str
    status: ProposalStatus
    result: dict[str, Any] | None
    created_at: datetime
    expires_at: datetime

    def expired(self, now: datetime) -> bool:
        return now >= self.expires_at

    def hash_matches(self) -> bool:
        return payload_sha256(self.payload) == self.payload_sha256


@dataclass(frozen=True, slots=True)
class ApplyOutcome:
    """Result of a writer. ``error`` is a stable code safe to show the model."""

    status: Literal["applied", "rejected", "expired", "failed", "conflict", "not_found"]
    result: dict[str, Any] | None = None
    error: str | None = None
    latest_version: int | None = None


def can_transition(current: ProposalStatus, target: ProposalStatus) -> bool:
    return target in _ALLOWED[current]


def canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def payload_sha256(payload: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def event_id_for(owner_id: UUID, proposal_id: UUID) -> UUID:
    """Deterministic event id so a crash between domain commit and ``applied`` is retry-safe."""
    return uuid5(EVENT_NAMESPACE, f"{owner_id}:{proposal_id}")
