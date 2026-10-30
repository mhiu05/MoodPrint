"""Private journal lifecycle requires migration 0019 before accepting traffic.

Retention and account/guest purge always touch journal metadata and its durable Storage deletion
queue, even when no journal entry exists. Earlier heads cannot run those lifecycle paths safely.
Keep this tuple at the current head; never accept a head that predates the journal tables.
"""

READY_REVISIONS: tuple[str, ...] = (
    "0019_journal",
)
