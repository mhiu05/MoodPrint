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
- [ ] Run locked dependencies, Ruff, mypy, PostgreSQL backend tests, OpenAPI drift, frontend unit/type/build/security checks.
- [ ] Run browser E2E, both full-stack scorers, migration chain, release-poller tests and production image/Compose checks.
- [ ] Verify exact hosted identity/roles/counts/constraints; obtain fresh protected backup; restore and rehearse reviewed 0011–0014 SQL with matching hashes.
- [ ] Inspect AWS deployed SHA/images/configuration/poller/rollback; prepare safe migration and deployment ordering.
- [ ] Publish integration PR and wait for required GitHub Actions checks. Merge only if all mandatory safeguards pass.
- [ ] Deploy through existing pipeline, verify domain with real authenticated browser/API/provider/two-user journeys and bounded performance measurements.
- [ ] Fix observed defects through tests and CI, then repeat live verification.
- [ ] Delete only the three named obsolete branches after successful live acceptance; close superseded PR #9 then.
- [ ] Record actual commands/results, deployment timeline, remaining blockers and final release verdict.

Initial blockers: AWS profile moodprint is expired (login confirmation pending). Hosted baseline is 0010_account_deletion; backup and rehearsal not yet verified. Initial HTTP/TLS/liveness/readiness pass against the old deployed release; these are not candidate acceptance evidence.
