# Restore drill (I-07, local)

Date: 2026-10-25 · Operator: implementation agent · Runbook: [backup-restore.md](../runbooks/backup-restore.md) §3

| Item | Value |
|---|---|
| Source | local `prod_load_test`, populated by the 50-user load run (J-02): 50 users, 25 rooms, 500 messages, 25 icebreaker sessions |
| Dump | `pg_dump --schema=moodprint --format=custom --no-owner --no-privileges` inside the local `postgres:17` container: 347,917 bytes, 1 s |
| Target | fresh local `restore_test` with the out-of-schema prerequisites Supabase provides (pgvector in `extensions`, `auth.sessions`) |
| Restore | `pg_restore --no-owner --no-privileges --exit-on-error`: exit 0, 2 s |
| Row counts | **38 tables, 3,191 rows in source = 3,191 restored, every table equal** (`counts=MATCH`) |
| Revision | not applicable: this synthetic database is built from metadata, not Alembic, so it has no `alembic_version` |
| Cleanup | `restore_test` dropped; dump file removed from the container |

Result: **PASS** for the local drill.

Not covered (still release gate G10): a drill from a real hosted dump (needs operator approval and a dump), encryption/off-host storage of the dump (age key and storage location are owner decisions, Q-04), and the post-restore re-application of deletions/revocations described in the runbook §4.
