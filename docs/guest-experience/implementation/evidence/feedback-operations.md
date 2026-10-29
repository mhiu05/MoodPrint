# Feedback operations (GE-10.3)

Local implementation only. D03 has **not** approved the proposed 180-day policy; collection and
administration remain disabled. This runbook is not permission to execute SQL on a hosted target.

`app_feedback` is independent of activity ratings and safety reports. It has no submitter UUID,
session/provider key, address, private-activity ID, URL or identity hash. Temporary submission
receipts support replay and limits: guest purge explicitly deletes them; registered account
deletion deletes them even though the registered tombstone remains; registered receipts expire
at 30 days. Rows and their review events expire at 180 days, including the exact cutoff, using
database time. Each normal retention tick processes at most 500 feedback rows and 500 receipts,
including when both feedback flags are off. Monitor backlog age rather than promising immediate
physical deletion of every historical copy.

The success receipt exposes the independent `feedbackId`. A person may keep it to identify an
accidentally submitted sensitive comment. There is no public lookup, account-based retrieval,
or claim that free text and timestamps are irreversibly anonymous. Do not copy the comment into
logs, tickets, audit notes, or this runbook.

For a requested redaction, prepare parameterized SQL for the exact approved environment and
feedback UUID, with an authorized operator and a current registered admin. Have a second reviewer
check the target, least-privilege connection, expected version and backup implications. The
protected transaction must:

1. Lock the active eligible registered operator, verify a live admin role under lock and recent
   password reauthentication within 12 hours, then lock the specified feedback row (canonical
   owner → staff-role → resource order). No submitter lookup or private-history join.
2. Check the expected feedback version; if missing or stale, stop and re-review. Set only
   `comment = NULL`, increment `version`, and set `reviewed_at = clock_timestamp()`.
3. Insert one `feedback_review_events` row with the feedback UUID, operator UUID,
   `action = 'redact'`, resulting version and database timestamp. Do not retain a copy of the
   original comment. Commit both changes atomically; record the approved content-free action.
4. Verify the one intended row/version and audit event without printing the prior content.

Prefer the protected application administration path for normal status changes. A redaction is
an explicitly reviewed operator action, not a new public endpoint or a broad database cleanup.
Never delete a person's account to try to retrieve or remove independent feedback.

Restore only into a quarantined disposable/staging target authorized for that operation. Preserve
immutable guest deadlines, deny expired identities immediately, finish guest/orphan cleanup and
feedback/receipt retention before enabling external access. Reapply reviewed post-snapshot
redactions using the protected content-free operational record and verify the resulting versions.
If that record or target authorization is unavailable, keep the restore quarantined. Backups and
provider/operational logs have separately approved policies; active-row tests do not prove their
physical erasure. No hosted deletion, redaction or restore was performed by this task.
