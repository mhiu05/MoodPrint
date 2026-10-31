# Friendship Discovery Implementation Plan

> For agentic workers: read documents 01–07 before implementation. Execute task by task using an applicable execution-plan skill; checkbox steps are tracking for a **future authorized implementation session**. This session writes documentation only. No commit, push, PR or deployment is authorized by this plan.

**Goal:** deliver the approved three-question friendship builder, truthful live preview and useful real recommendation cards while preserving existing matching/privacy contracts.

**Architecture:** one reducer in the existing social feature, one shared public-profile renderer, optional validated metadata in the existing PublicProfile JSONB payload. Keep profile endpoints, canonical taxonomy, publication/version/consent protocol and configured scorer.

**Tech stack:** existing React 19/Vite/TypeScript/custom CSS; FastAPI/Pydantic/SQLAlchemy; Supabase PostgreSQL via backend; Vitest, pytest, Playwright/axe. Retain existing shared Dialog GSAP; no new dependency.

**Spec:** [03 UX/UI](03-ux-ui-specification.md), [04 technical](04-technical-specification.md); requirement IDs in [02 PRD](02-product-requirements.md), test IDs in [06 validation](06-test-and-validation-plan.md).

## Global constraints

- Expected branch `test/local-2026-10-30`; verify before editing. Never switch/reset/rebase user work without authorization.
- Preserve pre-existing `RealApp.tsx` and `journal.css` edits. Do not edit `.gitignore`.
- Main title `Tìm một người bạn hợp gu 🌷`; eight initial entries; featured maximum 3; stored-interest maximum 10.
- Preserve canonical publication minimums: interests 3, values 2, languages 1; existing maximums unchanged.
- Friendship stays registered/adult 18+, respecting every existing filter/quota/block/version check.
- No new endpoint, SQL migration, RLS change, direct Supabase browser access, private identity publication, AI/journal/memory inference or scorer-setting change.
- Explicit server save → preview → separate final publish; local preview has no network; never implicitly enable MATCH.
- Only run integration/E2E tests in guarded local disposable environments. No hosted data mutation or paid model calls.
- No commit, push, merge, PR creation or deploy without separate user authorization. Later implementers must not treat roadmap checkbox completion as deployment permission.

## File inventory for later changes

Existing target files: `frontend/src/features/real/social/{Discovery.tsx,ProfileEditor.tsx,CandidateCard.tsx,RequestCard.tsx,TagPicker.tsx,profileRules.ts,social.css}`; `frontend/src/features/real/social/profileRules.test.ts`; existing browser specs; `backend/app/modules/social/{schemas.py,service.py,routes.py}`; generated `backend/openapi.json`, `frontend/src/api/generated/schema.d.ts`; existing backend tests.

Proposed new files, not existing facts: `frontend/src/features/real/social/{discoveryProfile.ts,discoveryProfile.test.ts,FriendshipQuestions.tsx,InterestPickerDialog.tsx,PublicProfileCard.tsx,ProfilePublishReview.tsx,useProfileNavigationGuard.ts,conversationStarters.ts,conversationStarters.test.ts}`. Responsibility/signatures are in 04. Add only modules that earn their boundary; do not introduce empty scaffolding or a second Profile model.

## Review focus

1. Legacy 4–10-interest profiles, duplicate-category child choices, and zero-feature fallback preserve full data (T05–T08, T20).
2. Older cached writers and incompatible backend rollback do not erase metadata or make new JSONB rows unreadable (T21–T23).
3. A saved draft, stale token, ambiguous write and browser Back/Forward cannot accidentally publish or lose unsaved choices (T11–T18).
4. Display intent/approach never silently rewrite legacy goal/style or fabricate common-ground claims (T02, T09, T24–T27).
5. Navigation/session changes and candidate rechecks cannot reveal private data or another account's state (T15, T19, T28–T31).

## Phase 0 — Preparation and compatibility

### P0-01 — Lock baseline and contract evidence

- **Priority / complexity:** P0 / S.
- **Objective:** establish exact branch/worktree baseline and legacy fixtures before behavior changes.
- **Current relevant files:** 01 audit paths, `backend/tests/social_helpers.py`, `frontend/tests/e2e/discovery.spec.ts`, `backend/app/core/config.py`, `frontend/src/features/real/journal/useJournalGuard.tsx`.
- **Likely changes:** future implementation evidence notes under this docs directory; test fixtures in existing social/profile tests as needed. No configuration or scorer edit.
- **Required changes:** baseline absent/partial/new metadata, ten interests, language-practice goal, direct/listening styles, strictGoal and all publication states; confirm actual locally configured scorer without reading/printing secrets. Review guard behavior and cached-writer compatibility.
- **Dependencies:** none.
- **Steps:**
  - [ ] Record branch, status and unrelated dirty files; read 01–07 and relevant source.
  - [ ] Add contract fixtures/assertions for old and proposed metadata shapes to tests that will own the change; confirm the new-contract assertions fail against old schema, while legacy assertions pass.
  - [ ] Record canonical invariants, expected API generation commands and rollback floor in implementation evidence.
- **Acceptance:** no unexplained scope/branch drift; every new metadata field and mandatory supplemental field is traceable to 03/04; scorer mode is not changed.
- **Tests:** T20–T23, T30, T37; baseline tests scoped by 06.
- **Risks:** old fixtures may encode the obsolete wizard; distinguish test structure from business rules.

### P0-02 — Prove lossless mapping and navigation boundary

- **Priority / complexity:** P0 / L.
- **Objective:** resolve the highest regression risks before wiring UI.
- **Current files:** `profileRules.ts`, `ProfileEditor.tsx`, `Discovery.tsx`, journal `useJournalGuard.tsx`, existing social/discovery browser tests.
- **Likely changes:** new `discoveryProfile.ts`/`.test.ts`, new `useProfileNavigationGuard.ts`, `Discovery.tsx`; registered discovery browser spec. Keep existing UI until functions/tests are ready.
- **Required changes:** implement pure hydration/reconciliation/goalMode functions with 04 signatures; profile-scoped navigation adapter using existing HashRouter interception pattern. Preserve history state and pending destination, add save-and-leave contract. No router migration.
- **Dependencies:** P0-01; final generated-type wiring waits on P3-01. Initial pure tests can use the documented contract via a temporary test-local extension type, removed after generation.
- **Steps:**
  - [ ] Add failing T02/T05–T08 unit cases for full-set preservation, three-feature cap, concrete group IDs, goal preservation and tentative additions.
  - [ ] Implement hydrateEditor/reduceEditor/toDraftProfile/validateReview; run those unit cases.
  - [ ] Add failing browser tests for cancel/save/discard navigation, Back then Forward, repeated Back and session expiry; implement the scoped guard and run them.
- **Acceptance:** no full-set truncation; native history works without loops, lost router state or duplicate save; legacy goal/style are stable.
- **Tests:** T02, T05–T09, T14, T15, T19, T20.
- **Risks:** history interception is subtle. If a reliable scoped adapter is not achieved, report a blocking design issue before broad routing changes; do not ship with an unload-only guard.

**Definition of done:** branch/baseline documented; pure compatibility rules and guarded navigation demonstrated by focused future tests; no unresolved decision about preserving canonical fields.

## Phase 1 — Friendship profile UI redesign

### P1-01 — Render the three-question builder and bounded picker

- **Priority / complexity:** P0 / L.
- **Objective:** replace survey presentation with exact approved choices.
- **Current files:** ProfileEditor, TagPicker, profileRules, social.css, taxonomy_v2.json (read-only source).
- **Likely changes:** ProfileEditor, profileRules, social.css; new FriendshipQuestions and InterestPickerDialog; existing discovery E2E spec. Keep TagPicker reusable for supplemental facets instead of changing every consumer.
- **Required changes:** Q1/Q3 native radios; six direct-interest checkboxes with hidden glyphs; two category launchers; selected tray/counter; exact fourth-attempt feedback; local search, one category, max eight results/page, explicit full-set management.
- **Dependencies:** P0-02. Can develop pure rendering independently of new API wiring; real writes require P3-01.
- **Steps:**
  - [ ] Add failing browser assertions for exact choices, Q1/Q3 replacement and category resolution, counter/limit and keyboard operation.
  - [ ] Replace STEPS-based five-screen presentation with three-question controls using the reducer actions.
  - [ ] Implement bounded shared picker and full-set deletion labels; apply scoped token styles.
  - [ ] Run registered discovery browser scenarios and unit mapping tests.
- **Acceptance:** three main questions only, correct chips/copy, no lost unrelated answer, no checkbox square visible, no fictional category IDs, no full-taxonomy wall on entry.
- **Tests:** T01–T10, T32, T35, T37.
- **Risks:** group button mistaken for a selected interest; nested modal; old checkbox limits accidentally reused as featured-limit semantics.

**Definition of done:** all approved choices, local keyboard/touch interactions and bounded expansion are reviewable with canonical IDs; legacy data remains intact.

## Phase 2 — Live profile preview and state management

### P2-01 — Share public-card presentation and local preview

- **Priority / complexity:** P0 / M.
- **Objective:** immediate truthful feedback from one state owner.
- **Current files:** ProfileEditor, CandidateCard (PeerCard/SeedAvatar), RequestCard, social.css, UI.tsx.
- **Likely changes:** new PublicProfileCard; refactor CandidateCard exports/wrapper and RequestCard consumer only as needed; ProfileEditor and discoveryProfile view model.
- **Required changes:** owner-local vs owner-reviewed vs peer display variants; empty sections; complete public-data disclosure; pair-alias explanation; sticky preview measured against viewport; one polite announcement.
- **Dependencies:** P1-01.
- **Steps:**
  - [ ] Add failing browser tests that count selection-triggered requests and assert preview sections/full disclosure without leaking account identity.
  - [ ] Extract pure card renderer and seed visual without circular imports; keep request-card heading/actions intact.
  - [ ] Derive local preview in render and add accessible tablet/mobile preview Dialog.
  - [ ] Run preview, request-card and alias regression scenarios.
- **Acceptance:** correct next-commit preview, zero selection-triggered requests, no stale copied state or private content, complete public-field disclosure reachable.
- **Tests:** T10, T19, T20, T24, T31–T35.
- **Risks:** public preview falsely hiding unfeatured stored fields; old request-card consumer changing unexpectedly.

### P2-02 — Save, review and publish state machine

- **Priority / complexity:** P0 / L.
- **Objective:** durable explicit drafts and deliberate publication with reliable recovery.
- **Current files:** ProfileEditor save/preview/publish, Discovery resource callbacks, api/client.ts (reuse), UI Dialog.
- **Likely changes:** ProfileEditor, Discovery, new ProfilePublishReview, navigation hook; discovery E2E scenarios and fullstack matching spec.
- **Required changes:** newest version ownership, operation freezing/revision, dirty snapshot, partial drafts, missing-data supplement, exact returned server review, consent copy, conflicts and uncertain-write reconciliation. Wire guard registration and existing session reset.
- **Dependencies:** P2-01 and P3-01 before real integration. Build stage UI/tests before new API rollout, then wire generated types.
- **Steps:**
  - [ ] Add failing scenarios for partial save/restore, supplemental minimums, stale versions/digest, save-and-leave failure and old live snapshot preservation.
  - [ ] Implement review-preparation/ready plus explicit save→preview→final publish orchestration; no write effects on selection.
  - [ ] Connect all exit paths and session cancellation; add authoritative error recovery.
  - [ ] Run scoped unit/browser/fullstack consent/version cases.
- **Acceptance:** no implicit publication or consent, no unsaved-loss on guarded exits, original live snapshot remains until final confirmation; old rooms/requests remain valid after normal update.
- **Tests:** T11–T23, T28–T31.
- **Risks:** stale prop expectedVersion, accidental resubmit after conflict, ambiguous publish outcomes, late response after logout.

**Definition of done:** single-source live preview and explicit durable state machine satisfy draft, version, consent, public-disclosure and navigation scenarios.

## Phase 3 — Backend/database integration, only if necessary

### P3-01 — Add optional metadata and preserve older writers

- **Priority / complexity:** P0 / M.
- **Objective:** persist approved intent/approach/featured data without altering matching policy.
- **Current files:** backend social schemas.py/service.py/routes.py; models.py (read); contracts.py (read); profile/social tests; scripts/export_openapi.py.
- **Likely changes:** social schemas.py, scoped payload/save handling in service.py/routes.py, backend/openapi.json, generated schema.d.ts; existing test_profile_v2.py/test_matching_compatibility.py/test_matching_privacy.py. No migration/model/index/RLS/config change expected.
- **Required changes:** optional typed FriendshipDiscovery v1; strict enum/ID/subset validation; omitted-metadata preservation/intersection; legacy full PUT semantics otherwise unchanged; no new required canonical facets or altered minimums.
- **Dependencies:** P0-01/P0-02; implement before connecting new frontend writes. Phase numbering is organizational, not a reason to deploy UI before its API.
- **Steps:**
  - [ ] Add failing schema/API round-trip/omission/explicit-null/invalid-subset tests and canonical scorer-invariance cases.
  - [ ] Implement additive DTO and validated payload construction inside existing transaction/receipt path.
  - [ ] Run affected pytest cases against a guarded local disposable DB; verify no new metadata enters scorer inputs semantically.
  - [ ] Run `python scripts/export_openapi.py` at repo root; from frontend run `npm run contracts:generate` and typecheck. Review generated diff.
- **Acceptance:** old/no/partial/complete metadata all round-trip correctly; omitted extension is preserved; explicit invalid input fails; all existing filters and minima remain. Stored JSONB is snake_case and JSON wire camelCase.
- **Tests:** T13, T16–T23, T28–T31, T36.
- **Risks:** old backend rejects stored extension on rollback; oldest clients omit metadata; accidental nested JSONB mutation not persisted.

**Definition of done:** additive API contract is verified and generated, with legacy and rollback-floor evidence. Database phase is explicitly **no-op for SQL** unless new concrete evidence justifies a separately reviewed change.

## Phase 4 — Friend recommendation card redesign

### P4-01 — Render grounded recommendations and template starters

- **Priority / complexity:** P0 / M.
- **Objective:** show real public context, trustworthy common ground and a useful opener.
- **Current files:** CandidateCard, Discovery, RequestCard, backend social schemas/describe (read), matching/explain.py (read).
- **Likely changes:** CandidateCard, Discovery, PublicProfileCard, social.css; new conversationStarters.ts/.test.ts; existing social/discovery/fullstack matching specs. No scoring/explain behavior changes.
- **Required changes:** pair alias/seed header; public intention or canonical fallback; existing ≤3 reasons; exact starter allowlist/hash/variants; public-data details; real empty state; preserve invite/skip/block/report pathways and expired-ref recovery.
- **Dependencies:** P2-01/P3-01; can unit-test templates earlier.
- **Steps:**
  - [ ] Add failing tests for exact reason grounding, absent reasons, legacy profile fallback, stability/variants and unsupported claims.
  - [ ] Implement pure selectConversationStarter and card layout, retaining server order and actions.
  - [ ] Add empty/error/loading/expired/sent states and focus recovery; run social lifecycle and report regressions.
- **Acceptance:** no invented members or compatibility number; no per-load AI request; all template topics proven by server reason plus candidate ID; same allowed action semantics and chat reporting remain.
- **Tests:** T24–T31, T34, T37.
- **Risks:** deriving shared claims from unsaved viewer state; parsing arbitrary reason substrings; candidate-only report button unsupported by API.

**Definition of done:** real candidates show factual reasons/starters and all empty/safety/action states work without matching-policy changes.

## Phase 5 — Responsive polish, accessibility and animation

### P5-01 — Finish structural responsiveness and accessibility

- **Priority / complexity:** P0 / M.
- **Objective:** equal function across phone/tablet/desktop and assistive input.
- **Current files:** social.css, tokens.css (reuse), App.module.css/me2we.css (read), UI Dialog, existing responsive/motion/discovery specs.
- **Likely changes:** social.css and new feature components; minimal scoped Discovery class only. No global token or AI chat palette replacement.
- **Required changes:** available-width grid, fixed rem hierarchy, mobile question navigation and preview, safe-area/no-sticky-footer behavior, 44px targets, contrast/focus, full keyboard and screen-reader feedback, reduced-motion CSS.
- **Dependencies:** P1-01/P2-02/P4-01.
- **Steps:**
  - [ ] Add failing 320/390/768/1024/1280/1440 width, short-height and zoom scenarios; axe scan target surface.
  - [ ] Implement precise 03 layout/states and the minimal CSS transitions; retain only shared Dialog GSAP behavior.
  - [ ] Manually inspect screenshots, keyboard paths, forced colors, reduced motion and mobile navigation clearance; fix defects in scope.
- **Acceptance:** no page overflow/obscured focus/duplicate preview announcements; 03 measurements and accessibility behaviors validated; no animation delay before content/actions.
- **Tests:** T32–T35 and T01–T10 keyboard variants.
- **Risks:** viewport-only layout produces narrow preview behind rail; double safe-area padding; hidden native inputs lose focus semantics.

**Definition of done:** device matrix and manual accessibility review have recorded evidence; no severe/critical axe issue, all functionality usable without motion or pointer.

## Phase 6 — Testing, regression checks and release readiness

### P6-01 — Complete cross-layer verification and review

- **Priority / complexity:** P0 / L.
- **Objective:** prove acceptance and document remaining deployment assumptions.
- **Current files:** existing Vitest, pytest and Playwright configs/specs listed in 01/06; scripts/check_docs.py, test_fullstack.py; all changed files.
- **Likely changes:** existing test suites plus focused new pure-module tests; implementation verification notes in docs. No infrastructure change is needed to run current suites.
- **Required changes:** requirement→test evidence matrix, generated contract check, old/new writer paths, v1/v2/shadow invariance, consent/privacy/race regressions, matching-empty and report lifecycle, fresh code/diff review, backend-first rollout/rollback notes.
- **Dependencies:** all prior tasks.
- **Steps:**
  - [ ] Run focused unit/API/browser suites first; fix failures, then required broader type/build/regression checks in 06.
  - [ ] Run real local fullstack E2E with disposable DB; record skipped tests as unverified rather than passed.
  - [ ] Review changed code against 02 FR01–FR19, NFR/PRE and 03/04; inspect source diff for private-data access or scope creep.
  - [ ] Record commands/outcomes, screenshots, acceptance evidence, known limits and reviewer findings; resolve release-blocking findings.
- **Acceptance:** all must-have test IDs and requirement acceptance criteria have fresh evidence; no unintended source/config/data changes; backend compatibility floor and rollout order documented. No commit/PR/deploy is performed without explicit authorization.
- **Tests:** T01–T37; command sets in 06.
- **Risks:** all mocked tests pass while backend policy fails; locally skipped PostgreSQL cases mistaken for coverage; pre-existing unrelated failures hidden.

**Definition of done:** complete reviewed implementation report with passing required local checks or explicit blockers. Implementation readiness does not imply production deployment approval.

## Recommended dependency order

`P0-01 → P0-02 → P3-01 → P1-01 → P2-01 → P2-02 → P4-01 → P5-01 → P6-01`.

Pure UI/template work may be prepared before API completion, but connect/ship new writers only after the additive API. P0 issues, privacy/consent failures and incompatible legacy round trips are release blockers; visual nice-to-haves never delay fixing those.
