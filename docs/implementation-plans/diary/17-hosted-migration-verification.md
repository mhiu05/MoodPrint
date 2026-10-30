# Hosted migration verification

Status: **APPLIED**. Migration `0019_journal` is on the hosted project. The sections below keep the earlier block and the gates that cleared it.

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

## Continuation — artifact, backup, and local rehearsal

The notes below record the state before the hosted apply. The apply itself is in the next section.

| Gate | Result |
| --- | --- |
| Compatibility release | Pull request [#24](https://github.com/mhiu05/MoodPrint/pull/24) merged as `faeffff`. It accepts `0018_app_feedback` and `0019_journal` and was confirmed live before DDL. |
| Reviewed SQL | `deploy/supabase/reviewed-sql/0019-review.sql`, SHA256 `6062c0c8d86a12aaab56e0db0d39ce23f2fffa6543092ce417ac15e4623f2535`. Offline export matches. No `DROP` or `TRUNCATE`. |
| Provider backups | Still `pitr_enabled = false`, `walg_enabled = true`, `backups` empty. That is not a provider restore point. |
| Logical backup | Custom-format dump of the hosted database, restored with `--schema=moodprint` into disposable local Postgres 17. Revision `0018_app_feedback`, 49 tables, 552 rows, and every per-table count matched the hosted database, including 6 `moods` and 6 `users`. Supabase-managed schemas were not restored locally. |
| Upgrade rehearsal | `apply_supabase_review.py --upgrade 0019 --rehearse-url` on a copy of that restore: all checks PASS, including preserved rows, RLS, runtime DML, denied API roles, and unchanged auth structure. The untouched restore copy remains `0018_app_feedback`. |

The dump files under `E:\MoodPrint-backups\` are outside the repository and contain the hosted rows, so they must not be committed.

## Hosted apply

Applied only after `https://moodprint.duckdns.org` served the compatibility release: `Last-Modified` moved from `Thu, 29 Oct 2026 03:36:31 GMT` to `Thu, 29 Oct 2026 14:11:00 GMT`, and readiness stayed 200. A second dump, taken immediately before DDL, restored with the same 49-table and 552-row match.

`scripts/apply_supabase_review.py --upgrade 0019 --apply` committed on `roznanxbiyqybjpvtilq`. Every check passed. A later read-only check saw `0019_journal`, the three journal tables with RLS enabled, and unchanged counts of 6 moods and 6 users. Live readiness stayed 200. Report: [0019-execution.json](../../../deploy/supabase/reports/0019-execution.json). Roll back by serving the compatibility image. Do not drop the new tables.
