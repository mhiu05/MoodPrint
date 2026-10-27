# Guest experience implementation plan

> **For agentic workers:** Execute task by task using the applicable executing-plans workflow. Use subagent-driven development only when delegation is explicitly authorized by the user or applicable instructions. This file is a plan, not authorization to implement during the audit.

**Goal:** Add a safe two-hour guest trial, public landing/optional onboarding and voluntary application feedback while preserving registered-user behavior.

**Architecture:** Extend the existing FastAPI/Supabase Auth BFF and private PostgreSQL model. Store an immutable guest deadline, enforce it at every authorization boundary, purge with durable jobs, keep retained feedback unlinked, and retain the one-worker MVP topology.

**Tech stack:** Existing Python 3.12/FastAPI/SQLAlchemy/Alembic/PostgreSQL/pgvector, React 19/TypeScript/Vite/HashRouter/CSS/GSAP, pytest/Vitest/Playwright. Driver.js is a conditional dependency candidate, not installed or approved by this plan alone.

**Specs:** [02 guest design](02-guest-auth-design.md), [03 landing/tour](03-landing-onboarding-design.md), [04 feedback](04-feedback-system-design.md), with evidence in [01](01-current-architecture-audit.md) and release tests in [06](06-testing-and-release-plan.md).

## Global constraints

- Work on a **separate feature branch**, proposed `feature/guest-experience`; preserve all user edits. Do not change `.gitignore` or existing configuration without task necessity and authorization.
- No production data, migrations, Dashboard settings, merges, deployments, paid model runs or infrastructure changes without a later explicit release decision and target/budget approval.
- Guest lifetime **exactly 7200 seconds from database grant time**, absolute, never sliding or reset by refresh/retry/restart. Registered behavior remains as before.
- Keep 16+ personal eligibility, 18+ registered social eligibility, explicit AI/MEM/VOICE consent, approved memory, ownership, CSRF and server authorization. Never enable MATCH for a guest.
- No automatic guest creation on a public page load. No shared demo identity, real-user fixtures, raw token logging, implicit data conversion or full guest-data migration to Redis.
- Proposed guest quotas: 25 AI turns/trial, 6/min, 1 active; initially 10 global guest runs; voice 6 clips/180s per trial, 2/min, 1 active/guest and 3 global. Owner-approved nonzero spend budget before paid guest availability.
- Guest active-store cleanup target: start ≤60s and complete ≤5min under healthy services, with alerts/retry. This is not universal backup/provider erasure at T.
- Retained feedback must contain no identity/session/provider/private-content reference; publish approved separate-retention disclosure before accepting it.
- Proposed flags default false: `GUEST_AUTH_ENABLED`, `FEEDBACK_ENABLED`, `FEEDBACK_ADMIN_ENABLED`, `PRODUCT_TOUR_ENABLED`. Disabling guest entry must **not disable expiry or cleanup**.
- Follow existing generated OpenAPI/TypeScript and reviewed-SQL artifacts workflow; do not silently pick a migration number without checking current head.

## Review focus

1. Request starts before expiry but blocks until after T: no late private output/authorization or data resurrection.
2. Guest creation succeeds upstream but DB/HTTP fails: recover same deadline or purge orphan; no identity farming through retry.
3. Client loses its cookie or forges consent/profile/room IDs: no previous guest recovery, social access or cross-owner existence leak.
4. Guest purge removes usage/receipts: retained feedback stays unlinked and daily spend cannot reopen.
5. Public callback/deep links and optional tour encounter recovery tokens, hidden navigation, missing targets or active drafts: safe navigation/focus, no secret leak or data loss.

Every task below owns tests for its associated review focus. Every implementation task uses this cycle: add the named failing case → run and observe failure → implement the specified interface/behavior → rerun targeted tests → run relevant broader checks → review diff → make a focused feature-branch commit. Do not mark checkboxes from prose expectations alone.

## Phase 0 — Establish release assumptions and compatibility

### GE-00 — Freeze baseline, constraints and capacity reproduction

| Item | Task |
|---|---|
| Objective / priority / risk | Rebase evidence on latest main, preserve work and reproduce capacity limitation; **P0 / medium** |
| Dependencies | None |
| Files | Read `AGENTS.md`, `ARCHITECTURE.md`, manifests, these nine documents, `scripts/load_chat_memory.py`, `backend/tests/chat_load_server.py`; write only new feature validation notes initially |
| Approach | Record SHA/status, tool versions and safe target; run baseline in disposable DBs. Reproduce the audit's 50-user SSE failure in isolation before declaring capacity. Do not increase timeout, reduce users or weaken assertions to manufacture PASS |
| Acceptance | Baseline failures recorded separately; no source changes mixed into setup; owner decisions from 07 assigned; unresolved capacity remains a release gate |
| Required tests | Current backend/frontend/migration/fixture/fullstack suites; existing load harness at 50 visitors/one worker; content-free error/latency evidence |

- [ ] Create feature branch from reviewed main without overwriting user work.
- [ ] Run commands in [06 §1](06-testing-and-release-plan.md#1-executed-audit-baseline); record actual environment and outcomes.
- [ ] Confirm proposed disclosure, feedback retention and spend budget decisions; implementation may proceed with flags off while release decisions remain open.

### GE-01 — Prove hosted anonymous compatibility and abuse path

| Item | Task |
|---|---|
| Objective / priority / risk | Prove integration instead of relying on the Dashboard toggle; **P0 / high** |
| Dependencies | GE-00; explicit non-production Auth target authorization before hosted writes |
| Files | `backend/tests/test_guest_provider.py` (new), `backend/tests/test_auth_flows.py`, `backend/tests/conftest.py`, proposed `backend/tests/live/test_guest_auth_compatibility.py`; docs under `docs/guest-experience/` for sanitized evidence |
| Approach | Add fake provider anonymous claims/body/captcha and mandatory server correlation cases. Separately prove a synthetic hosted user/session can be created/verified and deleted through existing app/helper model, including narrow orphan-marker lookup/delete privilege. Verify rate-limit burst from BFF egress and approved CAPTCHA path; confirm header strategy from official docs |
| Acceptance | Verified boolean anonymous identity; no password/email requirement; 50-user entry feasibility documented; provider child deletion proven; no secrets retained. If no approved hosted target exists, record BLOCKED hosted check and keep rollout disabled |
| Required tests | Mismatched sub/issuer/anonymous status/session; invalid/expired token; provider 429/5xx; unsupported CAPTCHA; upstream success + local failure |

- [ ] Add exact anonymous wire-contract tests before changing provider code; run `uv run --locked pytest -q tests/test_guest_provider.py`.
- [ ] Record hosted integration evidence only after target approval; do not use production trial identities for destructive testing.

## Phase 1 — Backend identity and authorization before UI entry

### GE-02 — Expand account model and public contracts

| Item | Task |
|---|---|
| Objective / priority / risk | Introduce server-owned guest lifetime/capabilities compatibly; **P0 / high** |
| Dependencies | GE-01 provider contract, GE-00 migration head |
| Files | `backend/app/infrastructure/database/models.py`, `backend/app/contracts.py`, `backend/app/core/config.py`, `backend/app/core/revisions.py`, new `backend/app/modules/guests/models.py`, next Alembic revision, reviewed SQL/manifest through existing tools; generated `backend/openapi.json`, `frontend/src/api/generated/schema.d.ts`, `frontend/src/api/contracts.ts` |
| Approach | Add kind/start/deadline constraints, session created_at, lifecycle/provision/usage tables from 02. Old rows default registered with null guest times. Add flags and SessionView fields, server-derived capabilities. Private runtime grants/RLS only |
| Acceptance | Expand migration works from empty and existing schema; registered rows/URLs unaffected; invalid guest deadlines/type edits rejected; no public table/helper access; readiness recognizes reviewed compatible revision |
| Required tests | New `backend/tests/test_guest_schema.py`; migration upgrade/check; registered default/null serialization; frontend fixture contract updates; generated drift |

**Interfaces:** `SessionView.account_kind`, `guest_started_at`, `guest_expires_at`, `guest_quota`; `GuestCleanupJob`, `GuestProvisioningAttempt`, `GuestUsage` ORM records; field camelCase in HTTP.

- [ ] Pin constraint cases: guest expiry differs from start by 7199/7201 seconds fails, exactly 7200 succeeds; registered timestamps non-null fail.
- [ ] Run schema/migration tests and generate contracts using existing offline scripts; verify only intended contract changes.

### GE-03 — Implement absolute lifetime and registered-only service gates

| Item | Task |
|---|---|
| Objective / priority / risk | Make direct APIs safe before any anonymous provisioning is exposed; **P0 / critical** |
| Dependencies | GE-02 |
| Files | `backend/app/core/security.py`, `backend/app/infrastructure/database/provider_session.sql`, new `backend/app/modules/guests/policy.py`, `auth/routes.py`, `consent/routes.py`, `social/service.py`, `social/retrieval.py`, `social/routes.py`, `social/summary.py`, `social/notifications.py`, `activities/routes.py`, `moderation/routes.py`, `moderation/staff.py` |
| Approach | Add fresh DB-time guest predicate to validation/helper; skip sliding renewal for guests. Enforce registered kind in MATCH, consent enable, all social reads/writes/peer gates/staff; deliberate zero summary projection without reads. Preserve own personal profile routes |
| Acceptance | `T−1ms` valid; `T`/`T+1ms` denied; direct restricted API requests fail regardless of forged rows/consents; registered behavior unchanged; no another-user private data leakage |
| Required tests | New `test_guest_expiration.py`, `test_guest_permissions.py`; parameterized endpoint inventory; existing auth/eligibility/social/matching/moderation regressions |

**Interfaces:** `async database_time(db)->datetime`; `async assert_guest_active(db,user,*,at=None)->None` (explicit time is internal/test-controlled only); `require_registered_user(user)->None`; preserve public `require_actor`/`transaction` signatures. Production policy always obtains fresh DB time, never client `at`.

- [ ] Write deterministic predicate and real-DB-helper boundary tests; include multi-tab sliding attempts and missing provider session.
- [ ] Test both requester and peer classification and fabricated preexisting guest social rows before marking permission task complete.

### GE-04 — Add idempotent anonymous provisioning and guest end

| Item | Task |
|---|---|
| Objective / priority / risk | Issue isolated sessions using existing BFF; **P0 / critical** |
| Dependencies | GE-01–03 |
| Files | `auth/provider.py`, `auth/routes.py`, `auth/age.py` (reuse only unless necessary), new `guests/routes.py`, `guests/service.py`, `main.py`, contracts; new `test_guest_auth.py`, `test_guest_provisioning.py` |
| Approach | Implement intent cookie, CAPTCHA-bound creation, DB grant T0/T, disabled consents, same cookie protections, compensation/recovery and explicit end/logout. No provider token storage; never overwrite registered session. Register guest routes |
| Acceptance | Two independent browser cookie jars get distinct internal/provider IDs; repeat/live creation returns original T; same-key lost response recovers; failed DB grant leaves no app authorization and reconciles orphan; underage never reaches protected features |
| Required tests | Concurrent same intent; same key/different age payload; response lost after app grant; crash before subject persist recoverable via mandatory provider marker; ambiguous outcome forbids another signup for that attempt; marker spoof/multiple-match denied; provider error; forged origin/intent/CSRF; cookie flags; early end; registered CTA conflict |

**Interfaces:** `SupabaseAuth.anonymous_session(captcha_token, *, correlation_id: str)->ProviderSession`; `create_guest(intent,body,request)->SessionView`; `end_guest(request,actor)->None`; narrow SQL `find_guest_orphan_subjects(attempt_id)` / `delete_orphan_guest_identity(attempt_id)` from02. API contracts exactly as 02 §3. Token/captcha arguments must be excluded from repr/logs.

- [ ] Add failure-injection tests at every external/transaction boundary before implementing each recovery branch.
- [ ] Run auth + guest permissions together; keep `GUEST_AUTH_ENABLED=false` until lifecycle and cost tasks pass.

## Phase 2 — Lifecycle, long-running work and cost controls

### GE-05 — Fence streams, AI/tools, exports and embedding work at deadline

| Item | Task |
|---|---|
| Objective / priority / risk | Prevent late content and background resurrection; **P0 / critical** |
| Dependencies | GE-03–04 |
| Files | `ai/runtime.py`, `ai/chat_routes.py`, `ai/store.py`, `ai/memory.py`, `ai/embeddings.py`, `ai/persistence.py`, `voice/routes.py`, `users/routes.py`, new `guests/deadlines.py`; tests `test_guest_inflight.py`, `test_guest_embeddings.py`, `test_guest_exports.py` |
| Approach | Clamp content lifetimes, schedule cancellation against T, fresh checks before tools/provider dispatch/content emit/finalization, background user lifetime guard, bounded transactions; guest export/delete confirmations without password step-up |
| Acceptance | AI/voice/SSE/proposal/export call spanning T has no late private output; terminal buffered events cannot replay after T; late embed/result cannot republish; pre-T allowed data remains owned; registered cancellation/opt-in behavior unchanged |
| Required tests | Held fake provider; event-iterator barrier; slow upload/SQL; no network reader; pending job claimed before T/publish after; actual server restart with same DB; no paid call replay |

**Interfaces:** internal deadline helper consumes DB `guest_expires_at`; `run` task carries a deadline but each sensitive finalization still revalidates. No client-provided duration override in production.

- [ ] Write a stream test that pauses after authorization but before yielding final, advances past T, then asserts no final content.
- [ ] Assert no committed mutation is accepted by a final authorization evaluated after T; distinguish authorized pre-T commit/transport completion from new authorization.

### GE-06 — Complete guest hard purge and orphan reconciliation

| Item | Task |
|---|---|
| Objective / priority / risk | Delete all temporary active-store data with durable retries; **P0 / critical** |
| Dependencies | GE-02,04,05 |
| Files | New `guests/lifecycle.py`, `guests/jobs.py`; `users/lifecycle.py` (extract reusable primitives narrowly), `main.py`, `jobs/retention.py`, guarded provider helper migration; new `test_guest_cleanup.py`, `test_guest_cleanup_recovery.py` |
| Approach | Create scheduled cleanup at provisioning; owner/lease-fenced FK-aware purge from 01 inventory; provider anonymous identity deletion; remove guest user/session/consents/jobs/receipts; independent worker error isolation and lag metrics. Reconcile targeted provider orphans |
| Acceptance | Seed every allowed store, expire, purge and prove zero guest ownership references; other user's canaries unchanged; provider deletion verified; repeat is safe; failure never restores access; no silent abandonment after retries |
| Required tests | Job lease loss; DB/helper failure then retry; worker death mid-purge; failed-job alert; orphan after lost subject response; late AI/index publication; unexpected social FK data; restore of expired guest |

**Interfaces:** `async process_guest_cleanup(app)->int`; `async reconcile_guest_provisioning(app)->int`; content-free `guest_cleanup_lag_seconds`, `guest_cleanup_retry_count`, `guest_orphan_count` metrics. Cleanup runs even when entry flag off.

- [ ] Assert absent consent/events/AuthSession/DataJob/Idempotency rows, not just absent transcript text.
- [ ] Keep completion false until app and provider erasure gates both pass; no full-erasure claim about backups/services.

### GE-07 — Add shared guest admission and independent aggregate budget

| Item | Task |
|---|---|
| Objective / priority / risk | Bound farming, concurrency and paid liability durably; **P0 / high** |
| Dependencies | GE-02–04; GE-05 dispatch integration |
| Files | New `guests/limits.py`, `guests/accounting.py`; `ai/persistence.py`, `ai/accounting.py`, `voice/routes.py`, `ai/embeddings.py`, config/contracts; new `test_guest_quotas.py`, `test_guest_abuse.py`, `test_guest_budget.py` |
| Approach | PostgreSQL atomic per-trial/IP/global counters/reservations; limits from 02; uncertain-spend settlement, price configuration fail-closed, preserve registered headroom; detached daily totals survive guest purge |
| Acceptance | Simultaneous admissions cannot overshoot configured counters; replay charges once; midnight/restart/new token does not reset trial totals; purging users cannot reopen spend; voice/embed included; canonical proxy/IP normalization tested |
| Required tests | Concurrent independent DB sessions, 26th turn denial, second active run denial, 181st voice second denial, shared NAT behavior, forged forwarding header, budget exhausted/unknown price/uncertain outcome, cleanup crossing budget settlement |

**Interfaces:** `reserve_guest_operation(db,user,kind,upper_cost)->Reservation`; `settle_guest_operation(db,reservation,actual_or_uncertain)->None`; stable reservation ID on idempotent retry. Lock order documented across owner, usage and global budget rows.

- [ ] Prove global budget counts outstanding reservations before provider dispatch and remains closed when actual usage is unavailable.
- [ ] Run one-worker synthetic load with fixed configured quotas; do not increase worker count as a shortcut.

## Phase 3 — Public entry and guest interface

### GE-08 — Introduce public route boundary and product landing

| Item | Task |
|---|---|
| Objective / priority / risk | Public product explanation independent of private auth loading; **P1 / medium** |
| Dependencies | GE-02 contracts; guest CTA remains disabled until GE-04–07 accepted |
| Files | New `frontend/src/AppEntry.tsx`, `features/public/LandingPage.tsx`, `features/public/landing.css`; modify `main.tsx`, `features/real/Auth.tsx`, small RealApp entry section, `index.html`; approved synthetic screenshot assets under existing public conventions |
| Approach | Topology/copy from 03; lazy app boundary; one callback owner; preserved hash deep links; metadata/prerender only public content. Existing tokens/avatars/components |
| Acceptance | Root works without API/cookies and sends no signup request; callback/recovery and old app links still work; valid registered session can continue; CTA availability honest; 320px/desktop/keyboard/SEO content checked |
| Required tests | New `frontend/tests/e2e/landing.spec.ts`; extend `auth.spec.ts`; new `frontend/src/AppEntry.test.ts` if pure route classification extracted; fullstack legacy deep-link checks |

- [ ] Test `/auth/callback#...` is sanitized once before any rendering/telemetry.
- [ ] Capture screenshots from synthetic current UI; no invented product proof or production personal content.

### GE-09 — Guest entry, status, expiry and personal UI variants

| Item | Task |
|---|---|
| Objective / priority / risk | Complete usable guest experience without false retention or social claims; **P1 / high** |
| Dependencies | GE-04–08 |
| Files | New `features/guest/GuestEntry.tsx`, `GuestStatus.tsx`, `GuestExpired.tsx`, `useGuestLifecycle.ts`; modify `RealApp.tsx`, `Eligibility.tsx`, `AssistantGuide.tsx`, `AIData.tsx`, `Privacy.tsx`, `social/useSocialSummary.ts`, `api/client.ts` |
| Approach | Server-derived deadline/account kind, same expiry state across tabs, abort and clear state at T, active/no-network/session-error distinction; locked matching explanation; guest export/end no password; ordinary registration with no data transfer |
| Acceptance | Refresh/restart never restarts timer; open/offline tab expires; old guest IDs never restore after new trial; private caches/drafts/audio gone; five AI assistants remain accessible when authorized; no social polling/calls for guest |
| Required tests | New `frontend/tests/e2e/guest.spec.ts`, `guest-expiry.spec.ts`, `frontend/tests/fullstack/guest-journey.spec.ts`; guest deadline unit tests using existing Vitest conventions; underage/declined consent/error/retry/mobile/keyboard |

- [ ] Check day-retention/tomorrow/password UI text variants against 03 §7.
- [ ] Exercise explicit new-trial and separate signup transitions; no silent identity upgrade.

## Phase 4 — Voluntary feedback and admin

### GE-10 — Feedback storage, submission, retention and privacy separation

| Item | Task |
|---|---|
| Objective / priority / risk | Collect minimal app feedback from both account kinds; **P1 / high** |
| Dependencies | GE-02–07; retention/disclosure approval before flag enabled |
| Files | New `backend/app/modules/feedback/{models,schemas,service,routes}.py`, next migration, `main.py`, `guests/lifecycle.py`, `jobs/retention.py`, generated contracts; tests `test_feedback.py`, `test_feedback_privacy.py`, `test_feedback_retention.py` |
| Approach | Schema/API from 04, no permanent identity FK; separate expiring receipts; owner-lock idempotency/limits, plain-text validation; feedback flag default off |
| Acceptance | Rating-only works; guest expiry still enforced; duplicate/replay concurrency safe; private metadata rejected; guest purge leaves feedback with no guest link; 180-day purge works; registered deletion policy consistent |
| Required tests | Strict 1–5 integer, categories0–8/dedup, comment1000/1001 codepoints, control/HTML/SQL strings, consent notice version, expired submission barrier, guest cleanup and budget separation |

**Interfaces:** `submit_feedback(db,user,body,key)->FeedbackReceipt`; HTTP fields/endpoints in 04 §4. `app_feedback` has no user/session/provider ID or raw context URL.

### GE-11 — Admin feedback authorization, aggregates and review status

| Item | Task |
|---|---|
| Objective / priority / risk | Minimal useful internal review without exposing feedback; **P1 / high** |
| Dependencies | GE-10 |
| Files | New `feedback/admin_routes.py`, `feedback/queries.py`; `moderation/staff.py` narrow reusable-gate change; config/main/contracts; tests `test_feedback_admin.py` and existing `test_moderation_admin.py` |
| Approach | Registered admin + live role/reauth + independent flag; bounded filters/cursors; consistent spam exclusion; versioned status changes; content-free review audit |
| Acceptance | Guest/normal/moderator denied (MVP admin-only); admin revoke immediate; disabled flag404; distribution/mean/count/filter correctness; conflicts409; moderation remains unchanged |
| Required tests | Auth/CSRF/reauth; role changed between request and update; empty/filtered aggregate; multi-category counts; forged version/context; unauthorized direct URLs |

### GE-12 — Feedback form and protected dashboard UI

| Item | Task |
|---|---|
| Objective / priority / risk | Accessible collection and triage with minimal effort; **P1 / medium** |
| Dependencies | GE-09–11 |
| Files | New `frontend/src/features/feedback/FeedbackPage.tsx`, `features/real/admin/Feedback.tsx`; Shell/settings/public links; new `frontend/tests/e2e/feedback.spec.ts`, `feedback-admin.spec.ts`, `frontend/tests/fullstack/guest-feedback.spec.ts` |
| Approach | Form/copy/states from 04, native ratings/checkboxes, optional comment, no persistent draft; no automatic prompt in sensitive chat. Admin semantic table/simple rating bars, no new BI package |
| Acceptance | Rating-only submission from both kinds; correct success/retry/suppression; mobile/keyboard/200% text; no private attachment/network payload; expired draft cleared; admin hidden and API-protected |
| Required tests | No rating selected, keyboard radio group, optional categories/comment, double-click/network retry, expiry while form open, HTML displayed as text, admin empty/error/conflict, guest feedback survives purge |

## Phase 5 — Optional onboarding and release proof

### GE-13 — Validate tour candidate and implement optional replayable flow

| Item | Task |
|---|---|
| Objective / priority / risk | Contextual guidance through actual components; **P2 / medium** |
| Dependencies | GE-08–09; route/DOM targets stable |
| Files | New `frontend/src/features/onboarding/{TourController,tourSteps,useTourState}.tsx/ts` as appropriate; stable `data-tour` targets in existing screens; `package.json`/lockfile only for one justified pinned dependency; tests `frontend/tests/e2e/onboarding.spec.ts`, `frontend/src/features/onboarding/tourSteps.test.ts` |
| Approach | Prove Driver.js React19/StrictMode/mobile/keyboard/SR/reduced motion/CSP before selecting; fallback from 03 only if evidence requires. Four optional steps, adult registered intro separate; route readiness/3s bounded waits and cleanup |
| Acceptance | Skip/Back/Finish/replay work; no consent/write side effects; missing/conditional target doesn't trap; tour stops at guest expiry; draft/focus preserved; no overlay during active emotional chat |
| Required tests | Guest vs teen/adult registered step set; browser Back; missing target; navigation/resource failure; native dialog collision; reduced-motion/resize/scroll; manual NVDA/VoiceOver |

### GE-14 — Integrated QA, capacity, rollout/rollback and release decision

| Item | Task |
|---|---|
| Objective / priority / risk | Prove combined journey and preserve registered MVP; **P0 release gate / high** |
| Dependencies | GE-00–13 (tour may ship disabled if explicitly deferred) |
| Files | New `frontend/tests/fullstack/guest-experience.spec.ts`, proposed `scripts/load_guest_experience.py`; existing suites, reviewed artifacts, proxy packaging/tests, release docs and config examples |
| Approach | Full matrix from 06, synthetic 50-visitor load with configured guest run cap, restart/cleanup failure and restore rehearsal, staging Auth/CAPTCHA/provider gates under explicit approval, one worker, no production writes until release decision |
| Acceptance | No unresolved critical privacy/auth defects; capacity target measured and the audit failure explained; registered flows pass; cleanup lag/alerts proven; budget approved; exact approved image/migration/release artifacts reviewed; rollback retains expiry/cleanup |
| Required tests | All backend/static/type/unit/API/migration/contract/frontend build/E2E/fullstack/proxy checks; manual mobile/keyboard/SR/privacy copy; hosted synthetic identity cleanup; approved limited live provider smoke only with budget |

- [ ] Publish executed command/output evidence and all skips/failures; PASS only for observed scopes.
- [ ] Stop at concrete release package and explicit **go/no-go** review. Do not auto-merge, apply hosted SQL, toggle Dashboard settings or deploy.

## Execution and handoff checkpoints

GE-08 public copy/layout can be developed behind unavailable trial CTA while backend work proceeds. GE-10 can reuse registered actors before guest UI is complete, but guest acceptance requires GE-06. GE-13 deliberately follows navigation stabilization to avoid redoing selectors. No task requires a React-router migration, Redis, new AWS service, full analytics platform or guest conversion.

The audit produced this roadmap only. Implementation test files and interfaces above are **proposed new work**; do not claim they exist or passed until created and executed on the feature branch. Future handoff prompt: [08](08-claude-code-handoff.md).
