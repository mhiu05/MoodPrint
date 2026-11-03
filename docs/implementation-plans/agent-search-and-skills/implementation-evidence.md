# Implementation ledger — 2026-11-03

Scope: 00–07; inline execution in E:/MoodPrint, no commit/deploy/live providers.
Baseline branch: test/03-11-26. Preserve existing changes in AgeFields, GuestEntry,
LoginPage, landing.css, Auth and RealApp. No real .env or .gitignore edits.

Ruling: user authorizes implementation from the existing plans, superseding planning-only
restrictions and commit/worktree skill steps. This ledger retains evidence without commits.
Pre-flight: W1 → W2 → M2 → S3 share normalized options, protocol 3 and run scope.
C1 covers both grant readers; K1 global timezone remains shared, schedule owner != speaker.

## Tasks

- [x] W1 contracts/persistence/protocol
- [x] W2 Web/accounting
- [x] W3 grounded rendering/UI (offline error/reload/cancel journeys verified in the final review below)
- [x] M1 adapter
- [x] M2 jobs/lifecycle
- [x] M3 cards/reuse
- [ ] M4 rollout (worker heartbeat/deadline fake tests pass; real containers/provider/staging gate not run)
- [x] S1 registry
- [x] S2 resolver/runtime
- [x] S3 composer
- [ ] S4 journeys (target E2E pass; cohort rollout not done)
- [x] C1 grants/receipts
- [x] C2 runtime/privacy
- [x] C3 settings removal
- [ ] C4 rollback (preflight code only; cohort rollout/live drill not run)
- [x] K1 controls/controller
- [x] K2 info panel
- [x] K3 routes
- [x] K4 scheduler regression

## Evidence

Disposable harness initially failed because Docker Desktop was stopped. Started Docker hidden,
then provisioned owned `dd013fd508944053be6bd7002906d4e4`, loopback55439, PG17.10/vector0.8.2.
No existing database used. Collaboration agent used separate owned55440 and removed it.

- W1 initial citation/normalization tests RED, then 30 pure tests green; persistence route
  regression exposed misplaced protocol parameter (fixed); 40/40 targeted tests passed.
- Search adapters/registry: 18 fake tests passed; both skills load only from the closed registry.
- Root Maps jobs+accounting+usage/budget+multi-message group: 30/30 passed.
- Web/skill runtime integration: 2/2 passed with actual SDK scripted Model, separate child tokens
  and fee ledger, no journal tools or planner in the Web branch.
- Migration/source/API group: 15/15, then source+Maps API group13/13. Disposable migrations0025–27
  checked actual upgrade/RLS/no-public-grants; destructive downgrade deliberately refuses.
- Full frontend unit command `npm.cmd test`: 39 files,239 Vitest tests passed; Redocly Node test1/1.
- Ruff/mypy have been run; most recent mypy:184 modules green. Final lint rerun pending.
- Compose synthetic config validation and `bash -n deploy/aws/deploy.sh`: exit0, no deploy.
- Broad targeted backend first run116 passed/1 failed: trusted persistence fixture was missing
  new search boundary marker; corrected fixture then13/13 source/API tests green.
- Full backend fake suite (`pytest -m 'not live'`) running; do not mark complete until output.
- Browser fixture regression running in `.tmp/agent-search-e2e`; most tests green, known failures:
  exact label selectors for select controls, resize focus, Maps area label includes helper text.
  No live API/provider traffic. Earlier failed run interrupted after identifying shared causes.

## Independent review and fixes

Review details: search-review.md. Verified/reproduced issues, then fixed:
URL alternate numeric hosts; journal rendering bypass of source guard; source-backed marker on
every saved bubble; ordinary model history stops at source boundary; expired/cancelled Maps
cleanup ordering; idempotent DELETE404; late actor ref reopens cleanup; persist billing before
vendor metadata deletion. Known missing vendor run maps to missing state for cleanup recovery.
Follow-up tests for final late-start/unknown-fee recovery matrix still need broadening.

Ruling: initial public Web topic extraction uses closed canonical labels to avoid forwarding
personal statements. Unknown topics return needs_query. This narrows coverage and loses fine
subtopics; broader safe extraction remains a limitation, not a live capability claim.
Ruling: source-backed ordinary follow-ups fail closed at the context boundary. Maps results can
be reused only through reauthorized mapsSearchId; no source-free historical web paraphrase.
Ruling: four additive migrations keep old sharing preference snapshots unchanged. New required
head0028; rollout flags remainfalse in examples, explicit operator enablement after credentials,
pricing/build and worker verification. Existing AI consent semantics are preserved (see agent
collaboration-evidence.md), not replaced by a new consent policy.

## Integration notes

Root integrated composer/options/retry, citations, Maps card/reuse, per-agent settings,
owner identity, route redirects, removed Account settings entries and preserved receipts/inbox.
Subagent evidence: collaboration-evidence.md (157 prescribed;142 supplemental),
checkins-evidence.md (23 unit tests). Do not count overlapping runs as unique tests.
No commits/push/merge/live calls/hosted migrations/AWS or real .env edits.

## Handoff at user's request

Implementation stopped for handoff, not marked complete. Authoritative final snapshot:
`08-implementation-handoff.md`; continuation prompt `09-claude-code-prompt.md`.
Focused browser rerun5/5passed. Latest frontend build fails missing required sourceBacked
on constructors. Full backend fake suite interrupted at~7%,4failure markers, no final summary;
owned pytest processes terminated, disposable root DB kept for next implementer.
Broad browser154pass/6fail;5fixedandrerun, login-copy case remains. No completion claim.

## Continuation session — 2026-11-03 (Claude Code)

Same disposable PG (`dd013fd5…`, port 55439), env loaded silently from the harness `.env`;
`backend/.env` never read. Commands ran with `backend/.venv` (pinned lock env), fakes only.

Fixes (all fake-verified):
- Build: `sourceBacked` on every message constructor (self/group false; live direct bot derived
  turn-level from validated citations/cards, then reconciled from authoritative history).
- `alembic/env.py` did not import search models (`alembic check` drift); 0027 UNIQUE renamed to
  `uq_ai_maps_searches_operation_id` to match ORM naming (0027 never applied outside disposable DBs).
- Guest inventory/policy classified `ai_search_usage`/`ai_maps_searches` (detached) and the three
  new routes (maps registered-only; prompt capabilities a guest zero projection, tested).
- `check_capacity` had silently switched to whole-JSON bytes, shrinking every temporary chat;
  restored text bytes plus cards/citations bytes only when present.
- Maps worker: terminal jobs (timed_out/cancelled/failed) are no longer revived to ready/failed;
  they only reconcile billing or retry a failed abort; billed terminal jobs wait for cleanup.
- Search subset never counts child tokens that the global window has already released.
- Default protocol-2 send without options keeps the pre-search idempotency digest input.
- `safe_query` closed slots (topics, gazetteer place, time); `unsupported_topic` vs `needs_query`.
- Dead `AI_AGENT_CHECK_IN_SETTINGS_ENABLED` removed; panel gated by `features.proactive` (06.K4 ruling).
- Stale head assertions moved to 0028 (older heads still rejected; downgrade still refused).

New regressions: late ref after lease takeover; cleanup crash after run deletion + 404/missing;
terminal never revived/abort retry; account detach cleanup; attached/detached tokens, midnight,
tombstone+retention+flags off, daily cap/global concurrency; uncited-sibling page for protocol
1/2/default history, SSE replay and export; default digest compatibility; numeric-host URLs;
group fabricated places card; Web-after-Maps 20 s deadline gate; composer state cases.

Results:
- Full backend `pytest -m "not live"` run 1: 1886 passed, 14 failed, 3 skipped (all 14 fixed above
  and rerun green per file). Run 2 after fixes: **1925 passed, 1 failed, 3 skipped** (39 min, with
  Playwright running concurrently). The failure `test_guest_embeddings::test_late_embedding_cannot_
  recreate_deleted_memory` is a wall-clock guest-expiry test; rerun alone 3×: 4/4 each. Tests added
  after run 2 started (numeric URLs, 20 s gate) passed separately.
- Ruff app+tests clean; mypy 184 modules clean; OpenAPI exported, contracts regenerated.
- Frontend typecheck/build pass; `npm.cmd test` 39 files/239 Vitest + Node 1/1 (composer file now 4).
- Playwright 11 target specs: 158 passed, 2 failed. `activities` dock motion failed under load,
  3/3 alone. `ux-redesign` "first-time sign in explains…" fails because pre-existing user edits in
  `Auth.tsx`/`LoginPage.tsx` removed the visible heading/lede; user files and test left unchanged.
- Visual check of check-in panel screenshots (320/1280): no overflow. Observed: paused slot's
  select still shows "Không tạm dừng" (same as HEAD CheckInsPage); at 1280 the deep-linked
  section heading scrolls under the panel header. Not a full manual QA (no zoom/reduced-motion review).

Not done/unproven: live OpenAI/Apify, pricing/build bounds, worker heartbeat across containers,
hosted migrations 0025–0028, AWS/SSM/redeploy, cohort rollout. Flags stay false.

## Independent review and completion — 2026-11-03 (Codex)

Authoritative follow-up: [10-final-offline-review.md](10-final-offline-review.md).
Claude's report was a useful checkpoint, not evidence that every acceptance gate passed.
Independent review found and fixed additional Maps concurrency, abort, lock-order and total
deadline defects; added red→green disposable-PG/HTTP-stream regressions. Follow-up review
also closed late-ref slot restoration and cleanup-error slot reactivation. A second reviewer
found no further important issue in that final backend delta.

Fresh backend checks (disjoint file groups, no parallel DB suites):
- `final-search-backend.log`: **245 passed**, 673.96 s. Agent skills/options, search accounting,
  citations, migrations, provenance, Web, collaboration defaults, SSE v2, guest permission/schema,
  readiness. Test DB ownership marker verified, harness env loaded without printing its values.
- `final-maps-all-complete.log`: **26 passed**, 48.50 s. Maps jobs/provider/API, worker heartbeat,
  guest embeddings. Includes failed abort retaining concurrency, retry abort past TTL,
  cancellation lock-order barrier, streaming total deadline, worker I/O deadline, late ref,
  cleanup failure preserving settled quota, stale heartbeat/readiness and orderly cleanup.
- Ruff `app tests`: clean. Mypy `app`: **184 source files clean**.

Frontend final unit/build checks: **39 files / 241 Vitest tests**, Node tests **2/2**,
typecheck and production build exit 0. Logs: `.tmp/final-frontend-{unit,typecheck,build}.log`.
Focused browser acceptance: **53 passed**, 2.1 min, five specs covering skills, Web, Maps,
check-in settings and activities. Artifacts/log: `.tmp/final-search-ui-verified/` and
`.tmp/final-search-ui-verified.log`. Final 11-spec integration rerun **174 passed, 5.8 min**;
log `.tmp/final-agent-search-acceptance.log`. No remaining failure in that run.

Additional UI fixes: paused select reflects server state and can resume; quiet-hour help
opens shared settings with exact keyboard focus restoration; header is outside the scroll
body so deep links remain visible at enlarged text. Maps 404 has a safe unavailable/new-turn
recovery (does not reveal whether expiry or authorization caused it); terminal/cancelled cards
stop polling and an in-flight GET cannot overwrite cancellation.

Web fixture journeys now cover empty/timeout/rate-limit/budget/cancel, uncited fallback after
reload and normal next-turn options. These render synthetic grounded replies; provider failures
and financial behavior are verified separately by backend fakes, not by those UI fixtures.
Maps journeys cover empty/failed/timed-out/gone, offline retry of the same job, keyboard reuse
without auto-send on mobile, navigation back, reload and cancellation without new actor/chat.

Test corrections: guest late-response fake now survives local cancellation until the test
crosses the actual DB deadline. The conservative monotonic deadline may intentionally expire
before DB T by the sampling round trip; production deadlines were not weakened. Login test
now asserts the user's current accessible form rather than removed marketing copy; user's
Auth/LoginPage files were not edited.

The prior activity “motion flake” had a concrete fixture defect: removing API interception
allowed a pending unauthenticated local history GET through the dev proxy (trace: 401 then
`/login`). The fixture now mutates its state while interception stays installed. No paid
provider or remote mutation was invoked. Subsequent dock tests pass with full interception.
Mock-only Vite additionally disables API proxy via `MOODPRINT_MOCK_API_ONLY=1` from Playwright
webServer config. A Node regression exercises an unhandled API GET against a synthetic local
sentinel: red before fix (one forwarded request), green after fix (404 and zero forwarded).
Dedicated fullstack/live configs are unchanged. Mock suite uses its own server (no reuse of
an unguarded dev server). Post-guard browser acceptance activities/collaboration/proactive:
**45 passed**, 1.8min (`.tmp/final-e2e-guard.log`). These overlap the174-case run, not45 extra
unique cases. See report10 for details.
After requiring the owned server (`reuseExistingServer=false`), the manual Web provenance
smoke passes1/1 and typecheck exits0 (`.tmp/final-owned-server-smoke.log`).

Visual evidence actually inspected: check-in screenshots at 320/1280 and desktop 200% text.
Automated axe, keyboard and resize checks cover 320/390/768/1099/1100/1280. This is not a claim
of manual screen-reader/device QA or actual browser-zoom testing. Full backend ~1900-test
suite was not rerun; Claude's historical 1925-pass/1-fail run remains historical, with that
failure covered by the corrected four-test module in the fresh 26-test group.

No real `.env` edits/reads, `.gitignore` edits, SDK/dependency upgrades, AWS/SSM, hosted
migration/deploy, commit/push/merge or live provider calls. Example flags remain disabled.
