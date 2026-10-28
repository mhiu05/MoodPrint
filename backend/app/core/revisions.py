"""The guest-lifecycle and feedback schema require migration 0018 before accepting traffic.

Earlier heads lack the immutable account-kind/deadline columns, the cleanup tables, the guest-aware
provider-session helper and the unlinked feedback tables the retention and purge paths always touch
(even with every flag off). Accepting them would advertise readiness while treating every user as
registered, never expiring a trial or failing the first purge. Keep this tuple at the current head;
never add a head that predates 0018.
"""

READY_REVISIONS: tuple[str, ...] = (
    "0018_app_feedback",
)
