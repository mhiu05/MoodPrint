"""The guest-lifecycle schema and helper require migration 0017 before accepting traffic.

Earlier heads lack the immutable account-kind/deadline columns, cleanup tables and the
guest-aware provider-session helper. Accepting them would advertise readiness while treating
every user as registered and never expiring a trial. Keep this tuple at the guest-aware head(s);
never add a head that predates 0017.
"""

READY_REVISIONS: tuple[str, ...] = (
    "0017_guest_security",
)
