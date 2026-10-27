"""The guest-lifecycle schema requires migration 0016 before accepting traffic.

Earlier heads lack the immutable account-kind/deadline columns and cleanup tables. Accepting
them would advertise readiness while treating every user as registered and never expiring a
trial. Keep this tuple at the guest-aware head(s); never add a head that predates 0016.
"""

READY_REVISIONS: tuple[str, ...] = (
    "0016_guest_foundation",
)
