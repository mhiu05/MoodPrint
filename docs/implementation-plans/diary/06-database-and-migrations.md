# Database and migrations

Current implementation: **PASS for local migration/ACL/schema verification**. `0019_journal.py` exists and preserves Mood data. Hosted application migration remains NOT_STARTED by design; see [14](14-implementation-progress.md).

Status: NOT_STARTED. Add Alembic `0019_journal` after `0018_app_feedback`; leave all historical rows and prior reviewed artifacts intact.

## Schema

- `moodprint.journal_entries`: UUID PK; `user_id` FK/index, account `local_date`, timezone, mood small integer check 1..5, text<=10000, JSONB emotions/factors bounded by DTO and checks, status draft/saved, version>=1, created/updated timestamptz. Index `(user_id,local_date,created_at,id)` and owner/status/update. **No unique owner/date constraint.**
- `moodprint.journal_media`: UUID PK, entry FK cascade, owner FK, type, unique server object_path, MIME, positive bytes, optional nonnegative duration, pending/ready, created_at. Composite ownership check in service; indexes entry/owner/status/created.
- `moodprint.journal_storage_deletions`: UUID PK, unique object_path, created_at and attempt metadata. No account FK: cleanup must survive account erasure. Internal bounded worker only, never returned by user APIs.

Use `Base.metadata` schema/naming convention from `infrastructure/database/models.py`; import journal models wherever metadata initialization occurs. No data backfill: historical `Mood` has no trustworthy creation timestamp and its notes have a different AI promise.

## Security and concurrency

Enable RLS on new private-schema tables and revoke direct end-user roles, matching 0018. Grant DML only to the existing least-privilege runtime role with its explicit policy. BFF authorization maps opaque session to application `users.id`; Supabase `auth.uid()` is not interchangeable with that UUID. Storage is similarly backend-capability mediated, without browser general-purpose table access.

The existing user lock serializes owner writes; use expectedVersion and idempotency receipts. Multiple new entries/day are intentional, repeated requests with one key are not. Daily calendar marker is the latest saved entry on that date; display all entries/count and explain the marker, never average missing data or overwrite Mood summaries.

## Lifecycle, release and rollback

Journal export includes text and metadata, not binary attachments or signed URLs. Extend explicit journal scope, all_private/account, retention and guest purge. Queue object deletion transactionally before deleting media rows. Pending reservations expire after upload tokens have expired, so orphan cleanup cannot race a still-valid capability.

Test fresh Alembic upgrade/downgrade/upgrade on a separate disposable local database plus ORM/schema drift. Readiness must require 0019 when the app uses the tables. Production migration remains a reviewed release prerequisite, not an action in this task. Safe rollback serves the old application while retaining additive journal tables; destructive downgrade is for disposable tests only, never a production rollback plan.
