"""Schema heads this application accepts as ready (DR-16).

The only place heads are listed. Each expand-only migration appends its head and
keeps the previous one for one release, so the previous image stays ready on the
newer schema and an app rollback needs no code change.
"""

READY_REVISIONS: tuple[str, ...] = ("0013_shared_activities", "0014_moderation")
