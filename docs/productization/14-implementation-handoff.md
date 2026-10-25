# 14 — Implementation Handoff (fresh-session entry point)

You are starting implementation of the MoodPrint productization program with no prior chat context. This page is sufficient to begin; everything else is linked.

## 1. Read in this order

1. This page.
2. [Implementation plan](../plans/2026-10-25-moodprint-productization-implementation.md): Global Constraints, Review Focus, Common commands, then Phase A.
3. [01 — Codebase audit](01-codebase-audit.md) §2–§3 (what exists; confirmed defects).
4. The spec for the phase you are on: B/C → [05](05-matching-design.md), [07](07-database-and-api-contracts.md); D–G → [06](06-shared-activities-design.md); H → [08](08-frontend-ux-plan.md); I → [09](09-security-privacy-operations.md); J → [10](10-testing-evaluation-strategy.md), [11](11-migration-and-rollback.md), [12](12-release-readiness.md).
5. Repository rules: `CLAUDE.md` (root), `README.md`, `deploy/README.md`.

## 2. Architecture decisions already made (do not re-litigate)

DR-01 SSE watermark (`connections.activity_seq`) for activity sync · DR-02 delete prototype · DR-03 connections survive profile edits (**confirm with owner before release R1**) · DR-04 deterministic `rules-v2` scorer, no runtime model calls · DR-05 no percentages · DR-06 per-pair alias · DR-07 request sender card · DR-08 three activities, one active per connection · DR-09 static content banks · DR-10 retire outbox · DR-11 staff moderation API + screen · DR-12 AI daily quota + global ceiling · DR-13 read markers, no read receipts · DR-14 migrations 0011–0014 expand-only · DR-15 single worker · DR-16 `READY_REVISIONS` · DR-17 English practice post-MVP · DR-18 soft goals + `strictGoal`. Details: [13](13-risks-and-decisions.md).

## 3. Implementation order

A-01 → A-02 → (A-03, A-04, A-05) → B-01 → B-02 → B-03 → B-04 → (B-05, B-06) → C-01 → C-02 → C-03 → C-04 → C-05 → (C-06, C-07, C-08) → D-01 → D-02 → D-03 → (D-04, D-05, D-06) → D-07 → E-01..E-03 → F-01..F-03 → G-01..G-03 → H-01..H-04 → I-01..I-08 (I-05, I-06, I-07, I-08 can start any time after A) → J-01 → J-02 → J-03* → J-04* → J-05. (*approval-gated.) The authoritative graph is in the plan.

Track progress by ticking checkboxes in the plan and adding evidence files under `docs/productization/evidence/`.

## 4. Skills to use

- If installed: `superpowers:executing-plans` (or `subagent-driven-development`), `superpowers:test-driven-development`, `superpowers:systematic-debugging`, `superpowers:requesting-code-review`, `superpowers:verification-before-completion`.
- Superpowers was **not installed** in the planning environment (checked 2026-10-25). Project-local equivalents in `.claude/skills/`: `/test-first-engineering`, `/feature-delivery`, `/root-cause-debugging`, `/api-contract-testing`, `/browser-e2e-testing`, `/accessible-web-testing`, `/change-review`, `/security-audit`, `/evidence-gated-completion`, `/release-readiness`, plus `supabase-postgres-best-practices` before writing migrations.

## 5. Environment

Backend settings (`backend/app/core/config.py`; never commit values; `backend/.env` is the developer's file and points at the **hosted** project — do not use it for tests or Alembic):

| Variable | Needed for | Notes |
|---|---|---|
| `TEST_DATABASE_URL` | all backend tests, full-stack harness | must be a local DB whose name ends `_test` |
| `DATABASE_MIGRATION_URL` | local Alembic | pass explicitly, local host only (`env.py` refuses others) |
| `DATABASE_URL` | running the API locally | local DB for dev; hosted only in deployed environments |
| `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY` | real login (not tests) | |
| `FRONTEND_ORIGIN`, `COOKIE_SECURE` | origin/CSRF checks | |
| `OPENAI_API_KEY`, `OPENAI_MODEL`, `AI_ENABLED` | live AI only | tests force AI off and use the SDK fake model |
| `AI_ACCOUNTING_ENABLED` | AI budget ceiling (I-05) | hosted schema already has `ai_usage` |
| `SEMANTIC_MEMORY_ENABLED`, `VOYAGE_*` | semantic memory | keep off unless approved (Q-02) |
| New: `MATCHING_SCORER`, `ACTIVITIES_ENABLED`, `ACTIVITY_KINDS`, `MODERATION_ADMIN_ENABLED`, `AI_DAILY_TURNS_PER_USER`, `AI_DAILY_BUDGET_USD` | added by tasks C-02, D-03, I-01, I-05 | defaults in [07 §5](07-database-and-api-contracts.md#5-settings-added-backendappcoreconfigpy); add to `backend/.env.example` and `deploy/runtime.env.example` |

Local infrastructure: Docker container `moodprint-ai-memory-pg` (PostgreSQL 17 + pgvector) on `127.0.0.1:16432`; read the password with `docker exec moodprint-ai-memory-pg printenv POSTGRES_PASSWORD` and never print it. PostgreSQL roles are cluster-wide: if you create `moodprint_runtime` manually, drop it afterwards or `tests/test_runtime_provision.py` breaks.

## 6. Database safety boundaries

- Allowed without asking: creating/dropping local databases whose names end `_test` on the local container; `alembic upgrade/check` against them.
- **Requires explicit approval each time**: any SQL against the hosted Supabase project `roznanxbiyqybjpvtilq` (including `apply_supabase_review.py --apply`), hosted fixture runs (`scripts/test_supabase_fullstack.py`), production data reads beyond read-only advisors, AWS changes, deploys, billable live AI runs.
- Never: `alembic upgrade` online against hosted; Supabase MCP `apply_migration`; DROP/TRUNCATE in migrations; `format('%I')` in migration SQL (offline SQL keeps `%%`).

## 7. Current Git revision

- Audited: `5689dd9c725d625acfc7bc3a322548295a29608b` on `main`.
- Planning documents: committed on branch `docs/productization-plan` (see [§11](#11-planning-review-record) for the commit SHA). The user's uncommitted `.gitignore` change was left untouched.
- Start implementation on a new branch from `main` after the planning branch is reviewed/merged: `git switch -c feat/productization`.

## 8. Test commands

See the plan's "Common commands" (VC-DB, VC-BE, VC-BE-T, VC-MIG, VC-SQL, VC-CONTRACT, VC-FE, VC-FS). Baseline on 2026-10-25: ruff PASS, mypy PASS (61 files), pytest **278 passed**, frontend typecheck PASS, vitest **89 passed**; mocked Playwright 34 and full-stack 13 per the last recorded run (not re-run during planning).

## 9. Completion criteria

- Every task's acceptance and verification met with recorded evidence; plan checkboxes ticked.
- Release gates in [12 §2](12-release-readiness.md#2-gono-go-gates-all-must-be-pass-with-evidence-links) evaluated in J-05 as PASS/FAIL/BLOCKED; overall status PASS only if all gates PASS (otherwise PARTIAL/HOLD).
- Before claiming completion of any task, run `/evidence-gated-completion` (or `superpowers:verification-before-completion`).

## 10. Known blockers and work that must NOT be repeated

Blockers (external): Q-01 (DR-03 confirmation), Q-02 (provider/legal), Q-03 (moderators), Q-04 (Supabase plan/backups), Q-05 (SMTP), Q-06 (AWS/domain). Staging deploy (J-04) and hosted migrations (J-03 apply) cannot complete without them/approval.

Do **not** repeat:

- The codebase audit and prototype inventory (this set); only re-verify a claim if code changed.
- Hosted Supabase initialization, runtime role provisioning, Auth bridge helper, migrations 0001–0010 (already applied; hosted at `0010_account_deletion`).
- Prior live-AI evaluations and prompt selection (`backend/evals`, `docs/plans/validation-artifacts/live-ai`).
- The MVP-completion fixes recorded in `docs/mvp-validation/README.md` (mood timezone, `needs_republish`, report-after-block, social export, stream fallback).
- Re-deciding architecture (DR-01…DR-18) unless a task's tests prove a decision infeasible — then record a new decision in [13](13-risks-and-decisions.md).

## 11. Planning review record

Documentation-only review performed on 2026-10-25:

| Check | Result |
|---|---|
| Required files (15 productization docs + 2 plan artifacts) exist | PASS |
| Local links (233) and source line anchors (66) resolve; heading anchors exist; code fences balanced | PASS (scratchpad validator; not committed) |
| Referenced source paths exist, or are explicitly planned new files (87 planned paths reviewed) | PASS |
| Task graph: 52 tasks, 82 dependency edges, acyclic, Mermaid graph = `Depends:` fields, checklist complete | PASS |
| Every requirement (45) traced to tasks; every test ID referenced exists in the catalog (44); every task has acceptance + verification | PASS |
| Legacy `python scripts/check_plans.py` still passes (CI unaffected) | PASS — "12 plans; 39 tasks; 43 planned test IDs; 130 local links; DAG acyclic" |
| Independent read-only reviewer subagent | **BLOCKED** — stopped on an API session limit before reporting; replaced by a focused self-review against the code |

Findings from the self-review and fixes applied:

1. **HIGH** — B-02 (connections survive republish) originally missed the full-snapshot comparisons in discovery (`social/retrieval.py` and the `candidates` recheck) and in `decide()` replay; a connected peer would have reappeared as a candidate. Fixed: B-02 now enumerates every comparison site and adds tests 6–7.
2. **HIGH** — abort hooks could lock a session before its room. Fixed: hooks lock `connections` rows first (06 §13, D-05).
3. **MEDIUM** — hook location was inconsistent (06 said `invalidate_user_social`, D-05 said `interaction`). Unified on `interaction()`.
4. **MEDIUM** — `ConnectionView.activeActivity` had no owning task. Assigned to D-03.
5. **MEDIUM** — suspension acceptance needed a login check that wasn't listed. Added `auth/routes.py` to I-03.
6. **MEDIUM** — report retention (1 year) had no owner. Added the purge to I-01.
7. **MEDIUM** — the review SQL must byte-match `apply_supabase_review.py`'s regeneration. Added `VC-SQL` with the exact environment.
8. **MEDIUM** — readiness rollback gap for the first migration. Added `READY_REVISIONS` and release R0.5 (11 §3, B-04).
9. **LOW** — ID collisions between decisions/defects and task IDs. Renamed to `DR-*`, `DEF-*`, `PR-ACT-*`, `PR-FND-*`.
10. **LOW** — JSONB `?|` binding pitfall. Added an expression-API note (05 §9).

Commit: the planning documents are committed on branch `docs/productization-plan` (`git log -1 -- docs/productization` shows the SHA). Only files under `docs/productization/` and the two `docs/plans/2026-10-25-*.md` files are included.
