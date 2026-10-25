"""Schema heads this application accepts as ready (DR-16).

Keep the reviewed compatibility window explicit so both the deployed app and its
rollback remain ready throughout additive migrations 0011–0014. Unknown heads
remain unready.
"""

READY_REVISIONS: tuple[str, ...] = (
    "0010_account_deletion",
    "0011_social_stabilization",
    "0012_matching_v2",
    "0013_shared_activities",
    "0014_moderation",
)
