# Hosted migration verification

Status: **BLOCKED**. Migration `0019_journal` was not applied.

## Identity

Read-only Supabase Management API calls, using the configured project token, returned:

| Check | Result |
| --- | --- |
| Project ID | `roznanxbiyqybjpvtilq` |
| Name | `database` |
| Region | `ap-northeast-1` |
| Status | `ACTIVE_HEALTHY` |
| Database host | `db.roznanxbiyqybjpvtilq.supabase.co` |
| Postgres | `17.11` |
| Query role | `postgres` (Management API, not the application runtime role) |
| Local `backend/.env` | Same project ref is present. The connection string is not recorded here. |

This matches the project named in [14](14-implementation-progress.md) and [journal storage](../../supabase/journal-storage.md).

## Schema

| Check | Result |
| --- | --- |
| `moodprint.alembic_version` | `0018_app_feedback` |
| `journal_entries` | absent |
| `journal_media` | absent |
| `journal_storage_deletions` | absent |
| `moodprint.moods` | still present; row count was read only as a count, contents were not inspected |
| Roles present | `anon`, `authenticated`, `moodprint_runtime`, `service_role` |
| `storage.buckets` `journal-media` | `public = false`, file size limit `52428800` |
| `storage.buckets` and `storage.objects` RLS | enabled, zero policies (default deny) |

## Why it was not applied

`origin/main` at `9ca7fc8` sets `READY_REVISIONS` to only `0018_app_feedback`. `backend/app/main.py` returns not-ready when `version_num` is outside that tuple. The feature branch accepts only `0019_journal`.

Moving the hosted database to `0019_journal` would make the currently deployed application fail `/api/v1/health/ready` and any lifecycle path that requires readiness. This branch was not deployed. No compatibility image that accepts both revisions was authorized.

The Management backup listing returned `pitr_enabled = false`, `walg_enabled = true`, and an empty `backups` array. That is not evidence of a rehearsed, restorable backup, so the backup gate also fails.

## Rollback

Do not drop tables that were not created. When a later authorized release is deployed, apply the reviewed `0018_app_feedback` → `0019_journal` SQL through `scripts/apply_supabase_review.py` after a new reviewed artifact is approved. Do not edit the previously pinned SQL files. Roll back by serving an application that still accepts `0018_app_feedback` while leaving additive journal tables in place. Do not use `alembic downgrade` on the hosted database.
