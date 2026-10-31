# Migration 0020 preflight and rehearsal — 2026-10-31

**HOSTED_MIGRATION_DEFERRED — COMPATIBLE_RELEASE_REQUIRED**

The owner approved the intentional private-profile retirement. Hosted execution
was not attempted: the currently serving backend requires revision 0019 and still
maps the table/columns that 0020 removes. Production remained operational.

## Verified target and live compatibility

Read-only observations were made on 2026-10-31, approximately 13:32–13:40
Asia/Bangkok. No private text, journal content, tokens or passwords were selected
for the hosted audit.

| Identity | Observed value |
| --- | --- |
| Supabase project | `roznanxbiyqybjpvtilq`, name `database`, region `ap-northeast-1`, `ACTIVE_HEALTHY` |
| Project database endpoint | `db.roznanxbiyqybjpvtilq.supabase.co` |
| Actual backend endpoint | `aws-0-ap-northeast-1.pooler.supabase.com:5432/postgres` |
| Actual backend login | `moodprint_backend.roznanxbiyqybjpvtilq` |
| Actual backend Supabase URL | `https://roznanxbiyqybjpvtilq.supabase.co` |
| Database revision table | `moodprint.alembic_version` |
| Hosted revision before / after audit | `0019_journal` / `0019_journal` (no migration executed) |
| PostgreSQL / vector | `17.11` / `0.8.2` |
| AWS instance | `i-0664d6ea5930452db`, `ap-southeast-2`, running |
| Serving image source revision | `5d2b384516b9318e6ee132c1a8b08dcbc374b79b` |
| Serving API image digest | `sha256:213d7b4ba57cafbca4395928911e6c69db71997142404a88a57da5762f61b431` |
| Serving web image digest | `sha256:e64e7081884d1fef4c8c5fd2ea960ea4b97ae6f226b147e1dbab2db4eac4c29e` |
| Container state | API and web running, healthy, restart count 0 |
| Public HTTPS health | `/api/v1/health/live` 200 `{"status":"ok"}`; `/api/v1/health/ready` 200 `{"status":"ready"}` |

The project reference is corroborated by MCP project inventory, local environment
host/login/URL, and the running backend's filtered environment. The live image's
`app/core/revisions.py` accepts only `0019_journal`; its ORM still contains
`PrivateItem` and legacy `source_id` columns. OCI image labels identify the source
revision. These are current observations, not an inference from a historical tag.
Read-only SSM commands inspected Docker metadata/source and called health probes;
they did not restart containers or change configuration.

Supabase's separate migration-history listing is empty. This application uses
Alembic, whose actual revision table is present. The source migration chain has
one head, `0020_private_profile_retirement`, directly after `0019_journal`.

## Impact and database controls

| Object / effect | Fresh hosted count |
| --- | ---: |
| Retired `private_items` rows | 11 |
| Users whose `data_version` would increment | 3 |
| Proposals with purpose `private_item` to delete | 0 |
| Pending source-backed memory proposals to expire/clear | 0 |
| Proposals with source metadata to detach | 0 |
| Approved memories with source metadata to detach | 0 |
| Users to preserve | 6 |
| Application auth-session rows to preserve | 88 |
| Consent rows to preserve | 24 |
| Journal-entry rows to preserve | 0 |
| Published-profile rows to preserve | 17 |

The 17 published-profile rows are historical snapshots for 2 owners; **0** are
currently `valid`. This is not a claim of 17 active public profiles or members.

Catalog inspection confirmed the expected table, proposal `purpose`, and five
source columns. The only foreign keys into `private_items` are
`fk_memories_source_id_private_items` and
`fk_memory_proposals_source_id_private_items`, matching the real migration.
Required existing extensions include `vector 0.8.2`, `pgcrypto 1.3` and
`uuid-ossp 1.1`. At 13:38:19 Asia/Bangkok the database was not in recovery,
reported 15,799,987 bytes and 13 connections. No other active statement involving
the retired names was present in that single snapshot. This does **not** prove
that serving workers are compatible or that future requests cannot use them.

All nine audited tables (`users`, `auth_sessions`, `consents`, `private_items`,
`memories`, `memory_proposals`, `journal_entries`, `matching_drafts`,
`published_profiles`) have RLS enabled, owner `postgres`, and the existing
`backend_access` ALL policy for `moodprint_runtime`. Effective privilege checks:

- `anon`, `authenticated` and `service_role`: no `moodprint` schema USAGE and no
  SELECT/INSERT/UPDATE/DELETE on those tables.
- `moodprint_runtime` and the actual `moodprint_backend` login: schema USAGE and
  table DML, with neither superuser nor BYPASSRLS. Backend login connection limit 20.
- MCP inspection ran as `postgres`; ownership of the affected tables was verified.
  No destructive operator permission was exercised.

Runtime RLS intentionally trusts the server role. Actor/session, age, consent,
ownership and pair checks in FastAPI remain mandatory; table RLS alone is not
per-user authorization proof.

Sanitized raw evidence is retained outside Git at
`.tmp/18plus-release/hosted-preflight-final.json`, SHA-256
`abf35ac37df4b68314d3af3c3f1fb87f44fda5dca47c9d690f8ed291dae6d12a`.
It contains aggregate/catalog results and filtered runtime information only.

## Real migration and synthetic backup/restore proof

The real [0020 migration](../../backend/alembic/versions/0020_private_profile_retirement.py)
was not edited. It increments affected data versions, expires pending source-backed
memory proposals, deletes obsolete private-item proposals, detaches retained
approved memories, removes the five obsolete source/purpose columns and their
constraints/indexes, and drops `private_items`. Its destructive downgrade remains
prohibited. It does not delete users, journals or published friendship profiles.

An independent, uniquely labelled local container was provisioned with
`scripts/disposable_postgres.py --port 55627`, run ID
`23cd48b7555a4ac0a41822632b356dac`, PostgreSQL 17.10 and vector 0.8.2.
It used tmpfs storage and a loopback-only port. Unique sibling databases were
created and removed through the ownership-verifying test helper; no shared
application/test database was reset.

Fresh [migration regression](../../backend/tests/test_discovery_migration.py):
**1 passed, 0 failed, 0 skipped**, 14.25 seconds. Evidence:
`.tmp/18plus-release/migration-rehearsal.log` and `migration-rehearsal.xml`.
The test applies the full real chain to 0019, seeds legacy data, upgrades to
0020, repeats the no-op `upgrade head`, verifies intended retirement and
preservation, compares policies, checks browser-role denial, and confirms
downgrade refusal.

A separate synthetic backup/restore run additionally:

1. Seeded one user, session, journal, draft, public snapshot, approved memory,
   private item, three proposals and four consents at real revision 0019.
2. Created a full custom-format PostgreSQL archive with `pg_dump`, stored only in
   ignored local scratch, and verified its TOC using `pg_restore --list`.
3. Restored into another newly owned isolated database with
   `pg_restore --exit-on-error --single-transaction --no-owner`.
4. Compared exact canonical row hashes/counts for all nine representative tables,
   normalized table ACLs, RLS flags, policies and revision before migration.
5. Applied the actual 0020 Alembic migration to the restored DB; verified target
   revision, private-table retirement, expected proposal reduction and preservation
   of auth, consent, journal, draft, published profile and approved memory counts.
6. Completed the original full migration regression, including downgrade refusal.

Archive: **188,714 bytes**, SHA-256
`82f44de810df52b3e69f057eef2fdccae3f2c5281cdf70d1582b2cf3dd61e2e2`.
TOC validation, restore and restored migration all exited **0**. Results are in
`.tmp/18plus-release/synthetic-restore-result.json`; the archive and TOC are
`synthetic-0019.dump` and `synthetic-0019.toc`. The local runner is
`synthetic_restore_rehearsal.py` (SHA-256
`dc88fefdb4ff6fbd80c5077d04e35858006c89ed164e9be4b870c7098b397e7b`).
This synthetic baseline includes the regression's matching RLS bootstrap and
the migration-installed controls; it is **not** a full clone of hosted Auth,
runtime grants/policies or Storage objects.

An initial schema-filtered dump failed restoration because pgvector extension
creation was excluded. The corrected successful procedure dumps the **whole
isolated synthetic database**, including extensions. ACL comparison normalizes
implicit default ACLs before comparison. The failed attempts were disposable;
no assertion, migration constraint or production guard was weakened.

Cleanup exited **0** using the guarded helper with the exact run ID: only this
labelled container and its local credential file were removed. Synthetic archives,
hash/TOC results and sanitized logs remain outside Git; other Docker resources
were left intact.

**Hosted backup and hosted restore: NOT_PERFORMED.** The incompatible-backend
gate already prohibits migration. Avoiding an unnecessary production-data copy
is deliberate. Synthetic restoration does not satisfy the future hosted-backup
gate. Before a later destructive execution, create a fresh encrypted/off-site
backup, verify its integrity and restore it into an isolated environment with
representative Auth/journal/matching/consent checks. Include separate Storage
object protection; database backups contain Storage metadata rather than blobs.
Do not assume a recoverable automatic backup on a Free project. See
[Supabase backup documentation](https://supabase.com/docs/guides/platform/backups).

## Offline review package and future execution boundary

[prepare_0020_review.py](../../scripts/prepare_0020_review.py) exports exactly
`0019_journal:0020_private_profile_retirement` using `alembic upgrade --sql`.
It clears hosted/provider configuration, writes only new files under constrained
scratch/pending directories, refuses overwrite, and provides no hosted executor.
The tracked [pending SQL](../../deploy/supabase/pending-review/0020/0020-review.sql)
and [gate metadata](../../deploy/supabase/pending-review/0020/0020-review.json)
record the approved semantics while keeping `hostedExecutionAllowed: false`.
The metadata's `NOT_VERIFIED` values describe generator defaults; this document
records the actual current audit and decisive compatibility failure.

SQL SHA-256: `2aad54136bba6256557144e8d4137476b884f70a9a4bf58dd79daf40d5648474`
(2,030 bytes, LF). A scoped `.gitattributes` rule protects those exact bytes.
The existing approved-artifact manifest and SQL approvals were left unchanged.

Fresh review-package tests: **7 passed, 0 failed, 0 skipped** in 9.82 seconds
(`.tmp/18plus-release/migration-review-package.xml`). They exercise the real
offline export, exact tracked artifact/hash, protected-output refusal, overwrite
refusal, wrong-range refusal and hosted/provider configuration isolation. Tests
were observed failing before implementation/artifact generation. Scoped Ruff,
documentation validation and the 11 existing pinned-approval checks pass.

Reproduce into a **new** path:

```powershell
backend/.venv/Scripts/python.exe scripts/prepare_0020_review.py --output .tmp/0020-review-new.sql
```

The local online Alembic runner continues to reject remote targets. The existing
`apply_supabase_review.py` continues to reject destructive SQL and has plans only
through 0019. Neither guard was relaxed. A later release operator must add/review
a dedicated 0020 execution path after all operational evidence exists: compare
the artifact byte-for-byte to the current real Alembic export and expected hash,
verify TLS/project/database/owner and exact starting revision, serialize migration
ownership, require bounded old-traffic drain and a ready compatible image, apply
the complete export in its real transaction with bounded statement/lock timeouts,
then verify data counts, retired columns, ORM, RLS/effective ACLs and readiness.
The revision UPDATE is part of Alembic's actual migration export; stamping a
revision or executing only that statement is forbidden.

Do not feed this destructive artifact into an expand-only executor or introduce
a broad `allow remote` / `allow destructive` bypass. Backup evidence, compatibility,
sequencing and verified target are independent gates, not a single approval flag.

## Hosted gate and recovery

| Gate | Result |
| --- | --- |
| Correct target | PASS, corroborated against serving runtime |
| Disposable real migration rehearsal | PASS |
| Synthetic archive integrity and restoration | PASS; not a hosted backup |
| Fresh hosted backup/restoration | NOT_PERFORMED; required before future apply |
| Compatible serving backend | **FAIL**; serving image accepts only 0019 |
| No incompatible traffic / safe sequence | **FAIL** while current backend serves |
| Migration owner | Identity/ownership inspected; no hosted DDL exercised |
| Dedicated destructive hosted executor | NOT_IMPLEMENTED; existing guards preserved |
| Hosted execution | **DEFERRED**, no DDL/DML submitted |

Pre-stage and verify the compatible release before a later bounded maintenance
window. Complete fresh backup/restore proof, drain old requests/streams/workers,
run the reviewed migration, start the compatible backend, verify schema, data,
ACLs and health, then serve the matching frontend and resume traffic. Keep the
current application running until that release operation is authorized and ready.
Do not hold production indefinitely awaiting the user's PR.

Recovery after committed 0020 is a reviewed forward fix or a rehearsed full
restore with compatible application sequencing. An old 0019 backend cannot be
rolled back onto 0020. Restores must reconcile consent/session revocations,
deletion requests and external Storage changes before traffic resumes; never
recreate retired content or stamp history to simulate recovery.
