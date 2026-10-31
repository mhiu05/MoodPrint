"""Proactive check-ins (R1) require migration 0022 before accepting traffic.

The ORM writes ``ai_messages.part_index/part_count`` and ``ai_runs.origin`` on every insert
(0021) and account/guest purge deletes the five proactive tables (0022), so an older head
would fail at the first chat turn or deletion. The compatible rollback image is R0
(``release/proactive-r0-compat``): pre-feature code whose window accepts 0020, 0021 and
0022. Keep this tuple at the current head; never accept a head that predates the schema.
"""

READY_REVISIONS: tuple[str, ...] = (
    "0022_proactive_messages",
)
