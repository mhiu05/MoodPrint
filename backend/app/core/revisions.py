"""Intermediate C: the 0028 ORM accepts both schema 0028 and additive 0029.

Feature F restores the journal-intelligence ORM and must accept only 0029.

The ORM maps ``ai_messages.citations/source_backed`` (0025), ``ai_search_usage`` (0026),
``ai_maps_searches`` (0027) and receipt ``permission_policy`` (0028). All four are additive;
0025-0027 are forward-only and 0028 only drops its column without non-legacy receipts.

V3 note kept for history: three agents, orchestration receipts and groups required 0024.

The ORM maps ``ai_conversations.kind``/``active_agent*`` and ``ai_messages.mentions`` on every
chat select/insert, so an older head fails at the first conversation read. 0024 is expand-only
(see docs/implementation-plans/three-agent-orchestration-group-chat/11).

Phase 2 note kept for history: companion collaboration (R2) required migration 0023.

The ORM maps ``ai_runs.parent_run_id`` on every run select/insert and account/guest purge
deletes ``ai_sharing_permissions``/``ai_collaborations`` (0023), so an older head would fail
at the first chat turn or deletion. 0023 is expand-only: the Phase 1 image (R1, head 0022)
keeps working on a 0023 schema once its window also accepts 0023 (integration requirement
recorded in evidence/execution-phase2.md). Keep this tuple at the current head; never accept a
head that predates the schema.
"""

# Intermediate C: the unchanged 0028 ORM remains compatible with additive 0029.
# Restore feature F only after 0029; F must narrow this window to 0029 again.
READY_REVISIONS: tuple[str, ...] = (
    "0028_collaboration_defaults",
    "0029_journal_intelligence",
)
