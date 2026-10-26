# MoodPrint MVP release execution plan

**Goal:** Integrate the three development branches and release safely to moodprint.duckdns.org.

**Architecture:** React/Vite frontend, single-worker FastAPI backend, hosted Supabase PostgreSQL/Auth, existing EC2 in ap-southeast-2. GitHub push CI publishes digest-pinned releases from main; EC2 polls every five minutes. No hosted migration is performed by the poller.

**Spec:** Product owner's full release directive supplied 2026-10-26.

## Constraints and review focus

- Preserve all existing work, credentials, production data, consent and safety controls.
- No manual .gitignore edits, force pushes or early branch deletion.
- A fresh recoverable backup, isolated restore and exact reviewed SQL rehearsal precede hosted DDL.
- Main merge can trigger deployment; keep it gated until database/configuration and rollback are ready.
- Test saved-history restoration, actor isolation, rollback scorer and all three activities on the integrated tree.
- Unknown credentials, provider behavior, capacity or operator coverage are blocked checks, never PASS.

## Execution ledger

- [x] Fetch references, inspect graph/PR #9/current public health and hosted revision.
- [x] Create external integration worktree from latest origin/main; merge productization then local MVP without duplicating product-experience.
- [x] Run locked dependencies, Ruff, mypy, PostgreSQL backend tests, OpenAPI drift, frontend unit/type/build/security checks.
- [x] Run browser E2E, both full-stack scorers, migration chain, release-poller tests and production image/Compose checks.
- [x] Verify exact hosted identity/roles/counts/constraints; obtain fresh protected backup; restore and rehearse reviewed 0011–0014 SQL with matching hashes.
- [x] Inspect AWS deployed SHA/images/configuration/poller/rollback; prepare safe migration and deployment ordering.
- [x] Publish integration PR and wait for required GitHub Actions checks. Merge only if all mandatory safeguards pass.
- [x] Deploy through existing pipeline, verify domain with real authenticated browser/API/provider/two-user journeys and bounded performance measurements.
- [x] Fix observed defects through tests and CI, then repeat live verification.
- [x] Delete only the three named obsolete branches after successful live acceptance; handle superseded PR #9.
- [x] Record actual commands/results, deployment timeline, remaining blockers and final release verdict.

Initial blockers (subsequently resolved): expired AWS profile; hosted0010 with backup/rehearsal pending. Initial health against the old release was not candidate acceptance evidence. The final release report supersedes intermediate progress below.

## Execution update, 2026-10-26 Asia/Bangkok

- Both original blockers resolved. Hosted0014 is verified:39RLS tables, preserved385rows, no invalid constraints, correct runtime grants without RLS bypass.
- Fresh pre-deployment backup20261025T234120Z restored with all39 exact table counts matching; encrypted backup retained outside Git.
- Integration PR11 merged as cfc3a11. Its main CI correctly blocked publishing after detecting transient dialog contrast during opacity animation.
- Hotfix PR12 removes the dialog opacity fade and adds an exact-open-frame browser regression (RED0→GREEN1).63 browser tests,54unit,type/build and3 focused full-stack journeys pass. Both PR/push CI passed; merged as4de7bb1b1c21c50444b80514cf56715a6155be1e. Main push CI40245721736 is running.
- Old2c remains public and healthy. Maintenance was removed during the CI fix; poller timer remains temporarily stopped. Re-enable gate for controlled deployment, then restore timer after release/recovery.
- Runtime version5 removes DATABASE_MIGRATION_URL from the application environment. It retains least-privileged backend access, verified providers, nonzero accounting safeguard, v1 scorer and activities off for the compatibility baseline.
- API confirmed disable_signup=true and confirmation-email protection after the renewed dashboard save. No staff operator: admin remains disabled.
- Bounded isolated10/20/50-user tests on EC2 have zero integrity/authorization errors but fail unchanged latency targets.50users plateau at41.3requests/s,12checked-out connections,77.3API CPU-seconds in80.75elapsed seconds. This is an isolated local-DB topology with API+driver sharing CPU, not a claim of hosted50-user capacity. Keep access restricted pending capacity work.
- Independent review found no P0/P1 in the contrast hotfix. It previously found and helped verify the fixed v1 goal race and incompatible historical-image rollback; the controlled compatible-image baseline remains required.

## Latest verified state, 00:21 UTC

- Main CI40245721736 and publish40246469472 succeeded. Exact4de images deployed and healthy.
- Core acceptance passed for all five real assistants, saved-history restoration, actual API restart continuation, explicit memory approval, real Voyage retrieval, cancellation/recovery, mood and responsive/accessibility checks.
- Compatible4de runtime/config preserved root-only before SSM version6 enabled matching v2/activities. Migration credentials are absent from the deployed application.
- Actual v2/mutual approval, two-user messaging/read markers, Icebreaker3rounds, Quiz5rounds and scoped one-shot export passed. Focus pause/reload/peer resume passed; actual15-minute completion remains running before block/report/privacy cleanup.
- Actual-domain authenticated read p95 ranges2774-3486ms,0errors across48samples: latency FAIL against500ms. Production DB select1 round trip approximately115ms; retain invite-only recommendation.
- Signup remains disabled, email confirmation retained; admin/STT/sandbox remain disabled. Poller timer/gate restoration and three-branch deletion await critical live completion.

## Final outcome

RELEASE_LIMITED. Actual Focus completed15minutes00:29:56, followed by block/report/admin-off acceptance. Scoped export/deletion/restored preferences/logout passed. Server confirmed3 users preserved, fixture profiles withdrawn, five new AI conversations and new memory/vector removed, all3 activities completed. Gate removed/timer active00:34:12; public HTTPS/assets/health passed00:34:20. Exactly three obsolete local/remote branches deleted; source worktrees preserved detached, root main4de7bb1 and private environment unchanged. PR9 was already automatically closed through integration; final explanation posted. Performance remains FAIL, signup/admin off, no unrestricted-launch claim. See [final release report](mvp-production-release.md).
