# P0 integration gate — 26 October 2026

**Phase A PASS.** See the [final verified integration report](FINAL.md) for current
main, migration, deployed digests, CI, hosted smoke, restored timer and deleted
branches. The continuation notes and first-pass evidence below retain the full
operational history; their intermediate pending statuses are superseded by FINAL.
The user explicitly authorized hosted 0015 and associated staging operations.
Migration **0015_context_privacy committed PASS at 14:35:12 UTC**, preserving
485 existing rows across 39 tables, Auth structure, turn-table ACL/RLS and runtime
column access. Legacy stamps remain NULL, nullable and without a default.

The F03 release `dc53e05b92af58408740a07b17c23fdf7b1cb59a` is now actually deployed:
both containers healthy, public liveness/readiness/homepage PASS. Hosted synthetic
privacy smoke PASS: fresh approved memory, revocation, saved transcript access,
durable policy stamps and complete synthetic resource cleanup. Four provider
requests settled; 4,913 input / 1,191 cached / 218 output tokens; estimated
USD 0.00049311 at the repository pricing snapshot.

[Integration PR #17](https://github.com/mhiu05/MoodPrint/pull/17) merged at
14:58:34 UTC as **`5e73a130fd0f081887c3c2ab2093c43674388012`** using the repository's
merge-commit convention after [integration CI passed](https://github.com/mhiu05/MoodPrint/actions/runs/40342985397).
Both its merge-result tree `ca0681c9a376a36478aefe64a6291c7dc9869412` and final
main tree equal the verified P0 source tree exactly. Final-main push
[CI is running](https://github.com/mhiu05/MoodPrint/actions/runs/40344737979);
the final P0 deployment and branch cleanup remain pending. The timer remains paused
until the final P0 release passes. Old 0014 deployment states were preserved as
`staging.before-0015.env` and `staging.previous.before-0015.env`; the automatic
rollback entry now points to the healthy F03-compatible pair.

Fresh protected backup: `moodprint-pre0015-20261026T143414Z.dump.dpapi`, encrypted
SHA256 `398e573d917a8dcd3f90c14d0e6d3471c434fce974f6b73d45007fd6bbd604d6`.
An isolated, network-disabled **schema-only recovery and 0015 upgrade PASS** restored
39 schema tables. No hosted private rows were restored. Full-data restore and
portable recovery/PITR remain unverified; archive listing is not counted as either.
The temporary recovery containers were removed. The first recovery attempts
identified pg_restore's filtered-schema namespace omission; explicitly creating
the namespace in the empty isolated database resolved it.

## Historical first-pass gate and evidence

The sections below preserve the earlier blocked inspection. Their statements
about unexecuted DDL and the old deployed SHA describe that first pass, superseded
by the authorized continuation above.

## Exact Git and release state

| Item | Observed state |
| --- | --- |
| Remote `main` | `dc53e05b92af58408740a07b17c23fdf7b1cb59a` |
| Remote P0 source `fix/ai-context-privacy-p0` | `66cc3c51ffd8579dfe23fe034f128396bcb0f711` |
| Evidence feature branch | `fb72c3c92b0bc4d533457dff36527104431ffd5b` |
| Remote `dev` | `779db2ac3c8013c799e38e8bd74184e83c48b826`, unchanged |
| [PR #15](https://github.com/mhiu05/MoodPrint/pull/15) | Merged into `main`; F03 source is present |
| [PR #16](https://github.com/mhiu05/MoodPrint/pull/16) | Merged into `fix/`; F01/F02/F04 remain outside `main` |
| Intended integration comparison | 37 files, 8,146 insertions / 23 deletions; no further schema change |
| Documentation branch | Ancestor of `main`; no separate merge needed |
| Integration PR / merge SHA | Not created / none: release gate remains unmet |
| Deleted branches / worktrees | None |

The active local feature tree equals the remote P0 source tree. All existing
worktrees and pre-existing untracked files were preserved. Browser tests wrote
57 tracked screenshots; their generated versions were preserved in the task's
artifact directory and the original tracked images restored. `.gitignore` was
not edited. Local `main` and `dev` were not moved.

## Executed verification

The [exact-source CI run](https://github.com/mhiu05/MoodPrint/actions/runs/40331918784)
completed successfully on `66cc3c5`. Its log is retained locally at
`.worktrees/p0-integration-verification/source-ci.log`.

| Command / check actually executed | Observed result |
| --- | --- |
| `git fetch --all --prune`; `gh pr view 15/16`; `gh run list/view`; Git comparisons | Exact refs, PR bases, successful source CI and release provenance verified |
| `.venv/Scripts/python.exe -m pytest -q --tb=short --junitxml=...` | **600 passed**, 927.59 s, exit 0; disposable local PostgreSQL |
| F03 cases within that run | **22 passed**: context privacy and migration regressions |
| Evidence/evaluation cases within that run | **39 passed**: 25 evidence, 12 runtime, 2 evaluation-preparation cases |
| Full CI Ruff command over app/tests/evals/Alembic/relevant scripts | PASS, exit 0 |
| `.venv/Scripts/python.exe -m mypy app` | PASS, 88 source files, exit 0 |
| `npm.cmd run typecheck`; `npm.cmd test`; `npm.cmd run build` | PASS; **54 unit tests**; production build completed |
| Existing frontend Playwright suite, temporary config and installed Chrome | **68 passed**, exit 0; includes narrow/desktop and accessibility assertions |
| Existing full-stack harness, separate local DB and fake SDK model | JSON evidence: **28 passed**, 0 skipped/unexpected/flaky, 438.80 s |
| `alembic upgrade 0014_moderation`; `alembic upgrade head`; `alembic check` | PASS on a newly created local DB; no ORM drift |
| Exact-source CI contracts, full-stack, packaging, workflows, synthetic load | All configured steps PASS; 600 backend / 54 unit / 68 browser / 28 full-stack tests |
| `python scripts/check_plans.py` | PASS: 12 plans, 39 tasks, 43 test IDs, 76 links |
| Linux container: `python -B -m unittest discover -s deploy/aws/tests -v` | **14 passed**, exit 0, read-only source mount and no network |
| DPAPI synthetic byte round trip | PASS |
| Hosted database inspector | Both configured URLs connect to the expected project over TLS; schema **0014**, column absent |

The local full-stack PowerShell wrapper exited 1 because it treated Node's
`NO_COLOR` warning on stderr as a terminating native-command error. The completed
Playwright JSON independently records all 28 assertions passing; the exact-source
Linux CI harness also completed successfully. This wrapper failure is not counted
as a clean local harness exit. The warning also interrupted normal teardown;
the two remaining test-server processes were identified by their exact command,
PID and creation time, stopped individually, and ports 8002/5174 rechecked free.

Other setup failures were corrected or explicitly separated: sandbox Git/network/
Docker access needed scoped escalation; an initial SSM JSON string acquired
PowerShell metadata; the temporary browser config needed its Vite working
directory; Windows lacks `fcntl`; the first Linux test container lacked `/tmp`
and the expected deployment directory layout. A stray placeholder module command
failed during harness preparation. No assertions were weakened. An SSM recovery
request initially exceeded AWS's 100-character comment limit and was resubmitted
with a shorter comment before any command ran.

## Hosted blocker and operational recovery

The [main verification](https://github.com/mhiu05/MoodPrint/actions/runs/40331805437)
and [publish run](https://github.com/mhiu05/MoodPrint/actions/runs/40333602551)
both succeeded. The [published manifest](https://github.com/mhiu05/MoodPrint/releases/tag/staging-dc53e05b92af58408740a07b17c23fdf7b1cb59a)
identifies `dc53e05`. **Publishing did not establish deployment success.**

Read-only SSM inspection `35a33928-8ca8-4742-ac3f-81ae631796b8` found:

- Both running image revisions: `779db2ac3c8013c799e38e8bd74184e83c48b826`.
- Hosted database: `0014_moderation`; `context_policy` absent; turn-table RLS enabled.
- Runtime role: neither superuser nor RLS bypass; AI processing enabled.
- The poller attempted the new image pair, failed health verification and restored
  the previous image pair at 13:53:31 and 13:58:54 UTC (20:53:31 and
  20:58:54 Asia/Bangkok).
- The timer was active, so another incompatible rollout could recur. `deploy.sh`
  does not run migrations; it replaces the active pair before checking health.

After the user's instruction to handle the missing requirements, the timer was
stopped using SSM `18824751-bc74-482b-b9e6-dbdb2fcb0b3f`. Preparation briefly enabled
the existing maintenance gate and stopped the old API worker, fencing mixed
workers before any planned schema change. **Automatic approval review then
rejected execution of hosted DDL**, stating that explicit approval to execute the
shared-environment migration was missing. The rejected command never started.
No indirect execution or retry of that rejected migration occurred.

The unchanged old API was restored and maintenance removed using SSM
`34f17a32-886e-4b43-942b-9fcdcf9cd27e`. Public readiness and homepage returned **HTTP
200**. Final read-only SSM `aab83bf4-a38f-449b-9f34-7744c31576a9` at 14:14:10 UTC
confirmed both exact old-image containers healthy and schema still 0014. The
release timer remains **inactive** intentionally. F03 is therefore
present in Git but **not deployed**; healthy old containers do not prove the
privacy fix is active.

AWS identity was renewed with user-approved `aws login --profile moodprint`.
Configured/used Region: `ap-southeast-2`; project plan **FREE / ACTIVE**, not
upgraded. No AWS resources were created or deleted.

## Migration review and prepared recovery

Target: Supabase project `roznanxbiyqybjpvtilq`, database `postgres`, private schema
`moodprint`, migration role `postgres`; runtime role is `moodprint_backend`.
The existing target validator checks project, endpoint, owner, database, port
and TLS. The operation is **0014 -> 0015 only**, not online remote Alembic, a blind
stamp, a backfill, or a schema reset.

The exact reviewed export is retained at
`.worktrees/p0-integration-verification/0015-current-export.sql`, SHA256
`b7ca2fffff9a408c6c2b9a8157eee58afeac7fe092b175028b6e0b0eb9ac7cf4`.
The historical SQL artifact differs only by one trailing blank line. The executor
was kept strict; the new artifact matches the current offline export exactly.

```sql
BEGIN;
ALTER TABLE moodprint.ai_turns ADD COLUMN context_policy VARCHAR(32);
UPDATE moodprint.alembic_version SET version_num='0015_context_privacy'
WHERE version_num='0014_moderation';
COMMIT;
```

The nullable column has no default and preserves legacy rows as untrusted NULL.
It changes neither ACLs nor RLS. ALTER TABLE needs a table lock; the prepared
executor sets a **5-second lock timeout / 15-second statement timeout**, verifies
the start revision and absence of the column, then checks revision, row counts,
Auth structure, nullable/no-default metadata, unchanged ACL/RLS and runtime column
access. PostgreSQL documents ALTER TABLE's lock behavior in its
[official reference](https://www.postgresql.org/docs/current/sql-altertable.html).

A fresh consistent application-schema archive was taken after worker shutdown:

| Recovery artifact | Observed result |
| --- | --- |
| Timestamp | `20261026T141122Z` (21:11:22 Asia/Bangkok) |
| Protected file | `C:/Users/minhh/moodprint-backups/moodprint-pre0015-20261026T141122Z.dump.dpapi` |
| Encryption | Windows CurrentUser DPAPI, existing protected backup directory |
| Encrypted SHA256 | `e1edbb9cd87505a93f0ba3b79d3657824f8fc84be14549dc9b03b22fc743bc03` |
| Verification | Exact decrypt round trip and `pg_restore --list` PASS; 39 tables; exported consistent snapshot |
| Private-data boundary | No Auth-schema row data copied; no hosted private rows restored into tests |
| Recovery gap | Fresh full-data restore NOT RUN; portable recovery/PITR remains unverified and DPAPI requires this Windows profile |

An earlier 0014 isolated restore is recorded in
[the existing recovery evidence](../release/evidence/2026-10-26/backup-verification.json).
It is historical evidence, not a fresh restore result. Provider backup availability
was not inferred from connectivity; see the
[Supabase backup documentation](https://supabase.com/docs/guides/platform/backups).
These remaining recovery limits must stay explicit in the hosted-change approval.

Do not downgrade/drop the privacy column or backfill trusted policy stamps.
After 0015, the old image rejects that revision, so ordinary image rollback to
779db2a is unsuitable. Quiesce old workers, deploy a verified F03-compatible image,
and retain schema 0015 for forward repair. If an application issue occurs, keep
the maintenance gate / AI kill switch active while preparing a compatible repair;
never restore an unfiltered AI runtime as the privacy rollback.

## Continuation gate

1. Obtain explicit approval to execute the exact hosted migration, including the
   documented recovery limitation. Recheck live revision, traffic fencing and a
   fresh backup if time or writes have advanced.
2. Execute the reviewed transaction once through the existing guarded SQL route.
   On ambiguous completion, inspect read-only; do not automatically replay DDL.
3. Start the verified main F03 release, prove actual image SHA, schema revision,
   health and synthetic smoke behavior, then restore the normal release timer.
4. Only then create the P0 integration PR from `fix/` into `main`; verify its
   exact comparison and required checks, merge using the repository's merge-commit
   convention, and verify the final main release.
5. Delete only the three requested branches after containment is proven and the
   current worktree has safely moved off the feature branch. Preserve unrelated
   worktrees, uncommitted files and `dev`.
6. Begin P1 only after Phase A passes. No P1 branch or Draft PR exists yet; no new
   real-model evaluation or model spending occurred in this integration task.

Local diagnostics, JSON reports, test XML, controlled-operation requests and
non-sensitive helper scripts are under
`E:/MoodPrint/.worktrees/p0-integration-verification/`. Backups and credentials are
outside Git. This report is intentionally uncommitted so it cannot trigger a
replacement staging release or alter the verified P0 source comparison.
