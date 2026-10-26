"""The privacy projection requires migration 0015 before accepting traffic.

Earlier schema heads lack the content-free turn policy column. Accepting them
would advertise readiness even though chat cannot enforce its context boundary.
"""

READY_REVISIONS: tuple[str, ...] = (
    "0015_context_privacy",
)
