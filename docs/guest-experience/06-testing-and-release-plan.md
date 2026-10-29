# Testing evidence and release plan

Audit baseline: `984753389aa8bd4b3112b19a8beceb1e538fd659`, 2026-10-28 Asia/Bangkok. **Existing checks below were actually executed. Proposed guest/landing/tour/app-feedback tests do not exist yet and were not run.** No application source was changed.

## 1. Executed audit baseline

| Scope | Command actually executed | Observed outcome / coverage |
|---|---|---|
| Repository | `git status --short`; `git branch --show-current`; `git log -1 --format="%H %cI %s"`; `git ls-remote origin refs/heads/main` | Initial tree clean; local `main` and remote main both `984753389aa8bd4b3112b19a8beceb1e538fd659` |
| Backend lint | In `backend`: `uv run --locked ruff check app tests evals alembic` | **PASS**, all checks passed |
| Backend typing | `uv run --locked mypy app` | **PASS**, 89 source files |
| Backend unit/API/PostgreSQL | Disposable URL set, then `uv run --locked pytest -q` | **PASS**, **642 passed in 479.82s**; includes real PostgreSQL ownership/auth/lifecycle/social/AI/memory tests, synthetic providers |
| Frontend types | In `frontend`: `npm.cmd run typecheck` | **PASS** |
| Frontend units | `npm.cmd test` | **PASS**, **13 files / 73 tests** |
| Frontend build | `npm.cmd run build` | **PASS**, Vite 7.3.7 built. Existing warning: main JS 528.02kB minified / 169.55kB gzip exceeds 500kB warning threshold. Do not hide warning; lazy public/app boundary should be measured |
| Alembic | Disposable migration URL and empty `DATABASE_URL`, then `uv run --locked alembic upgrade head`; `uv run --locked alembic current`; `uv run --locked alembic check` | **PASS**, `0015_context_privacy (head)`; no new upgrade operations detected |
| Browser fixtures | `playwright.cmd test --config playwright.owned.config.ts auth.spec.ts real.spec.ts admin.spec.ts states.spec.ts --reporter=list --output "$env:TEMP/moodprint-guest-audit-e2e"` | **PASS**, **44 passed in 53.3s**. Synthetic intercepted APIs; includes mobile/desktop cases, login/recovery, consent/privacy, AI output/voice denial, admin and error/empty states. Does not prove hosted Auth |
| Synthetic fullstack | Separate DB; in `backend`: `uv run --locked python ../scripts/test_fullstack.py --reporter=list --output "$env:TEMP/moodprint-guest-audit-fullstack"` | **PASS**, **28 passed in 4.4m**. Real HTTP/FastAPI/PostgreSQL + fake SDK model, registered AI/history/memory, matching/messages/activities, moderation and responsive/axe cases |
| 50-user load, first run | `uv run --locked python ../scripts/load_chat_memory.py --workers 1 --users 50 --port 8017 --output "$env:TEMP/moodprint-guest-audit-load-50.json"` | **FAIL**, `scripts/load_chat_memory.py:317`, `AssertionError: SSE missing completed status`. Owned synthetic server log recorded `TimeoutError`, `AI_RUN_FAILED`. Ran while fullstack workload was also active. No final PASS JSON produced |
| 50-user load, isolated rerun | Same command/URL/worker/user/port with output `moodprint-guest-audit-load-50-isolated.json`, after fullstack ended | **PASS**, 50 AI completions, 130 durable messages; details below. Environment contention is a hypothesis for first failure, not an established root cause. Both outcomes retained |
| Reviewed SQL integrity | `python scripts/check_reviewed_artifacts.py` | **PASS**, 9 pinned approvals, 9 consumed by scripts. No SQL was applied remotely |
| Deployment poller units | `uv run --project backend --locked python -m unittest discover -s deploy/aws/tests -v` | **PARTIAL/blocked on Windows**: 2 release-gate tests passed; poller module import failed because `fcntl` is unavailable. No AWS call. Linux CI rerun required; no claim all deployment checks passed |
| Documentation baseline | `python scripts/check_docs.py` before new files | **PASS**, 32 Markdown files, 208 local links, 100 API operations, 48 settings, 38 ORM tables. Final document verification is appended below |
| Live public browser, read-only | Agent Browser named session `moodprint-guest-audit-20261028`: open root, snapshot, desktop/mobile screenshots, `a11y --json`, `errors`, close | Login screen observed; desktop and 390×844 captures inspected; axe4.12.1 reports **0 violations** at both sizes. No browser errors printed. No auth/AI/submission action performed |
| Live routing/cache, GET only | Python `urllib.request.urlopen` for `/`, `/auth/callback`, `/api/v1/health/live`, `/api/v1/health/ready` | All **200**, all `Cache-Control: no-store`; no CSP response header observed. Live build SHA not established |
| Hosted database, catalog only | Supabase MCP SELECTs for revision, relation RLS/SELECT privileges, policy groups, helper privileges, runtime role attributes | Revision0015; all39 relations RLS-enabled; anon/authenticated SELECT denied; runtime policies 38 ALL +1 SELECT, true predicates; helpers private and runtime-callable; runtime not superuser/BYPASSRLS. No personal/Auth records read |
| External compatibility research | Supabase docs/MCP search/changelog, official Auth source, OpenAI Docs search+fetch, Driver docs; `npm.cmd view` for tour candidates | Sources in 02/03. Driver1.10.2 MIT; Joyride3.2.0/React19 peer; Reactour3.8.0/React19 peer. No dependencies installed. Some documentation URLs timed out/unavailable; no guarantees inferred from them |

Disposable environment created only for this audit:

```powershell
docker run --detach --rm --name moodprint-guest-audit-db-20261028 --publish 127.0.0.1:16432:5432 --env POSTGRES_DB=moodprint_guest_audit_test --env POSTGRES_USER=postgres --env POSTGRES_PASSWORD=moodprint-local-only pgvector/pgvector:0.8.2-pg17
docker exec moodprint-guest-audit-db-20261028 createdb -U postgres moodprint_guest_migration_test
docker exec moodprint-guest-audit-db-20261028 createdb -U postgres moodprint_guest_load_test
docker exec moodprint-guest-audit-db-20261028 createdb -U postgres moodprint_guest_fullstack_test
```

The password above is the public synthetic local-only fixture value, never a credential from `.env`. Separate DBs prevent concurrent fixture reset collisions. Test URLs used this loopback host/port and respective `_test` database; production `DATABASE_URL` was never substituted for `TEST_DATABASE_URL`. Backend tests explicitly clear external provider configuration. Logs/load output and direct audit screenshots are in OS temp. Existing fullstack specs additionally wrote54 screenshots to hardcoded repository paths despite Playwright's output override; those generated-only folders were verified and moved to OS temp afterward, leaving only the nine requested/planning Markdown files untracked. Nothing was committed or copied to production.

Observed isolated load summary:

| Measure | Value |
|---|---:|
| Users / backend workers | 50 / 1 |
| Non-AI endpoint calls / p95 / max | 941 / 1407.48ms / 2998.82ms |
| AI completions / p95 / max | 50 / 7631.29ms / 7738.30ms |
| Peak sampled admitted runs | 48 |
| Peak sampled PostgreSQL connections / checked-out pool sum | 12 / 10 |
| Peak sampled worker RSS | 179,998,720 bytes |
| Peak embedding backlog | 150 |

This tests the existing registered synthetic workload, fake latency, fixture pool5+5 and one Windows host. It does not test guest creation, guest cleanup, real provider cost/latency, sustained public traffic or a production EC2 size. The second run did not include `--crash-kill`; do not claim a process-kill load scenario was observed. Existing unit/fullstack recovery coverage is separate.

## 2. Future test infrastructure

Use real disposable PostgreSQL/pgvector for constraints, locks, helper privileges, deletion and quotas. Update synthetic `auth.users`/`auth.sessions` fixtures with anonymous flags and child tables/constraints needed by the test; simplified mocks cannot prove hosted Supabase cascade. Use fake Auth HTTP transports and deterministic SDK/STT/Voyage providers for paid work. Do not call live model judges or run public red-team traffic.

Clock strategy: pure lifetime predicate tests receive explicit instants (`T−1ms`, `T`, `T+1ms`). Production wrappers always obtain fresh DB time; test the SQL helper's predicate independently using explicit fixture instants and real auth/session rows. For full-request integration, seed immutable start/expires around the actual database clock and coordinate with barriers; a Python-only frozen `now()` does not freeze PostgreSQL. No client-accessible clock/duration override or production grace period. Keep a small real-time boundary integration test in addition to fast deterministic cases.

Use independent browser contexts with independent cookie jars, plus pages within the same context for multi-tab tests. Fullstack harness must start its owned servers/ports with external keys blank and stop them afterward. Keep artifacts in temp/CI artifacts; never change `.gitignore` to hide generated files.

## 3. Authentication and authorization matrix

| Proposed automated file | Cases / expected assertion |
|---|---|
| `backend/tests/test_guest_provider.py` | Anonymous signup body/captcha; verified user/claims consistent; wrong sub/issuer/session/anonymous type denied; 429/5xx sanitized; no token/password in log/repr |
| `backend/tests/test_guest_auth.py` | New browser gets unique subject/user/session; no email/password; secure opaque cookies; disabled consents; age recorded via existing policy; registered session not overwritten; explicit end |
| `backend/tests/test_guest_provisioning.py` | Concurrent same intent and lost post-grant HTTP response recover one lifecycle; payload mismatch409; mandatory provider marker finds orphan after crash before subject persist; ambiguous attempt never reissues signup; narrow lookup/delete privileges and spoof/multiple-match denial; intent not reusable as general auth; no T reset |
| `backend/tests/test_guest_expiration.py` | Exact DB deadline boundary; absolute renewal blocked on repeated GETs; UTC/midnight/timezone changes do not alter T; old cookie invalid after new trial; fail-closed DB/provider revocation |
| `backend/tests/test_guest_permissions.py` | Enumerate each actual OpenAPI operation and classify public/personal/social/staff. Guest direct calls denied for social/staff even with adult age, MATCH consent, published profile or forged preexisting room. Unclassified new route fails the test |
| `frontend/tests/e2e/guest-expiry.spec.ts` | Refresh, close/reopen context with retained cookie, tab focus, offline/reconnect, multi-tab expiry and explicit new trial; clear private UI/cache/audio; no auto-signup |
| `frontend/tests/fullstack/guest-journey.spec.ts` | Landing → CTA → age/disclosure → trial → personal features; separate contexts isolated; before-T server restart preserves only valid stored data and original deadline; after-T no authorization |

Restricted-route inventory must cover matching draft/read/preview/publish/withdraw; candidates/skips; connection request list/send/accept/decline/cancel; rooms/read/messages/events/end/block; peer-reference/reveal requests/grant/decline/value/revoke; all shared activity list/invite/respond/lifecycle/focus/feedback operations; staff/moderation/admin access. Some endpoints return no data today without consent; verify the new explicit guest policy nonetheless. Own private profile/moods/memory/settings remain allowed after eligibility/consent. Public `/bots`, `/taxonomy`, health and static page remain intentionally public. `/social/summary` returns explicit zeros with no guest social query.

Include teen/under16 guests, minimum-age unchecked, fabricated adult claim, revoked AI/MEM/VOICE consent, GET another guest's UUID, guessed registered UUID and malformed idempotency/CSRF/Origin. Verify owner query scoping at service level, not just hidden buttons.

## 4. Lifecycle, race and cost tests

| Proposed automated file | Deterministic scenario and oracle |
|---|---|
| `backend/tests/test_guest_inflight.py` | Hold provider/tool response across T; pause SSE after lookup before final output check; attempt replay final after T; slow voice upload/transcription; final DB/dispatch decision at/after T denied, no await between final output check and dispatch, task canceled/late result discarded. Pre-T authorization completing physical commit/transport later is explicitly distinct |
| `backend/tests/test_guest_cleanup.py` | Seed all allowed tables and RAM stores with owner canaries; hard-purge; query all owner/FK variants and Auth identity/session/refresh children; assert zero guest links and other user's canaries untouched |
| `backend/tests/test_guest_cleanup_recovery.py` | Worker unavailable past T (still401); lease stolen/worker killed mid-job; DB/provider helper fails then succeeds; retry exhausted remains denied/alerted; cleanup rerun safe; new trial different IDs; restore expired DB in isolated service then purge before readiness |
| `backend/tests/test_guest_embeddings.py` | Pending/running job reaches T, delayed embed returns after purge, reconcile tries to recreate; no late vector/job publication, no unapproved memory indexing, consent/version fence preserved |
| `backend/tests/test_guest_exports.py` | Export content and job owned/session-bound; expiry capped at T, old URL cannot download; T-spanning create/download rejected; purge RAM/DB payload; user-downloaded copy explicitly out of server control |
| `backend/tests/test_guest_quotas.py` | 25 trial turns across midnight/restart/token rotation; 26th denied; 6/minute and per-user/global concurrency; voice clips/seconds and embedding growth caps; receipts do not double-charge |
| `backend/tests/test_guest_budget.py` | Concurrent reserve/settle/uncertain call; unknown rate fails closed; purge all users while daily cap exhausted, then new trial still cannot reopen cap; AI/STT/embed counted; registered headroom preserved |
| `backend/tests/test_guest_abuse.py` | Rotating HMAC IP retention, trusted proxy normalization, spoofed forwarding headers, direct upstream anonymous accounts never gain app sessions, repeated create intent/CAPTCHA failure; no raw IP/content log leakage |
| `scripts/load_guest_experience.py` (new) | Fifty visitors browse/record/read, up to10 guest AI runs; expire a cohort; measure cleanup lag, DB pool/RAM/error rates, budget headroom and registered responsiveness; no unexpected500/private leak/replay |

Run SQL migration/privilege tests with runtime role as well as fixture owner/superuser. Verify helpers denied to PUBLIC/anon/authenticated and executable only by intended role; check **SELECT/INSERT/UPDATE/DELETE** grants and schema exposure rather than assuming RLS enabled means correct ownership. The live audit only established SELECT denial.

Two-hour test must distinguish authorization from cleanup: at T requests401 even with sweeper stopped; after sweeper resumes all active-store guest data purges; provider deletion proves the intended anonymous subject only. Log/provider/backups are verified against documented retention/restore contracts, not a row-count assertion. Do not label a backup-erasure guarantee PASS based on active DB deletion.

## 5. Landing, tours and feedback UI tests

| Proposed automated file | Coverage |
|---|---|
| `frontend/tests/e2e/landing.spec.ts` | Public content with API offline; no signup/session creation on page load; both CTAs; valid-session Continue; root metadata/meaningful HTML; same-origin API routing; responsive menu and skip link |
| Existing `frontend/tests/e2e/auth.spec.ts` additions | Confirm/recovery/expired callback once-only sanitization, legacy `/#/` and deep-link navigation, no token in history/analytics/request logs |
| `frontend/tests/e2e/guest.spec.ts` | Disclosures/age/consent, creation busy/error/retry, status, quota variants, locked matching, privacy/export/end/register actions, five assistants, no cross-tab sensitive broadcast |
| `frontend/src/features/onboarding/tourSteps.test.ts` | Guest/teen/adult configurations; conditional step inclusion; version/replay/dismiss logic; no social step for guest |
| `frontend/tests/e2e/onboarding.spec.ts` | Dim/actual target/note, Next/Back/Skip/Finish/Escape; replay, browser Back, missing/hidden/late target, bounded wait, route/GSAP settle, dialog collision, focus restore, resize/mobile/reduced motion/expiry. No data mutation |
| `frontend/tests/e2e/feedback.spec.ts` | Native1–5 radio and category checkboxes; optional comment/category; keyboard; busy/failure/retry/receipt; no repeated sensitive-chat prompt; expiry clears draft; safe plain rendering |
| `frontend/tests/e2e/feedback-admin.spec.ts` | Direct route denied for guest/user; live-role revocation, loading/empty/error filters, accessible rating distribution/table, version-conflict recovery |
| `frontend/tests/fullstack/guest-feedback.spec.ts` | Real guest submission then expire/purge; retained feedback remains, guest/receipt link gone; administrator reviews only feedback metadata/comment |
| `frontend/tests/fullstack/guest-experience.spec.ts` | Full intended journey plus ordinary separate registration; old trial data not transferred; registered original journeys continue to pass |

Desktop widths1280/1440, mobile320/390/430, tablet768, landscape and200% text. Verify no horizontal overflow or covered focus/composer/CTAs; touch targets, contrast and text labels; loading/error/empty/ineligible/unavailable/quota/expired states. Axe is a useful automated check, not a screen-reader or complete keyboard guarantee.

## 6. Feedback backend tests

Create `test_feedback.py`, `test_feedback_privacy.py`, `test_feedback_retention.py`, `test_feedback_admin.py` in `backend/tests`. Assert rating-only success for both kinds; strict integer1–5 including bool/string/fraction rejection; max1000 codepoints; categories enum/max/dedup; reject raw URL/private fields; escaped HTML/SQL strings harmless; CSRF/idempotency/rate limits; lost-response and concurrent duplicates; deadline-crossing submission fails; purge separation and180-day retention.

Admin cases: roleless/guest/moderator denied, registered admin allowed with reauth, independent flag404, revoked role denied, PATCH expectedVersion conflict, correct pagination/filter-bound aggregates, null mean when empty, category sum may exceed submission count, spam excluded consistently, no user-history joins or private activity in response. Maintain moderation flag/role behavior in existing tests.

## 7. Registered regression suite

Run unchanged behavior checks for email login/signup/confirmation/recovery/logout/reauth, age/consents, AI availability/quota/streaming/recovery/output guardrails, history opt-in/export/delete, memory approvals/source invalidation/Voyage opt-in, mood scope per turn, profiles/matching v1/v2/shadow, request/room/message isolation, identity reveal/block/report/moderation, shared activities/focus timers, privacy exports/account deletion and deployment/proxy contracts.

Current suites already exercise much of this (`backend/tests/test_auth_flows.py`, `test_chat_persistence.py`, `test_memory.py`, `test_embeddings.py`, `test_context_privacy.py`, `test_matching_privacy.py`, `test_enforcement.py`, `test_data_lifecycle.py`; existing frontend/fullstack specs). Add guest tests without weakening/removing these tests. Generated OpenAPI and frontend types must match; required lint/type/build checks apply even when behavior tests pass.

## 8. Manual and approved integration QA

1. **First visitor:** private/incognito context, public root, understand disclosure, keyboard age step, start trial, no email/password. Compare a second independent browser's empty data.
2. **Five-assistant experience:** synthetic/non-sensitive conversation with every assistant, starters only edit draft, approve/reject memory, journal note, voice preview/edit/send. Cầu Nối never reveals real candidates. No surprise consent grant or rating prompt.
3. **Deadline:** use controlled staging clocks/fixtures, keep tabs/stream/mic open; deadline clears app and no late final appears. Try old direct API/cookie and offline reconnect; start fresh trial and verify old data absent.
4. **Accessibility:** keyboard-only all flows; NVDA on Windows and VoiceOver on an available Apple device for tour/ratings/dialogs; reduced-motion,200% text, soft keyboard and small landscape. Manual SR checks not run by this audit.
5. **Failure recovery:** approved disposable staging DB/Auth, stop cleanup worker, expire guest, verify denial; resume, observe backlog clear; fail identity helper, retry, confirm no unrelated identity deleted.
6. **Feedback:** rating without text, decline optional prompt, submit as guest, expire/purge then review as admin; inspect payload and database schema for identity separation; account-version filters/zero samples.
7. **Privacy and restore:** rehearse isolated backup restore, enforce expiry/purge before external access; verify actual provider/log/backup retention and approved public language. Do not perform a production restore or export personal data.
8. **Hosted Auth/CAPTCHA:** explicit non-production target and authorization required; test provider claim/session/child deletion and proxy IP behavior. A CAPTCHA site-key/secret/setup change is a release configuration action, not implied by read-only audit permission.

Limited real OpenAI/Voyage/voice smoke tests require an explicit budget, synthetic text/audio, selected target/model and provider retention approval. Production load/paid evals are not authorized.

## 9. Release gates and rollback

| Gate | Required evidence / no-go condition |
|---|---|
| G0 baseline | Current SHA and clean/preserved work; first load failure and isolated pass understood sufficiently for target environment. No claim of production capacity from fake model |
| G1 schema/Auth | Expand migration and runtime grants tested; generated contracts current; approved hosted anonymous/cascade/CAPTCHA/upstream capacity proof |
| G2 authorization | Boundary/race/direct API isolation tests pass; no guest social/staff access; registered regressions pass. Any expiry bypass is no-go |
| G3 cleanup/privacy | All footprint tests and worker-failure retry pass; lag alerts; provider deletion proof; disclosure/feedback-retention approval; restore strategy. Universal instant-erasure promise is no-go |
| G4 cost/capacity | Nonzero approved daily budget, prices/reservations and unknown-spend behavior tested; voice/embed included; 50-visitor target tested with registered headroom and one worker |
| G5 UX/feedback | Mobile/desktop/keyboard/SR and all states; optional tour can remain disabled if separately deferred; feedback admin/data separation proven |
| G6 release | Linux deployment/poller/proxy/image checks, reviewed hosted SQL and exact image SHA; explicit owner release decision before migration/settings/deployment |

Rollout: deploy compatible schema/app with entry flags off under approved release process; verify cleanup/expiry/health; enable a small approved cohort, then widen based on evidence. Flags off immediately stop new trial creation; existing guests still expire and purge. Roll back to a **guest-aware** compatible image or keep a guest-denial/cleanup compatibility service until no guest remains; an older image that ignores `account_kind` is not a safe rollback. Do not run destructive Alembic downgrade, drop data, or disable authorization to restore availability.

Monitor only content-free counts/latencies: trial creation/rejections, active guests, age-ineligible outcomes, expiry denials, cleanup lag/retries/orphans, AI/STT/embed reservations/uncertain cost, DB pool wait, SSE count and500s. Do not log feedback text, raw IP, recordings, tokens or conversations. Release report states actual commands, result counts, artifacts, skips, owner decisions and remaining risks with **PASS/PARTIAL/FAIL** per scope.

## 10. Audit completion verification

Final validation observed:

| Check | Outcome |
|---|---|
| `python scripts/check_docs.py` | PASS:41 Markdown files,312 local links,100 API operations,48 settings,38 ORM tables |
| Read-only Python validation of source link line bounds, Markdown fences and required documents | PASS after correcting three out-of-range source links;72 source line links checked across9 new documents |
| Independent builder check | Two substantive gaps found (expiry linearization and crash-before-subject orphan correlation), corrected across design/roadmap/tests/handoff; reviewer reread and reported “nothing important left” |
| `git diff --exit-code` / `git diff --name-only` | PASS: no tracked source/config/test/lockfile changes; `.gitignore` unchanged |
| `git status --short` | Only `?? docs/guest-experience/` after moving generated-only screenshots out of repository |
| Owned resources | Agent Browser session closed; `docker stop moodprint-guest-audit-db-20261028` succeeded and its `--rm` disposable DB container was removed |

Local versions observed: uv0.11.14, Python3.12.13, Node24.13.0, npm11.6.2, Docker29.8.2. CI uses Node22, so local success does not substitute for unchanged Linux/Node22 CI.

Audit deliverables are complete and reviewed. Application-feature release remains **PARTIAL** until future hosted/provider/restore/Linux gates are satisfied; a completed audit is not a completed implementation.
