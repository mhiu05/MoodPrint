"""Guest lifecycle and feedback retention require migration 0018 before accepting traffic.

Earlier heads lack the immutable account-kind/deadline columns, the cleanup tables, the guest-aware
provider-session helper and the unlinked feedback tables those paths always touch (even with every
flag off). Accepting them would advertise readiness while treating every user as registered, never
expiring a trial, or failing the first purge.

0019_journal is accepted only as a compatibility window. This application does not read or write
journal tables, and the hosted upgrade that creates them is additive, so this image can keep
serving after that upgrade and is the rollback target. The journal application must not copy this
window: its retention and purge paths require the journal tables and accept only 0019_journal.
"""

READY_REVISIONS: tuple[str, ...] = (
    "0018_app_feedback",
    "0019_journal",
)
