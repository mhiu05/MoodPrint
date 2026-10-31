"""Companion collaboration (R2) requires migration 0023 before accepting traffic.

The ORM maps ``ai_runs.parent_run_id`` on every run select/insert and account/guest purge
deletes ``ai_sharing_permissions``/``ai_collaborations`` (0023), so an older head would fail
at the first chat turn or deletion. 0023 is expand-only: the Phase 1 image (R1, head 0022)
keeps working on a 0023 schema once its window also accepts 0023 (integration requirement
recorded in evidence/execution-phase2.md). Keep this tuple at the current head; never accept a
head that predates the schema.
"""

READY_REVISIONS: tuple[str, ...] = (
    "0023_collaboration",
)
