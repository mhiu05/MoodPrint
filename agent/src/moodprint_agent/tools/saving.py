"""Shared gate for every ``save_*`` tool: apply exactly what was stored and approved."""

from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID

from moodprint_agent.tools.context import CompanionToolContext
from moodprint_agent.tools.proposals import ApplyOutcome, ProposalKind


class _Writer(Protocol):
    async def apply(self, auth: Any, *, proposal_id: UUID, run_id: UUID) -> ApplyOutcome: ...


def error(code: str, message: str | None = None, *, retryable: bool = False) -> dict[str, Any]:
    body: dict[str, Any] = {"code": code, "retryable": retryable}
    if message:
        body["message"] = message
    return {"error": body}


def parse_uuid(value: object) -> UUID | None:
    try:
        return UUID(str(value)) if value else None
    except ValueError:
        return None


async def save_approved(
    context: CompanionToolContext,
    proposal_id: str,
    kind: ProposalKind,
    writer: _Writer | None,
) -> dict[str, Any]:
    """Re-check every binding the model could have changed, then let the domain adapter write."""
    store = context.deps.proposals
    if store is None or writer is None:
        return error("unavailable")
    pid = parse_uuid(proposal_id)
    if pid is None:
        return error("not_found")
    stored = await store.get(context.auth, pid)
    if stored is None or stored.kind != kind or stored.owner_id != context.auth.user_id:
        return error("not_found")
    # A proposal is made in one turn and approved in a later run of the same conversation.
    if stored.conversation_id != context.conversation_id:
        return error("not_found")
    if not stored.hash_matches():
        return error("payload_mismatch")
    if stored.status == "applied":
        return {"status": "applied", "result": stored.result}
    if stored.status in ("rejected", "failed"):
        return error(f"proposal_{stored.status}")
    if stored.status == "expired" or stored.expired(datetime.now(UTC)):
        return error("proposal_expired")
    if stored.status != "approved":
        return error("not_approved")
    if context.cancelled():
        # Linearisation point: a write that started before the cancel was acknowledged may
        # commit and stays; nothing new starts after it. Nothing is rolled back or promised.
        return error("run_cancelled")
    outcome = await writer.apply(context.auth, proposal_id=pid, run_id=context.run_id)
    if outcome.status == "applied":
        return {"status": "applied", "result": outcome.result}
    if outcome.status == "conflict":
        return {**error("version_conflict"), "latestVersion": outcome.latest_version}
    return error(outcome.error or outcome.status)


async def stored_preview(
    context: CompanionToolContext, arguments: dict[str, Any], kind: ProposalKind
) -> dict[str, Any]:
    """Approval dialog content: always the stored proposal, never the model's arguments."""
    pid = parse_uuid(arguments.get("proposal_id"))
    if pid is None or context.deps.proposals is None:
        return {}
    stored = await context.deps.proposals.get(context.auth, pid)
    if stored is None or stored.kind != kind or stored.conversation_id != context.conversation_id:
        return {}
    return {
        **stored.preview,
        "proposalId": str(stored.id),
        "expiresAt": stored.expires_at.isoformat(),
    }
