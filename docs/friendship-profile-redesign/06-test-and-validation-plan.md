# Friendship Discovery — test and validation plan

This is a plan for **later implementation**. No new tests are written or run in the planning session. Existing documentation-only checks are permitted and their results belong in 07. Do not report the scenarios below as already passing.

## 1. Existing tools and boundaries

- Vitest is installed and collects `src/**/*.test.ts`; current profile rules test is `frontend/src/features/real/social/profileRules.test.ts`. Use new `.test.ts` files only for meaningful pure state/mapping/starter rules; do not install a React testing library just for this redesign.
- Playwright and `@axe-core/playwright` already exist. Default `frontend/playwright.config.ts` explicitly enumerates fixture specs; extend registered `discovery.spec.ts`, `social.spec.ts`, `states.spec.ts` and `motion.spec.ts` instead of adding an uncollected filename. Use `--list` if collection is uncertain. Owned config avoids reusing a developer's Vite server.
- Real backend tests use pytest/pytest-asyncio with PostgreSQL fixtures. `backend/tests/conftest.py` resets schema; **never run against production/staging/shared databases**. Require the repository's local disposable DB guard and `_test` suffix. No SQLite substitute for JSONB/locks/RLS.
- `scripts/test_fullstack.py` owns synthetic FastAPI/Vite processes on 8002/5174 and calls `frontend/playwright.fullstack.config.ts`; use it for persistence, consent and multi-user action scenarios. Run sequentially with pytest if they share a database.
- Do not call live-provider configs, hosted Supabase runners, external AI, deployment commands or schema migrations for this feature's ordinary validation.

## 2. Fixture matrix

Prepare synthetic users/profiles only in test code and disposable environments:

| Fixture | Data / purpose |
| --- | --- |
| F0 | New adult registered, draft version 0, no publication, MATCH off; no inferred values/languages. |
| F1 | Valid legacy profile: interests reading/music/coffee; values respect/kindness; vi; balanced; friendship; no discovery. |
| F2 | Ten distinct taxonomy interests, legacy language-practice goal, listening or direct style, strictGoal true, two languages, nonempty activities/availability. |
| F3 | Partial draft: missing canonical minimums, null new answers; save valid, publication UI not ready. |
| F4 | Complete discovery v1 with explicit ordered featured subset; valid canonical full set. |
| F5 | Live, needs_republish, stale and withdrawn snapshots; MATCH on/off, versions intentionally different. |
| F6 | Teen (16/17), unknown-age, under16, guest, disabled/deletion-pending/restricted member. |
| F7 | Candidate with each supported exact shared reason; no shared reason; similar but unequal interest; same legacy style with different/new absent approach. |
| F8 | Bilaterally blocked/cooldown/open-room/pending-request pair; expired 15-minute ref; full invite quota. |
| F9 | Two simultaneous editor sessions, delayed/ambiguous responses and account/logout transitions. |

F7 is never rendered as a real population in the production empty state. Browser fixtures are test data, not product fallback people.

## 3. Scenario catalog

P0 means release-blocking. Every implementation task in 05 names the relevant IDs. U = Vitest pure unit; B = fixture Playwright browser; A = backend pytest/API; E = real local fullstack Playwright; M = manual inspection. All scenarios below are P0 except explicitly identified secondary animation polish in T35.

| ID | Layer / owner | Setup and action | Required assertions |
| --- | --- | --- | --- |
| T01 | B / P1-01 | Load F0, render builder at desktop and mobile. | Exact title; exactly four Q1 and three Q3 choices; eight initial interest entry choices; three main questions, no five-step wizard or forced extra main question. |
| T02 | U+B / P0-02 | Choose talk→study on a genuinely new unsaved profile; repeat on F2; save and change Q1 again. | Single selected radio; other answers retained; new unsaved canonical mapping works; saved legacy goal remains language-practice; after save Q1 is display-only; explicit goal setting is the only subsequent canonical change. |
| T03 | U+B / P1-01 | Toggle music/coffee/games, remove one, add another. | Ordered featured IDs unique; correct n/3, check state and actual labels in preview; no unrelated values reset. |
| T04 | U+B / P1-01 | With 3 featured, try fourth with pointer, Space and group child. | No replacement/extra ID/full-set mutation; exact friendly limit notice once; focus remains; removal then add succeeds. |
| T05 | U+B / P0-02 | Choose Sáng tạo→Vẽ and Thể thao→Cầu lông; choose two children in one category. | Only drawing/badminton/etc canonical IDs persist; category launchers are buttons; each selected child counts once; music deduplicates between entry and full category. |
| T06 | B / P1-01 | Open expanded picker, search Vietnamese with/without diacritics; paginate/category filter; close/Escape/reopen. | ≤8 result controls at a time; stable selected tray; no results copy and no API requests; close retains applied choices and returns focus; no nested dialogs. |
| T07 | U+A+E / P0-02/P3-01 | F2 fallback first three featured, change/clear features, save/restore/publish. | All ten full IDs/order and non-interest canonical facets survive; only explicit full-set delete removes a stored interest; public full-set disclosure remains available. |
| T08 | U+B / P0-02 | Full set at 10, attempt new featured ID; de-feature never-saved vs saved ID; reduce full set below 3. | No hidden deletion or >10 full set; tentative removal reconciles correctly; saved ID remains retained on de-feature; draft save allowed below minimum, review blocked until ≥3 full IDs. |
| T09 | U+B+A / P0-02/P3-01 | Q3 gradual→lively→activity-first on F1/F2. | One approach selected and immediately previewed; balanced/listening/direct stays unchanged; no automatic activities, invitation or personality inference. |
| T10 | B / P2-01 | Fill/change/unanswer questions, open/close compact preview and resize viewport. | Local preview always matches reducer; placeholders honest; no per-selection/drawer network or page reload; no focus loss or duplicate state; feature counter announcements concise. |
| T11 | B+A+E / P2-02 | Save partial F3, close/reload/reopen; then complete and save again. | Server draft restores exact allowed answers; next save uses returned version; no localStorage/sessionStorage/IndexedDB draft; no consent/publication changes. |
| T12 | B+E / P2-02 | Save fails once, retry; leave via save-and-leave while failed. | Dirty state and choices persist; no false success; no navigation until save success; identical uncertain retry keeps transport idempotency behavior; no double save. |
| T13 | B+A+E / P2-02/P3-01 | F0 chooses 3 questions; values/language absent; F1 complete existing profile repeats. | Missing-data review requires explicit 2–4 values and 1–2 languages; no guessed/preselected values/language; F1 skips required supplement; all public data shown before consent. |
| T14 | B+E / P0-02/P2-02 | Dirty Close, Discovery tab button and shell Link; choose continue/save/discard including save failure. | Each exit reaches same guard; safe initial focus; discard affects local edits only; saved draft/live snapshot preserved; selected tab/URL/scroll stay until decision; one destination executed. |
| T15 | B / P0-02 | Dirty browser Back then cancel, Back then save, Forward, repeated Back; reload/close; clean exit; session logout redirect. | No history loop/state loss/duplicate routes; history state retained; native unload only when dirty; no hidden save beacon; clean exit immediate; logout bypasses guard and clears private state. |
| T16 | B+A+E / P2-02/P3-01 | Save→server preview, edit answer, try old publish; expire token or change draftVersion. | Token invalidated; old publish denied by server; exact PREVIEW_CHANGED recovery; fresh preview and separate final click required; local preview never qualifies as server consent. |
| T17 | A+E / P3-01/P2-02 | MATCH off→draft save→preview→final publish; then consent withdrawn/restored. | Save/preview never enable consent; explicit final publish enables/logs existing consent; needs_republish stays hidden until deliberate publication; no premature candidates loaded. |
| T18 | B+A+E / P2-02 | Concurrent editor save at same version; stale publish version; uncertain publish timeout then reconcile. | STALE_VERSION/PREVIEW_CHANGED handled without auto-overwrite; local edits retained; exact user-approved overwrite uses latest version; no duplicate publication from ambiguous retry; complete server review shown. |
| T19 | U+B+A / P2-02 | Delayed draft/candidate response then logout/account switch/session reset. | No old-user preview/draft/candidates restored; pending handlers/guard cleared; ApiClient epoch/abort honored; no cross-user request acceptance. |
| T20 | U+A+E / P0-02/P3-01 | F1/F2 without metadata, with four/ten interests and uncommon canonical fields. | Read/save/preview/publish success as legacy; complete old facets preserved in new flow; no forced conversion/write merely from rendering; unknown taxonomy incompatibility blocks overwrite without dropping IDs. |
| T21 | A / P3-01 | Round-trip no/partial/full metadata; wrong enum/version, duplicate/unknown/non-subset featured IDs, 4 featured, 11 full. | Correct camelCase→snake_case→camelCase; 422 for invalid explicit metadata; ≤3 featured, ≤10 full; existing canonical limits unchanged. |
| T22 | A+E / P3-01 | New writer saves metadata, older writer PUT omits it and removes a full interest; explicit null case. | Omission preserves metadata and intersects featured subset; unrelated canonical full PUT semantics retained; explicit null clears extension only; no unsignaled truncation, no invalid subset published. |
| T23 | A+M / P3-01/P6-01 | Roll frontend back against expanded backend with new JSONB payloads; inspect rollback procedure. | Legacy client still reads/saves; new metadata survives omission; backend rollback floor documented; no destructive backfill or return to schema rejecting extension. |
| T24 | B+E / P2-01/P4-01 | F7 real API card/fixture, legacy and discovery-enabled peer. | Pair alias and seed, public intent or factual goal fallback, ≤3 unchanged server reasons, full disclosure; never session alias/private identity avatar or percentage. RequestCard headings/actions unchanged. |
| T25 | U+B / P4-01 | Exact music/coffee/etc reasons; only peer interest; similar interests; empty/unknown reasons; unsaved viewer draft differs. | Topic starter only with exact allowlisted server reason + peer ID; no shared claim from similarity/draft; unsupported cases use generic; correct label and no private inference. |
| T26 | U+B / P4-01 | Re-render/refetch same seed/profile versions, vary versions/seed across fixtures. | Stable same result; deterministic variants reachable; no Math.random/candidateRef dependency, clipboard side effect, AI request or auto-send. |
| T27 | B+E / P4-01 | Empty candidates vs loading, offline, no live profile and refresh failure. | Distinct statuses/actions; no fabricated member, misleading count or fallback match; initial static skeletons; stale cards disabled during refresh; errors recover without losing context. |
| T28 | A+E / P4-01/P6-01 | Send/skip/block candidate, duplicate/replayed/expired/foreign ref and invite quota. | Existing success/status/cooldown/quota/idempotency and owner checks survive; skip/block removes peer and restores logical focus; expired refs reload without auto-replaying action. |
| T29 | A+E / P4-01/P6-01 | After accepted room report interaction content, block/end then report; attempt report on a candidate without interaction. | Existing report evidence/ownership/moderation works and restricted subject disappears; candidate-only report denied/absent from UI; no regression in report-after-block/end access. |
| T30 | A+E / P3-01/P6-01 | F6/F8, strict goal both sides, shared/no language, stale 180-day and active 30-day boundaries, null last-seen before/after 2026-12-31 UTC. | Every 01 eligibility exclusion retained, registered 18+ only, current publication/consent required; ≤5 cards and locked recheck; scorer v1/v2/shadow behavior unchanged. Metadata-only change gives identical score/order/reasons. |
| T31 | A+E / P2-02/P6-01 | Change journal/mood/memory/private identity; edit/withdraw/republish profile; concurrent block/consent revocation during retrieval. | Private data cannot influence/publicly appear in profile/reasons/starter; no draft cross-user read; locked recheck suppresses revoked peer; ordinary publication edits/withdrawal do not close existing consent-valid rooms. |
| T32 | B+M / P5-01 | 320×568, 390×844, 768×1024, 1024×768, 1280×900, 1440×900, 844×390; 200% text/zoom. | Correct content-width grid, tablet collapse/mobile question flow; no page x-overflow, clipped Vietnamese or bottom-nav obstruction; sticky preview disabled if too tall; answers preserved during resize. |
| T33 | B+M / P5-01 | Tab/Shift+Tab, radio arrows, Space; all dialogs; discovery tabs; error-summary links. | Correct semantics and labels; visible focus, trap and restoration; no duplicate tabindex clone; focus never obscured; no pointer-only functionality. |
| T34 | B+M / P5-01 | axe against builder/review/expanded picker/recommendations/empty/error; screen reader + forced colors. | Zero serious/critical automated issues; meaningful legends, checked states/counter, one polite update per action, headings/dialog names; measured text/control contrast; manual WCAG checklist completed. |
| T35 | B+M / P5-01 | Reduced motion, hidden tabs, slow device and rapid toggling. | Selection remains responsive target ≤100ms; no essential info delayed by animation; no transforms/shimmer with reduced motion; GSAP cleanup has no orphaned timeline. Optional cosmetic transitions can be omitted. |
| T36 | A+B / P3-01/P6-01 | Regenerated OpenAPI/types, browser request bodies, backend min/max/errors and existing canonical test fixtures. | No generated drift/type errors; unchanged endpoint signatures except optional PublicProfile extension; no new SQL/RLS/config needed; 3/2/1 canonical publication minimums intact. |
| T37 | B+M / P1-01/P6-01 | Search rendered builder/cards/empty states and copy inventory; review diff against scope. | Approved title present; denylist below absent from product UI; source scope limited to authorized future feature; no fabricated matches, compatibility percentage or .gitignore edit. |

T37 test-input denylist only (these are forbidden UI strings, not proposed product copy): `Demo`; `Một chút về bạn, để những cuộc gặp gỡ thú vị hơn.`; `Ví dụ minh họa với dữ liệu giả định, không phải hồ sơ thật.` Do not reproduce these in any new user-facing component or fallback state.

## 4. Expected unit/API/browser ownership

| Test home | Cases / intended change |
| --- | --- |
| New `frontend/src/features/real/social/discoveryProfile.test.ts` | T02–T09, T20: pure hydration, featured/full retention, cap/minimum reconciliation, goalMode/style preservation; no snapshot-only tests mirroring markup. |
| Existing `frontend/src/features/real/social/profileRules.test.ts` | Keep canonical 3/2/1 minimum/max assertions; replace obsolete wizard-step-only assertions if STEPS is retired. |
| New `frontend/src/features/real/social/conversationStarters.test.ts` | T25/T26: exact evidence, deterministic stability, reachable variants and generic fallback. |
| Existing `frontend/tests/e2e/discovery.spec.ts`, `social.spec.ts`, `states.spec.ts`, `motion.spec.ts` | T01–T19/T24–T27/T32–T37 with mocked network failures and request counts. Use actual full taxonomy fixture for eight-choice/group tests. Preserve guest/teen locked tests. |
| Existing `backend/tests/test_profile_v2.py`, `test_social.py` | T11–T23/T36: partial metadata, omission preservation, validation, version/preview/consent and legacy round trips. |
| Existing `backend/tests/test_matching_compatibility.py`, `test_matching_privacy.py`, `test_matching_retrieval_v2.py`, `test_scoring_v2.py`, `test_ranking.py`, `test_explain.py` | T25/T30/T31: metadata invariance and matching/privacy regressions without modifying policy to make tests easier. |
| Existing `backend/tests/test_pair_alias.py`, `test_privacy_lifecycle.py`, `test_enforcement.py`, `test_moderation_admin.py` | Pair identity, publication/consent difference, restriction, reporting and lifecycle regressions. |
| Existing `frontend/tests/fullstack/matching-v2.spec.ts`, `local-mvp.spec.ts`, `moderation.spec.ts`, `responsive.spec.ts` | T07/T11–T23/T24/T27–T32 using real API/DB; ensure synthetic helper input types accept optional discovery. |

## 5. Future execution commands

Do not execute this section during planning. Use existing installed project environments; dependency installation needs separate scope. On Windows use npm.cmd/npx.cmd if PowerShell execution policy requires it. Commands below are separate steps, not a shell command chain.

From `frontend/`:

```powershell
npm.cmd run test -- src/features/real/social/discoveryProfile.test.ts src/features/real/social/profileRules.test.ts src/features/real/social/conversationStarters.test.ts
npm.cmd run typecheck
npx.cmd playwright test --config playwright.owned.config.ts discovery.spec.ts social.spec.ts states.spec.ts motion.spec.ts --reporter=list
npm.cmd test
npm.cmd run build
```

From repo root, after implementing DTO changes, regenerate contracts with `python scripts/export_openapi.py` in the existing backend Python environment, then from frontend `npm.cmd run contracts:generate`. Review the generated files and run typecheck again. These are intentional source writes during implementation only.

From `backend/`, with the existing project Python environment activated and a guarded local disposable `TEST_DATABASE_URL` already set (never echo a credential-bearing URL):

```powershell
python -m pytest tests/test_profile_v2.py tests/test_social.py tests/test_matching_compatibility.py tests/test_matching_privacy.py tests/test_matching_retrieval_v2.py tests/test_scoring_v2.py tests/test_ranking.py tests/test_explain.py tests/test_pair_alias.py tests/test_privacy_lifecycle.py tests/test_enforcement.py tests/test_moderation_admin.py
python ../scripts/test_fullstack.py matching-v2.spec.ts local-mvp.spec.ts moderation.spec.ts responsive.spec.ts
```

Repeat only the fullstack matching scenario for `E2E_MATCHING_SCORER=v2`; retain the default v1 run as well. Restore any session-scoped test environment setting after the run. Shadow invariance belongs in backend parametrized tests; do not change application config. Ports must be free; runner must only stop processes it owns. Do not run pytest concurrently on the same resettable DB.

From repo root, read-only documentation validation:

```powershell
python scripts/check_docs.py
git diff --check
git status --short
```

No nonexistent `npm run lint` requirement: frontend manifest does not define it. Full backend/static suites may be added to the final release verification if changed logic warrants them; do not repeatedly rerun unrelated suites once their risk is resolved. Never update visual baselines merely to hide a failure.

## 6. End-to-end journey scripts

1. **New adult:** start without consent/publication → Q1/music+coffee+reading/Q3 → local preview → missing-data review → explicit values/language → server review → final publish → real suggestion/empty → reload restores draft/current publication. Prove no publication before final click.
2. **Returning legacy member:** F2 ten interests/strictGoal/language-practice/direct → choose new display intention/approach → change featured subset → save/reload → review all old public facets → update publication → room still open. Full set and canonical goal/style survive.
3. **Safe recovery:** edit on phone → open preview → Back cancel → save-and-leave network failure → retry success → return draft → concurrent editor conflict → review fresh snapshot/token → expiry → explicit fresh review and publish.
4. **Real pair lifecycle:** two eligible public profiles → grounded recommendation → invite/accept → chat → block/report → subject restriction excludes future discovery. Non-interacted candidate remains blockable but cannot be reported through an invented unsupported path.
5. **Privacy boundary:** teen/guest/deletion-pending/restricted user cannot discover or publish; foreign draft/reference denied; modify private journal/AI memory and verify public snapshot/reasons unchanged; revoke consent during candidate retrieval and ensure final recheck excludes the peer.

## 7. Evidence and release criteria

### Requirement traceability

| Requirement | Owning implementation tasks | Validation IDs |
| --- | --- | --- |
| FR01 title/exclusions | P1-01, P4-01, P6-01 | T01, T24, T27, T37 |
| FR02 intention | P0-02, P1-01 | T02 |
| FR03 compact choices | P0-02, P1-01 | T03, T05 |
| FR04 fourth limit | P0-02, P1-01 | T04, T08 |
| FR05 secondary expansion | P1-01 | T05, T06 |
| FR06 retained full set | P0-02, P3-01 | T07, T08, T20–T22 |
| FR07 connection approach | P0-02, P1-01, P3-01 | T09, T21 |
| FR08 local preview | P2-01 | T10, T19, T31 |
| FR09 responsive layout | P2-01, P5-01 | T10, T32–T35 |
| FR10 durable private draft | P2-02, P3-01 | T11, T12, T18 |
| FR11 navigation | P0-02, P2-02 | T14, T15, T19 |
| FR12 publication | P2-02, P3-01 | T16–T18, T31 |
| FR13 canonical minimums | P2-02, P3-01 | T08, T13, T21, T36 |
| FR14 truthful live/draft states | P2-02 | T11, T13, T16, T17, T31 |
| FR15 recommendation content | P2-01, P4-01 | T24–T27 |
| FR16 actions/safety | P4-01, P6-01 | T28, T29, T31 |
| FR17 empty/error/expired | P2-02, P4-01 | T12, T16, T18, T27, T28 |
| FR18 API compatibility | P3-01, P6-01 | T20–T23, T36 |
| FR19 matching invariance | P0-02, P3-01, P6-01 | T02, T09, T30, T31 |
| NFR01–02 accessibility/reflow | P5-01 | T32–T35 |
| NFR03 performance | P2-01, P4-01, P5-01 | T10, T26, T35 |
| NFR04–05 reliability/maintenance | P0-02, P2-02, P3-01, P6-01 | T11–T23, T36 + source review |
| NFR06 Vietnamese | P1-01, P4-01, P5-01 | T01, T25, T32, T34, T37 + content review |
| PRE01/03/05/07 public-data boundary | P2-01, P2-02, P4-01, P6-01 | T07, T11, T13, T19, T24–T26, T31 |
| PRE02 explicit consent | P2-02, P3-01 | T16–T18 |
| PRE04/06 server access/eligibility | P3-01, P6-01 | T28–T31, T36 + ACL/source review |

Keep a per-ID result table: command/environment, test name, pass/fail/skip, assertion evidence, screenshot/manual notes and unresolved defect. Record requirements FR01–FR19/NFR/PRE mapping to IDs; all requirements have coverage in this catalog, with manual usability metrics distinguished from automated checks.

Release-blocking: any privacy/consent/access regression; silent old-data loss; wrong canonical goal/style mutation; invalid publication despite minimums; unknown API/DTO rollback compatibility; broken Back/Forward/save-and-leave; fabricated matches/explanations; keyboard blockage, obscured primary action or serious/critical a11y defects. Lack of an accessible local test DB is **unverified integration**, not a passing release gate.

Capture only synthetic profiles. No real journal/chat/account data in test artifacts. Unit/API mocks prove their own layer; only real local fullstack proves persistence and pair lifecycle. No production or hosted Supabase validation was performed in the planning session.
