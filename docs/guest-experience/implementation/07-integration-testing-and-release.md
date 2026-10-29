# Integration Testing and Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (when authorized/available) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove combined guest, registered, feedback and onboarding behavior and prepare a concrete release package without deploying.

**Architecture:** Real disposable PostgreSQL and actual HTTP/UI with synthetic Auth/SDK/STT/embed. External compatibility and owner policy remain explicit holds; rollback always preserves guest denial/cleanup.

**Tech Stack:** Existing pytest/Vitest/Playwright/fullstack/load scripts; Alembic/reviewed SQL; Linux CI/container packaging.

**Spec:** [Original testing plan](../06-testing-and-release-plan.md), [decision register](../07-risks-and-open-decisions.md), all [implementation plans](00-implementation-index.md#plan-map-and-task-ownership).

## Global Constraints

No production mutation, paid tests, hosted identity deletion, merge/deploy/settings changes without separate approval. PASS only actual evidence; skips/blockers reported. Preserve failing assertions/timeouts/load parameters. Exactly 7200s authorization; fake clock never a production API. One backend worker. Flags never disable expiry/cleanup.

## Review Focus

1. Synthetic server shortcuts could bypass real guest intent/claim/CSRF → full HTTP journey required (GE-14.1).
2. Test fixtures reset the same DB concurrently → separate DBs/serial suite runs (GE-14.1).
   3.50 visitors with capped guest calls do not prove 50 simultaneous paid calls/capacity (GE-14.2).
3. Restored/rolled-back data or code resurrects access → guest-aware compatibility only (GE-14.2/14.3).
4. Offline SQL generation might overwrite approved artifacts or forge approvals → pending local review package only (GE-14.3).

## Safe local setup and baseline commands

These are **future implementation commands**, not this planning session's application test results. Check Docker/tool availability and occupied ports/container names first; never kill another process/container. Use a new owned loopback container and public synthetic password, not .env data:

```powershell
# Repository root, only if the exact name/port is free.
docker run --detach --rm --name moodprint-guest-impl-db --publish 127.0.0.1:26432:5432 --env POSTGRES_DB=moodprint_guest_unit_test --env POSTGRES_USER=postgres --env POSTGRES_PASSWORD=moodprint-local-only pgvector/pgvector:0.8.2-pg17
foreach ($taskDb in @('moodprint_guest_migration_test','moodprint_guest_review_test','moodprint_guest_fullstack_test','moodprint_guest_load_test')) {
  docker exec moodprint-guest-impl-db createdb -U postgres $taskDb
}
# Backend:
$env:TEST_DATABASE_URL='postgresql+psycopg://postgres:moodprint-local-only@127.0.0.1:26432/moodprint_guest_unit_test'
uv sync --locked --python 3.12.13
uv run --locked ruff check app tests evals alembic
uv run --locked mypy app
uv run --locked pytest -q
uv run --locked python ../scripts/export_openapi.py
# Migration DB, distinct from resetting unit/fullstack fixtures:
$env:DATABASE_URL=''
$env:DATABASE_MIGRATION_URL='postgresql+psycopg://postgres:moodprint-local-only@127.0.0.1:26432/moodprint_guest_migration_test'
uv run --locked alembic upgrade head
uv run --locked alembic current
uv run --locked alembic check
# Frontend:
npm.cmd ci
npm.cmd audit --audit-level=low
npm.cmd run contracts:generate
npm.cmd run typecheck
npm.cmd test
npm.cmd run build
npm.cmd exec -- playwright test --config playwright.owned.config.ts --reporter=list --output "$env:TEMP/moodprint-guest-fixtures"
# Backend, own fullstack DB/ports8002+5174:
$env:TEST_DATABASE_URL='postgresql+psycopg://postgres:moodprint-local-only@127.0.0.1:26432/moodprint_guest_fullstack_test'
uv run --locked python ../scripts/test_fullstack.py --reporter=list --output "$env:TEMP/moodprint-guest-fullstack"
# Root:
python scripts/check_docs.py
python scripts/check_reviewed_artifacts.py
git diff --check
```

Run each section in its labelled directory, not as one unmodified script. Application fixture setup must blank external keys as current conftest does and reject non-loopback/non-*_test target using tests.database_target; fullstack LocalAuth must do likewise. Do not copy current .env into worktree/test env. `npm ci` executes locked tooling only after reviewing repository install scripts. Browser binary install/explicit installed Chrome is local tooling, never copy a personal browser profile.

Current Playwright configs/reporters/specs can write hardcoded evidence/screenshot paths even with --output. GE-14.1 must add an explicit `MOODPRINT_TEST_ARTIFACT_DIR` path override to reporter/screenshot helpers and affected specs, defaulting to existing convention, tests ensuring no write escapes configured artifact root. Until then inventory generated-only paths and move only verified owned artifacts to temp; never .gitignore/reset/clean. Do not hide failures by deleting evidence.

CI-required checks also include: script lint list from .github/workflows/verify.yml; contract `git diff --exit-code -- backend/openapi.json frontend/src/api/generated/schema.d.ts` **after generated changes committed**; Node 22 Linux; deployment `uv run --project backend --locked python -m unittest discover -s deploy/aws/tests -v` on Linux (Windows fcntl partial); workflow actionlint, Dockerfiles/Compose/Caddy validation, `bash scripts/test_staging_proxy.sh`. Follow exact existing verify.yml commands/versions rather than invent an AWS deployment. Test container packaging contains no .env/source maps and retains correct user. No new AWS resource is needed.

Historical only:642 backend,73 units,44 selected browser fixtures,28 synthetic fullstack;528.02kB main bundle warning; overlapping 50-user load failed SSE completion, same isolated run passed. Fresh branch output replaces none of that history. Baseline failures must be attributed, not reclassified as introduced or ignored.

## Clock/concurrency test design

Pure lifetime tests use explicit T−1ms/T/T+1ms. Request/service tests replace a clock dependency **inside test fixtures**, never an HTTP duration/clock override. SQL helper tests use real rows and test-only function clock injection in a disposable schema or a short boundary around actual clock_timestamp; production helper is checked for clock_timestamp/VOLATILE and immutable 7200s constraints. Freezing Python datetime does not freeze PostgreSQL. Include one short real-time SQL boundary case using a guest seeded with start=T−7200s and T near current DB time, then wait via a controlled barrier; no 2h sleeps.

Use asyncio Events and independent SQL connections/browser contexts to hold work before finalization; advance controlled clock or release near actual T and assert ordered authorization/dispatch events. Test pre-T final decision with later physical commit separately; no assertion of exact TCP/disk erasure. Restart owned processes with same DB; do not replay paid work.

## Mandatory negative scenarios and exact oracles

Commands in rows 1–18/22–25 run from backend except row 3. E2E commands run frontend. Every named test is **planned**, added in its owner task orGE-14.1. A nonzero security assertion is FAIL; skipped DB tests are PARTIAL.

| # / owner      | Command                                                                                                                 | Required oracle                                                                                         |
| -------------- | ----------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| 1 GE-03.1      | `uv run --locked pytest -q tests/test_guest_expiration.py::test_deadline_boundary`                                      | T−1ms allowed;T/T+1ms denied; real SQL helper case also exercised                                       |
| 2 GE-03.1      | `uv run --locked pytest -q tests/test_guest_expiration.py::test_refresh_never_extends_guest`                            | Repeated GET/credential rotation leaves original start/T unchanged                                      |
| 3 GE-09.2      | `npm.cmd exec -- playwright test --config playwright.owned.config.ts guest-expiry.spec.ts --grep "multiple tabs"`       | Both tabs shareT, clear private state, no auto signup                                                   |
| 4 GE-03.2      | `uv run --locked pytest -q tests/test_guest_permissions.py::test_guest_cannot_read_other_guest`                         | Other guest personal UUID reads/mutations 404, no existence/body leak                                   |
| 5 GE-03.2      | `uv run --locked pytest -q tests/test_guest_permissions.py::test_guest_cannot_read_registered_data`                     | Registered private canaries remain unreadable/unmodified                                                |
| 6 GE-03.2      | `uv run --locked pytest -q tests/test_guest_permissions.py::test_guest_direct_social_routes_denied`                     | Every exact social tuple denied 403 regardless forged consent; expired 401 first                        |
| 7 GE-03.2      | `uv run --locked pytest -q tests/test_guest_permissions.py::test_registered_cannot_select_guest_peer`                   | Forged profile/ref/room/activity cannot make guest a peer                                               |
| 8 GE-04.2      | `uv run --locked pytest -q tests/test_guest_provisioning.py::test_provider_success_database_failure`                    | No app grant; one targeted orphan pending/reconciled; permanent canary intact                           |
| 9 GE-04.2/06.2 | `uv run --locked pytest -q tests/test_guest_provisioning.py::test_ambiguous_signup_never_retries_upstream`              | Exactly 1 external signup across retries; unresolved stays ungranted                                    |
| 10 GE-04.2     | `uv run --locked pytest -q tests/test_guest_provisioning.py::test_lost_grant_response_recovers_same_user_and_deadline`  | Same lifecycle/T; rotated credentials; old credentials revoked; no plaintext-token storage              |
| 11 GE-05.2     | `uv run --locked pytest -q tests/test_guest_inflight.py::test_queued_sse_final_is_dropped_at_expiry`                    | Held/replayed terminal output yields no secret/final after finalTcheck; idle stream closes              |
| 12 GE-05.3     | `uv run --locked pytest -q tests/test_guest_embeddings.py::test_late_embedding_cannot_recreate_deleted_memory`          | No late memory/vector/job upsert after purge/T                                                          |
| 13 GE-06.2     | `uv run --locked pytest -q tests/test_guest_cleanup_recovery.py::test_worker_crash_rolls_back_then_retries`             | SQL transaction rollback/lease recovery; job retries, no partial completion claim                       |
| 14 GE-06.1     | `uv run --locked pytest -q tests/test_guest_cleanup.py::test_purge_removes_every_guest_owned_store`                     | All allowed ownership variants 0; registered canaries unchanged; replay safe                            |
| 15 GE-06.2     | `uv run --locked pytest -q tests/test_guest_cleanup_recovery.py::test_failure_never_reactivates_guest`                  | Retry exhaustion/incident/flag off never changes kind/start/T or restores access                        |
| 16 GE-10.3     | `uv run --locked pytest -q tests/test_feedback_privacy.py::test_guest_purge_leaves_feedback_without_any_identity_link`  | Feedback remains; guest/receipt/attempt/provider mapping gone, no hidden identifier column              |
| 17 GE-07.2     | `uv run --locked pytest -q tests/test_guest_budget.py::test_purging_all_guests_cannot_reopen_daily_budget`              | New identity still blocked by detached spent/reserved liability                                         |
| 18 GE-14.1     | `uv run --locked pytest -q tests/test_auth_flows.py`                                                                    | Existing permanent sliding/login/reset/reauth/logout behavior passes unchanged                          |
| 19 GE-08.1     | `npm.cmd exec -- playwright test --config playwright.owned.config.ts auth.spec.ts --grep "callback"`                    | Callback consumed once, tokens sanitized before rendering/history/network, recovery usable              |
| 20 GE-08.2     | `npm.cmd exec -- playwright test --config playwright.owned.config.ts landing.spec.ts`                                   | Useful root/metadata with APIoffline;zero creation requests/identities                                  |
| 21 GE-13.2     | `npm.cmd exec -- playwright test --config playwright.owned.config.ts onboarding.spec.ts`                                | Keyboard/skip/replay/back/missing target≤3s/expiry work, zero data mutations                            |
| 22 GE-11.1     | `uv run --locked pytest -q tests/test_feedback_admin.py::test_feedback_admin_role_and_reauth_matrix`                    | Guest/user/moderator denied; fresh permanent admin only; independent flag and live revocation           |
| 23 GE-10.2     | `uv run --locked pytest -q tests/test_feedback.py::test_concurrent_feedback_replay_and_expiry`                          | Final authorization at T rolls back feedback+receipt+accepted counter; preT commit distinction explicit |
| 24 GE-14.1     | `uv run --locked pytest -q tests/test_guest_cleanup_recovery.py::test_flags_off_keep_expiry_cleanup_and_reconciliation` | New entry disabled; existing T denial, orphan reconciliation and purge still execute                    |
| 25 GE-14.3     | `uv run --locked pytest -q tests/test_guest_cleanup_recovery.py::test_guest_aware_rollback_cannot_resurrect`            | Compatible image/config/schema reject expired/restored guest; old registered-only image prohibited      |

Additional required tests: Origin/CSRF/idempotency ownership, classification map all operations, under 16/no implicit consent, missed provider/session mismatch, long tool/voice/export/HTTP response barrier, budgetunknown/actualoverrun/settlement race, runtime CRUD/helper privileges, redaction/retention, moderate/admin revocation, narrow/offline/loading/error/empty UI, snapshot/restore. Existing output safety/mood source/memory approval and registered matching v 1/v 2/shadow remain unchanged.

## Registered regression and manual evidence

Run full backend suite, not only guest selection: auth/eligibility/consent; AI availability/quota/recovery/validated output; history/export/delete; memory/source/version/semantic; mood-per-turn privacy; matching/profile/discovery/requests/pairs/messages; reveals/blocks/reports/moderation; structured activities/focus; account deletion and deployment/config. Preserve all existing tests and assertions. Fixture browser passes are not real backend proof; synthetic fullstack uses actual HTTP/PostgreSQL but fake providers, never hosted/model success.

UI matrix 320/390/430/768/1280/1440, landscape,200%text, keyboard/focus/contrast/44px controls, reduced motion, offline, loading/error/empty/quota/expired/ineligible. Manually record NVDA and available VoiceOver checks for Dialog/tour/rating group; unavailable hardware is explicit gap. Auth/CAPTCHA hosted/GDPR/provider/log/backup facts need approvedtarget/review; do not infer from mocks. Optional tour may staydisabled pending explicitly scoped release; core trial never depends on completing it.

### Task GE-14.1 — Integrate real synthetic journeys and regressions

**Objective:** Prove the three features work together through actual HTTP/UI. **Priority:** P0. **Dependencies:** GE-12.2, GE-13.2 (inline fallback acceptable if spotlight deferred).

**Architecture:** Extend existing tests.e 2e_server/LocalAuth and test_fullstack harness, never add production test endpoints.

**Files:** Create `frontend/tests/fullstack/guest-experience.spec.ts`; modify `backend/tests/e2e_server.py`, `backend/tests/e2e_auth.py:LocalAuth`, `frontend/tests/fullstack/helpers.ts`, `frontend/tests/e2e/ux-fixtures.ts`, `frontend/playwright.owned.config.ts`, `frontend/playwright.fullstack.config.ts`, screenshot-writing specs found by `rg -n 'screenshot|evidence/' frontend/tests`; extend planned test files in matrix. Never run the live-provider smoke entrypoint as this synthetic harness.

**Interfaces:** LocalAuth models anonymous flags/correlation/session/child fixtures; synthetic CAPTCHA only inside tests. Test-only SQL clock/seed helpers guarded by loopback *_test/APP_ENV=test and absent from production app/router. Production 7200 immutable constraint remains active. MOODPRINT_TEST_ARTIFACT_DIR override directs all output to temp.

- [ ] Step 1: Add fullstack journey landing→disclosure/age→intent→guest→explicit consent→five bots/mood/memory/voicepreview→feedback→T→purge→adminreview; assert two contexts isolated, no social peer, newtrial fresh, ordinary signup doesn't transfer. Add missing matrix tests by exact names and flags-off test.

Representative assertions (arranged entities/responses/observations from the named tests):

```typescript
await expect(
  page.getByRole("heading", { name: "L??t d?ng th? ?? k?t th?c" }),
).toBeVisible();
expect(guestDataTransferredToRegisteredAccount).toBe(false);
expect(guestSocialResponsesWithPrivateData).toHaveLength(0);
```

- [ ] Step 2: Backend `uv run --locked python ../scripts/test_fullstack.py guest-experience.spec.ts guest-journey.spec.ts guest-feedback.spec.ts --reporter=list` -> meaningful missing harness/journey failures, not hosted fallback.
- [ ] Step 3: Extend synthetic transports/harness and artifact override; use backend production routes throughout, no browser request interception in fullstack. Keep existing registered synthetic actors.
- [ ] Step 4: Same command ->PASS; run each mandatory row command and record evidence identifiers.
- [ ] Step 5: Execute full baseline/check table and CI-required categories, separate DBs; rerun complete fullstack/fixture suites with existing registered scenarios.
- [ ] Step 6: Review synthetic boundaries, no external keys/calls, generated drift and data/privacy negative evidence; diagnose new failures with systematic-debugging.
- [ ] Step 7: Commit `test(guests): cover integrated experience and regressions`.

**Acceptance:** All 25localnegative oracles plus full journeys/regression pass; blocked external/manual marked separately. **Edge cases:** fixture reruns/cleanup, auth 503, occupiedports, artifact paths. **Rollback:** test-only changes don't weaken production guards. **Completion evidence:** exact commands/counts/no-skip DB proof, transient artifacts and screenshots outside commits.

### Task GE-14.2 — Measure capacity and rehearse failure/restore

**Objective:** Verify one-worker 50-visitor behavior and durable recovery. **Priority:** P0. **Dependencies:** GE-14.1.

**Architecture:** Extend synthetic load pattern; bounded guest concurrency and registered canary; isolate from other suites.

**Files:** Create `scripts/load_guest_experience.py`, `backend/tests/guest_load_server.py`, `backend/tests/test_guest_restore.py`; reuse `scripts/load_chat_memory.py`, `backend/tests/chat_load_server.py`; create `docs/guest-experience/implementation/evidence/capacity-recovery.md`.

**Interfaces:** New load CLI `--workers 1 --users 50 --port 8018 --output <temp.json> [--crash-kill]`; refuses workers≠1, nonloopback/*_test targets, occupiedports/external providers. Sample p 50/p 95/max/non-AI+AI latency, HTTPerrors, actual active admitted guest AI/STT≤10/3, poolwait/connections/RSS/SSE/backlog/cleanup lag, registered canary responsiveness, detachedbudget. No silent retries/parameter changes.

- [ ] Step 1: Add failing assertions in `test_guest_restore.py`: restored expired guest 401 even before cleanup, cleanup removes all before quarantine is lifted; stale attempt/reservation cannot replay provider; live registered canary remains. Add load script self-checks rejecting unsafe targets.

Representative assertions (arranged entities/responses/observations from the named tests):

```python
assert restored_expired_guest_response.status_code == 401
assert provider_calls_replayed_after_restart == 0
assert registered_canary_after == registered_canary_before
```

- [ ] Step 2: `uv run --locked pytest -q tests/test_guest_restore.py` -> expected restore/gate gaps identified.
- [ ] Step 3: Implement synthetic 50 visitor workload: all browse/journal/read; concurrency≥guest cap triggers clean 429retry UI rather than unboundedqueue; mix≤10 activeAI/3 voice plus registered canary. Expire cohort, pause/resume worker, steallease/restart owned server, settle uncertain costs. Restore only disposable snapshot in quarantined local target; expiry+purge/retention before network exposure.
- [ ] Step 4: `uv run --locked pytest -q tests/test_guest_restore.py` ->PASS. Set load DB URL then `uv run --locked python ../scripts/load_chat_memory.py --workers 1 --users 50 --port 8017 --output "$env:TEMP/moodprint-registered-50.json"`; then new `uv run --locked python ../scripts/load_guest_experience.py --workers 1 --users 50 --port 8018 --output "$env:TEMP/moodprint-guest-50.json"`; repeat new command with --crash-kill and a distinct output.
- [ ] Step 5: Compare default quotas/security/no 500/zero leaks, proposed healthy cleanup≤60s/≤5min, registered canary success; latency/memory/pool figures reported against observed baseline, not an invented approved productionSLO. Investigate unexplained stalls/failures, including historical overlappingrun; don't infer contention as proven cause.
- [ ] Step 6: Review no real provider/cost test claims, processcleanup owns only launched PIDs; report available target hardware and remaining production capacity uncertainty.
- [ ] Step 7: Commit `test(guests): measure bounded load and recovery`.

**Acceptance:** No privacy/auth/counter violation,50 visitors handled within configured capacity; measured output archived, no unsupported 50concurrent paid guarantee. **Edge cases:** cancellation-resistant fake, worker death,backlog, restore incident. **Rollback:** no production resource created; leave owned local test artifacts as evidence. **Completion evidence:** load JSON/counts/failure cause status and restore quarantine proof.

### Task GE-14.3 — Prepare reviewed release and guest-safe rollback

**Objective:** Concrete reviewable package and go/no-go, no release execution. **Priority:** P0. **Dependencies:** GE-14.2; GE-01.2 is required for G1 pass but can remain explicitly blocked by D04.

**Architecture:** Compatible expand schema/app; entry/paid/feedback/tour gated independently; current guest authorization/cleanup never removed.

**Files:** Create `scripts/prepare_guest_migration_review.py`, `scripts/verify_guest_migration_review.py` (local only), `backend/tests/test_guest_migration_review.py`; create `docs/guest-experience/implementation/evidence/release-readiness.md`, `rollback.md`; modify `deploy/runtime.env.example`, `docs/backend/configuration.md`, `docs/supabase/migrations.md`, `deploy/README.md`; extend `test_guest_cleanup_recovery.py`.

**Interfaces:** Prepare CLI `--from-revision 0015_context_privacy --output <owned-temp-or-deploy/supabase/reports/file.sql>` invokes offline `alembic upgrade 0015_context_privacy:head --sql`, writes UTF8 exactbytes/SHA256, no DBconnection. Verify CLI `--sql <pending.sql>` runs only on explicit empty loopback *_test DB and rolls back DDL; checks runtime CRUD/helper isolation and seeded authorization under new schema. Pending SQL lives outside pinned reviewed-sql directory.

- [ ] Step 1: Add `test_pending_review_never_executes_remote_or_overwrites_approval` and `test_guest_aware_rollback_cannot_resurrect`: unknown remote/old registered-only image refused; flags off leave deadline/jobs; no changing existing approvedSQL/MANIFEST. Run `uv run --locked pytest -q tests/test_guest_migration_review.py tests/test_guest_cleanup_recovery.py -k 'review or rollback'` -> meaningful missinggate failures.

Representative assertions (arranged entities/responses/observations from the named tests):

```python
assert remote_mutations == []
assert approved_artifact_hashes_after == approved_artifact_hashes_before
assert expired_guest_after_rollback_response.status_code == 401
```

- [ ] Step 2: Implement local pending-artifact generator/validator and compatibility rollback test. **Do not run existing prepare_supabase_migration.py against new head**: it expects 24 initial tables and would overwrite approved initialization SQL. Its baseline files/pins remain unchanged; modifications to helper/bootstrap checks require distinct pending review, not approval forgery.
- [ ] Step 3: Run same tests ->PASS; generate pending SQL from actual inspected priorhead, rehearse on empty localreview DB, record revision order/locks/backfill/trigger/grant diffs and contract changes. Existing `python scripts/check_reviewed_artifacts.py` must still pass for approved historical artifacts; it is not approval of pending new SQL.
- [ ] Step 4: Run Linux CI/poller/proxy/packaging and documentation checks; gather finalphase independent review where available. Re-run tests for any findings fixed.
- [ ] Step 5: Populate G0–G6 below with actualPASS/PARTIAL/FAIL, D01–D04 status, migration/image/branch/commits, allmanual/external gaps, narrow feature flags/cohort steps/monitoring/rollback. No owner decision invented; optional spotlight explicitoff if deferred.
- [ ] Step 6: Review release package for secrets, correct hostedtarget (when approved), durablecleanup rollback compatibility and unsafe oldimage prevention. Stay on the feature branch, leaveworktree intact.
- [ ] Step 7: Commit `docs(guests): prepare release evidence and safe rollback`; stop before hosted migration/settings/deploy/merge/public enablement. Do not ask routine development permission; present only concrete external actions requiring separate ownerdecision.

**Acceptance:** Fullsafe local work complete, pending reviewedSQL reproducible, no fabricated approval/push/merge/deploy. **Edge cases:** newer main/revision, historical SQL checks, Windowsfcntl, production restore. **Rollback:** below. **Completion evidence:** final inventory/commands/testcounts/review/deviations and status table.

## Release holds and rollback

| Gate               | Evidence to pass / hold                                                                                                                      |
| ------------------ | -------------------------------------------------------------------------------------------------------------------------------------------- |
| G0 baseline        | Currentmain/tree/versions+isolated baseline; capacity failure diagnosed sufficiently for target, no fake→production inference                |
| G1 schema/Auth     | Migration/runtime helper/grants/drift; GE-01.2 approved hosted anonymous/CAPTCHA/cascade/upstreamburst proof; D04 otherwise PARTIAL          |
| G2 authorization   | All expiry/route/peer/ownership/CSRF/tool/SSE/late publication races and registered regressions pass                                         |
| G3 cleanup/privacy | Exhaustive inventory/lease/retry/incident/restore, lagalerts; D01 disclosure/SLO/provider/log/backup review; D03 separate feedback retention |
| G4 cost/capacity   | D02 positive numerical approval, known model/STT/embed bounds/reservations, uncertaincost/cleanup tests, measured 50visitoroneworkerheadroom |
| G5 UX/feedback     | States/mobile/keyboard/SR/callback; feedback admin/separation; spotlight compatibility accepted or explicitly deferredoff                    |
| G6 release         | Linuxpoller/proxy/image/contract/docs/artifact review; exact SQL/image package and separate owner release authorization                      |

Proposed rollout after approval: compatible schema/app with entry/paid/feedback/touroff → verify privateguards/workers/health → approved small cohort → monitor → widen. GUEST_AUTH_ENABLED=false stops only new intents/signups, not existing lifetime/cleanup; GUEST_PAID_ENABLED=false stops new paid calls, conservatively settles in-flight liabilities; FEEDBACK_ENABLED=false stops submissions, notretention; FEEDBACK_ADMIN_ENABLED=false hidesreviewAPI; PRODUCT_TOUR_ENABLED=false tearsdown/blocksnewtour as readiness refreshes.

Rollback must use a prepared **guest-aware compatible image that recognizes actual schema head**, or a maintained guest-denial/cleanup compatibility service until zero guest/attempt work remains. READY_REVISIONS cannot blindly accept incompatible heads. Never deploy the old currentmain image that interprets every user as registered. No destructive Alembic downgrade, dropped guest columns, resetdeadline, refunded uncertain budget or stoppedcleanup. Expired restored guests remain denied; quarantine any restore, enforce expiry/retention/purge before exposing service. Actual production restore requires separate approval.

Monitor content-free counts/latencies only: admission rejections, activeguests/expirydenial, cleanup lag/retry/incident/orphan, financial reservations/uncertain/overrun, DBpoolwait/RSS/SSE/500s. No tokens/raw IP/comments/conversations/audio/user IDs in guest operational metrics. Runbook escalation >5min cleanup, ambiguous orphan>24h, overrun or authorization bypass → entry/paid off, preserve evidence, keepdenial/cleanup.

## Planning-session validation record

Planning-only validation observed on 2026-10-28, Asia/Bangkok:

| Executed check                                                                                                                    | Observed result                                                                                                                                                                                    |
| --------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `python scripts/check_docs.py`                                                                                                    | PASS: 51 Markdown files, 390 local links, 100 API operations, 48 settings, 38 current ORM tables                                                                                                   |
| `python scripts/check_reviewed_artifacts.py`                                                                                      | PASS: 9 pinned approvals, 9 consumed by scripts; no approved SQL modified                                                                                                                          |
| `node frontend/node_modules/prettier/bin/prettier.cjs --write 'docs/guest-experience/implementation/*.md'`, followed by `--check` | PASS: all 10 new plans conform after formatting; original audits were excluded                                                                                                                     |
| Inline read-only Python structure/link/dependency/hash validator                                                                  | PASS: 10 documents, 35 unique subtasks/15 GE parents, 34 test assertion snippets, 25 mandatory scenario rows, prerequisite order, balanced fences, 9 fragment links and 18 handoff bootstrap paths |
| SHA256 comparison of original nine audits                                                                                         | PASS: every byte hash matches initial inspection                                                                                                                                                   |
| `git diff --exit-code`; `git diff --cached --exit-code`; `git status --short --untracked-files=all`                               | Tracked/staged diffs empty, including .gitignore; only the original untracked audits and 10 new implementation Markdown files                                                                      |

Self-review corrected the actual activity-worker and synthetic-Auth paths, guest account-delete204 behavior, permanent-token recovery conversion denial, quota-claim producer order, mapped recovery/cleanup lock order, late financial settlement and durable spending halt semantics. No application feature, migration, new test or configuration was implemented. Application/static/type/build/runtime/manual/hosted checks are future Sonnet gates, not passes from this documentation session. No production mutation or paid test occurred. Planning is CONDITIONALLY_READY for local implementation; public release remains PARTIAL pending D01–D04 and the G0–G6 evidence.
