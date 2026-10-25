# Hosted migration review package (J-03)

Audience: the operator who applies reviewed migrations to the hosted Supabase project.

**Status: ready for review — nothing here has been applied to the hosted database.**
Hosted is at `0010_account_deletion` (last read-only probe). Applying any file below needs the
operator's explicit approval of that exact SHA-256 at the time of the apply.

## Artifacts

All four are expand-only Alembic offline exports (no `DROP`, no `TRUNCATE`, no `%%`). Each repeats
the ACL/RLS block: `backend_access` policy for `moodprint_runtime`, no grants to `anon`,
`authenticated` or `service_role`.

| Order | File | From → to | New tables | SHA-256 |
|---|---|---|---|---|
| 1 | [0011-review.sql](0011-review.sql) | `0010_account_deletion` → `0011_social_stabilization` | `connection_reads` | `4d5e485f2305e21935255a7e3c07017cc43d9ceb81f288feb601f038baf9363f` |
| 2 | [0012-review.sql](0012-review.sql) | `0011_social_stabilization` → `0012_matching_v2` | `matching_stats_daily` | `608c82109251d38fb05e903b86a7cf751dcde5b0ba0797c4ea9fa023f7b17489` |
| 3 | [0013-review.sql](0013-review.sql) | `0012_matching_v2` → `0013_shared_activities` | `activity_sessions`, `activity_participants`, `activity_responses` | `6176dd5bd3160654bd8789c96e68924a45b99f7803e4c58c072cbec786e93464` |
| 4 | [0014-review.sql](0014-review.sql) | `0013_shared_activities` → `0014_moderation` | `staff_roles`, `moderation_actions` | `1e0048215a0a3097840bb155b4fbebac30ec4d2b38190fbd90b8b56e548e7837` |

## Evidence so far (local only)

| Check | Result |
|---|---|
| Each file byte-matches a fresh `alembic upgrade <from>:<to> --sql` (`apply_supabase_review.py --upgrade NNNN`, review-only mode) | PASS 2026-10-25 for 0011–0014 (`alembicExportMatches: true`, hashes above) |
| All upgrade exports 0009→0014 execute verbatim, in order, on a local database with Supabase-like roles; every new table has `backend_access`; `anon` has no access (`test_reviewed_upgrade_sql_executes_verbatim_with_supabase_roles`, part of VC-BE) | PASS (VC-BE 473 passed, 2026-10-25) |
| `alembic upgrade head` + `alembic check` on a fresh local DB (VC-MIG) | PASS ("No new upgrade operations detected.") |
| Rehearsal on a restored **hosted snapshot** (`hosted_snapshot_test`) | **BLOCKED** — needs an operator `pg_dump --schema=moodprint` of hosted (approval) |
| Hosted apply | **BLOCKED** — approval required per file |

## Apply procedure (operator, after approval)

The application must already run a release whose `READY_REVISIONS` accepts both the old and the
new head (each release keeps the previous head for one release), so readiness stays green during
the apply.

1. Fresh backup: [backup runbook](../runbooks/backup-restore.md) §2.
2. Restore that dump into local `hosted_snapshot_test`, then rehearse each step in order:
   `cd backend && uv run python ../scripts/apply_supabase_review.py --upgrade 0011 --rehearse-url postgresql+psycopg://…/hosted_snapshot_test`
   (repeat for 0012, 0013, 0014). Save each JSON output as `00NN-rehearsal.json` here.
3. **Stop and request approval**, quoting the four hashes above.
4. On approval only, per file in order:
   `uv run python ../scripts/apply_supabase_review.py --upgrade 00NN --apply --approved-sha256 <hash>`
   The tool writes `00NN-execution.json`. Then `scripts/inspect_database.py` and the Supabase
   advisors (read-only).
5. Never use `alembic upgrade` online, `alembic stamp`, or the Supabase MCP `apply_migration`
   against hosted.

Rollback: expand-only, so the previous image runs on the new schema; see
[11 §5](../11-migration-and-rollback.md#5-rollback-strategy). Feature flags
(`ACTIVITIES_ENABLED`, `MODERATION_ADMIN_ENABLED`, `MATCHING_SCORER`) disable new behaviour
without touching the schema.
