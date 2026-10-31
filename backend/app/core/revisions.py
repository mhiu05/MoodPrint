"""Private journal lifecycle requires migration 0020 before accepting traffic.

Retention and account/guest purge touch journal metadata, its Storage deletion queue, and AI memory
tables whose source links changed when private profile notes were retired. Keep this tuple at the
current head; never accept a head that predates those schema changes.
"""

READY_REVISIONS: tuple[str, ...] = (
    "0020_private_profile_retirement",
)
