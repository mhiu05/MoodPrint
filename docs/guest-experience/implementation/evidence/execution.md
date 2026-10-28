# Guest Experience Execution Ledger

Branch: `feature/guest-experience` | Worktree: `E:\MoodPrint-guest-experience` (external sibling of `E:\MoodPrint`)
Planning baseline: `main` @ `984753389aa8bd4b3112b19a8beceb1e538fd659` (local main == origin/main, verified with `git ls-remote origin refs/heads/main` on 2026-10-28).
Execution order: plan 08 total order (35 subtasks GE-00.1 .. GE-14.3). Resume from this ledger and `git log`, never from memory.

Status vocabulary: Implemented / Tested / Verified / Blocked / Not tested. Nothing is marked from an expected result alone.

## Preflight (GE-00.1 setup)

| Check | Result |
|---|---|
| `git status --short` (main checkout) | `?? docs/guest-experience/` only |
| `git rev-parse HEAD` | `984753389aa8bd4b3112b19a8beceb1e538fd659` |
| `git branch --show-current` | `main` (never edited by this work) |
| `git worktree list` | main + 4 prunable stale `.worktrees/*` entries (gitdir missing; left untouched) + `E:/MoodPrint-release-integration` (detached; untouched) |
| remote main | `984753389aa8bd4b3112b19a8beceb1e538fd659` (matches local) |
| Worktree | `git worktree add /e/MoodPrint-guest-experience -b feature/guest-experience <baseline sha>`; session entered via `EnterWorktree` path mode |

Rulings:

- Ruling: created the worktree with `git worktree add` rather than `EnterWorktree name=` — the native tool only places worktrees under `.claude/worktrees/`, but the task requires an unused external sibling directory; the native tool was then used in `path` mode to enter it. Cost if wrong: none (same git state).
- Ruling: this ledger (`docs/guest-experience/implementation/evidence/execution.md`) is the durable task ledger instead of the superpowers `.superpowers/sdd/` workspace — the task mandates this file, and `.gitignore` must not be modified (`.superpowers` is not ignored). Cost if wrong: none.
- Ruling (revised in GE-02.1): `implementation/09-sonnet-implementation-prompt.md` was first left out (not in the task's required list), but the copied index links to it and `python scripts/check_docs.py` (a CI check) failed on the dead link, so it was copied too (sha256 `ac4e6e01175ceea0bed2453af7ca2d7519d234737de3932cf1cf5189c333fea3`, identical to the original, which stays untouched in `E:\MoodPrint`). It is a historical handoff; the task prompt supersedes it. Cost if wrong: none.

### Planning docs copied (sha256; verified identical to sources in `E:\MoodPrint`, originals preserved)

```
405319ead7c7b7348236e6296bd72c631be3367747001bb293f0eef599b99d5f  docs/guest-experience/00-feasibility-summary.md
74221ba4efb4436f2c0ae2c8b7b845dcf64e5ee6c35e78e0efade41487d34bd6  docs/guest-experience/01-current-architecture-audit.md
6108d4bc576005becc849764a353291b4f79d8059a604d55467afd0975279723  docs/guest-experience/02-guest-auth-design.md
1c99a43182a8844cebfe22d234ab56510fe1880d93e4ec6c4989da5293c2cde1  docs/guest-experience/03-landing-onboarding-design.md
8da949084987b9e6629c06fb5219b4ec97093f2afd9ee02e5a78c507fb9a2a60  docs/guest-experience/04-feedback-system-design.md
e9cbb1850e0c15c68c002fe38e6b61191fe3bd114b1ee0368c32c42d62e72553  docs/guest-experience/05-implementation-roadmap.md
9a45f8ae19422914ee910a8d42aedef4442230ef7205ed9b19c6824e57b2dd59  docs/guest-experience/06-testing-and-release-plan.md
172eea7702163c4dee707062d501d79c98386936ee9c9f7451b2133d0012fa27  docs/guest-experience/07-risks-and-open-decisions.md
c0ca861528758950ce70b1fca814481f2bdb8a2ceb0479b6f538ab29721f8a47  docs/guest-experience/08-claude-code-handoff.md
fa9514f11a874e4967099e3df0f71407920f6a75de079ecadef00d7921c51186  docs/guest-experience/implementation/00-implementation-index.md
f6e3503ee7d3cec8d65015e94e9ea70dbc06d1dc8a7e825c32444097908c0c93  docs/guest-experience/implementation/01-foundation-and-guest-auth.md
c4b8fade19c24ac82f225744fe338b52fa0540d1e900f83ede9b1141636e5bd6  docs/guest-experience/implementation/02-guest-expiry-and-permissions.md
dea066111428ec326b6c57299f57f52634e17dc208e2633b0b283ab029bc9e04  docs/guest-experience/implementation/03-guest-cleanup-and-cost-controls.md
92f3d813f1ddaa7f242c1bce77f8c5941eab2e411886f7ff9873a0cd40269fe2  docs/guest-experience/implementation/04-public-landing-and-guest-ui.md
9d40b465c2d9b25f9b4ec5afaf26618c4dba1ba1909157b4e7c433e6b6503e27  docs/guest-experience/implementation/05-feedback-and-admin.md
b892d45ddd9b9b0c79894a5fb0c1105c32078e084d58d7844fad5da955cdbc08  docs/guest-experience/implementation/06-interactive-onboarding.md
bd93165ef0c8edfd2644fca60008234712075a3a5e9e71f7953fc4271a404c94  docs/guest-experience/implementation/07-integration-testing-and-release.md
65fa6114b8a7c85399da0af60f7400b638d57da25637cb5e2dff2baa16071f9a  docs/guest-experience/implementation/08-interface-and-dependency-matrix.md
```

## Baseline (GE-00.1) — fresh results on `main` @ 9847533

Environment: Windows 11, uv 0.11.14 with locked Python 3.12.13 (host `py` also has 3.11/3.14, never used for application commands), Node v24.13.0 / npm 11.6.2, Docker 29.8.2. Owned disposable container `moodprint-guest-impl-db` (`pgvector/pgvector:0.8.2-pg17`, loopback `127.0.0.1:26432`, public synthetic password); databases `moodprint_guest_{unit,dev,migration,review,fullstack,load}_test`. No `.env` exists in the worktree; external keys blank. Other containers/ports on the host (e.g. `moodprint-ai-memory-pg` on 16432) were not touched. Pristine-tree commands ran from a throwaway detached worktree of the baseline commit (removed at the end) so uncommitted feature edits could not taint them.

| Check | Command (from) | Result |
|---|---|---|
| Backend lint | `uv run --locked ruff check app tests evals alembic` (backend) | PASS (All checks passed) |
| Backend types | `uv run --locked mypy app` | PASS (89 source files) |
| Backend tests | `uv run --locked pytest -q` (unit DB) | PASS: **642 passed** in 571.69s (matches the audit's historical 642) |
| Migrations | `alembic upgrade head` / `current` / `check` (migration DB, via pristine tree) | PASS: `0015_context_privacy (head)`; "No new upgrade operations detected." |
| OpenAPI | `python ../scripts/export_openapi.py` | PASS: no drift, 100 operations |
| Frontend contracts/typecheck/unit | `npm.cmd run contracts:generate`, `typecheck`, `npm.cmd test` | PASS: 73 unit tests in 13 files (matches audit). `schema.d.ts` regenerates byte-identical content (Windows CRLF only) |
| Frontend build | `npm.cmd run build` | PASS, warning kept: main chunk 528.02 kB (matches audit) |
| Owned browser fixtures | `npm.cmd exec -- playwright test --config playwright.owned.config.ts` (pristine tree) | **186 passed, 1 failed (187 total, 6.0 min)** — failure `real.spec.ts:798 validated AI cards navigate to existing tools…`: `locator.fill` test timeout 45s waiting for the Mây textbox. Rerun in isolation: PASS (3.4s). Attributed as a load-sensitive timeout flake: my backend pytest was running concurrently on the same machine during the full browser run. Not proven; recorded as a baseline flake, not an introduced failure. (The audit's historical "44 selected cases" is a subset; the owned config actually runs 187.) |
| Synthetic fullstack | `uv run --locked python ../scripts/test_fullstack.py --reporter=list` (fullstack DB, pristine tree) | PASS: **28 passed** in 4.6 min (matches audit) |
| Docs / artifacts | `python scripts/check_docs.py`, `python scripts/check_reviewed_artifacts.py` | PASS (before feature edits: 51 files/390 links; 9 pinned approvals) |
| 50-user isolated load | `load_chat_memory.py --workers 1 --users 50 --port 8017` (load DB, pristine tree, nothing else heavy running) | PASS: status PASS, 1 worker, `server_start_attempts` 1, wall 42.79 s, `unexpected_errors` [], no 5xx; non-AI endpoints p50 770.07 ms / p95 2691.75 ms / max 8098.28 ms (941 calls); AI completion p50 12449.89 / p95 14232.77 / max 14624.98 ms (50); peaks: 48 admitted runs, 12 PG connections, pool 10 checked out, RSS 180.7 MB, embedding backlog 150 (0 at end); 130 durable messages; runs completed 60 / cancelled 10 / interrupted 1. Compare against the audit's historical overlapping-run failure: this isolated run passed, consistent with the audit; contention remains an unproven (untested here) explanation. |

Quirks learned (affect later commands): `npm.cmd exec -- playwright test … -g "text with spaces"` fails on this host with `'C:\Program' is not recognized…` — use a space-free regex such as `-g "validated.AI.cards"`; the session harness refuses compound shell commands that expand `$TEMP` or `cd` into another tree while also invoking git, so scratch paths are written literally.

Not run in the baseline (recorded as gaps, not passes): Linux/Node 22 CI jobs, poller/proxy/packaging checks (`deploy/aws/tests` needs Linux `fcntl`), hosted Auth/CAPTCHA, real model/Voyage, NVDA/VoiceOver.

Owner decisions (all unresolved, flags stay off): D01 deletion/backup/provider/security-counter disclosure and cleanup targets; D02 numerical daily guest budget (and any real-provider test budget); D03 180-day unlinked feedback retention and notice; D04 non-production hosted Auth/DB/CAPTCHA target. Local implementation proceeds; these gate public enablement, paid actions and GE-01.2 hosted proof.

## Task ledger

(Entries are appended below, one block per task, in plan 08 order. A task with a `complete` line is DONE; do not redo it.)

| Task | Status | Base..Head | Evidence |
|---|---|---|---|
| GE-00.1 | in progress | 9847533.. | docs committed (41bc1b6); backend full-suite baseline still running; see Baseline section |

### GE-01.1 — Verify anonymous provider contract locally (backend/app/modules/auth/provider.py)

- RED: `uv run --locked pytest -q tests/test_guest_provider.py` → 35 failed / 1 passed (`AttributeError: 'SupabaseAuth' object has no attribute 'anonymous_session'`, `'ProviderSession' object has no attribute 'is_anonymous'`).
- GREEN: same command → 36 passed. Regression `tests/test_auth_flows.py tests/test_runtime_provision.py tests/test_guest_provider.py` on a separate disposable DB → 51 passed. `ruff check app tests evals alembic` clean; `mypy app` clean (89 files).
- Changed: `ProviderSession` gains `is_anonymous` (token hidden from repr); `verify_token` now also enforces audience `authenticated`, finite future `exp` and strict boolean `is_anonymous` agreement between claims and `GET /user` (missing/non-boolean fails closed as `AUTH_UNAVAILABLE`); `anonymous_session(captcha_token, *, correlation_id)` performs one `POST /signup` and classifies `AnonymousSignupError.outcome` rejected (explicit 4xx) vs ambiguous (transport failure, 3xx/5xx, unusable body, `/user` failure or claim mismatch); `password_session` and `update_password` reject verified anonymous sessions with 403 `REGISTERED_REQUIRED` before any `PUT /user`.
- Fakes updated to emit `aud` + explicit `is_anonymous=false`: `tests/test_auth_flows.py`, `tests/e2e_auth.py`. Added `test_anonymous_token_cannot_use_the_permanent_recovery_path` (zero `PUT /user`).
- Ruling: plan step 5 asks conftest.add_actor/LocalAuth/load servers to also insert `auth.users(is_anonymous=false)` — deferred to GE-03.1, the first task that changes the SQL helper to join `auth.users`; inserting an unused column now would be untested scaffolding. Cost if wrong: one fixture edit moved earlier.
### GE-02.1 — Add compatible durable foundation (migration 0016_guest_foundation)

- RED: `uv run --locked pytest -q tests/test_guest_schema.py` → 3 failed (`TypeError: 'account_kind' is an invalid keyword argument for User`; missing `0016_guest_foundation.py`; `alembic current` still `0015_context_privacy`).
- GREEN: same command → 3 passed (lifetime 7199/7200/7201, registered/guest NULL predicates, kind/start/T immutability via a shift that keeps the 7200s CHECK satisfied, promote registered→guest denied, session cap, runtime-only grants/RLS/policy and PUBLIC execute revoked on guard functions, seeded 0015→head upgrade keeps the registered row and passes `alembic check` "No new upgrade operations detected").
- Regression (dev DB): `tests/test_readiness.py test_foundation.py test_database_operations.py test_auth_flows.py test_guest_schema.py test_guest_provider.py test_runtime_provision.py test_context_privacy_migration.py` → 96 passed. `ruff check app tests evals alembic` clean, `mypy app` clean (91 files). `python scripts/check_docs.py` PASS (52 files, 391 links, 100 operations, 48 settings, 45 tables); `python scripts/check_reviewed_artifacts.py` PASS (9 pinned approvals unchanged).
- Added: ORM `User.account_kind/guest_started_at/guest_expires_at` + `ck_users_account_kind`/`ck_users_guest_lifetime` + partial index; `AuthSession.created_at` (server `clock_timestamp()`); `app/modules/guests/models.py` (7 tables, no identity in budget/reservations); migration with `protection_statements` (RLS + runtime-only policy) and guard functions/triggers `guard_user_lifecycle` / `guard_session_lifetime`; `tests/guest_schema.py` installs the same guards into every metadata-built fixture DB (conftest, e2e_server, chat/social load servers); `READY_REVISIONS` is now `("0016_guest_foundation",)` (old image on the new schema reports not-ready by design) and `test_readiness.py` / `test_foundation.py` expectations moved accordingly (window still asserted exactly).
- Ruling: `auth_sessions.created_at` added as `DEFAULT now()` then `SET DEFAULT clock_timestamp()` — a volatile default on ADD COLUMN rewrites the table; existing rows get the migration time (true creation time is unknown). Cost if wrong: historical `created_at` is approximate; nothing reads it for registered rows.
- Ruling: `benchmark.py` and `evals/scenarios_live.py` fixtures were not given the guard installer — they never create guest rows; `create_all` still builds the new columns. Cost if wrong: a later guest test there would lack the trigger.
- Ruling: abuse-bucket `scope` allowlist is fixed to `intent, intent_global, creation_hour, creation_day, failed_signup, feedback, ai_minute, voice_minute` (derived from plan 03 limits); 0016 is unshipped so a later task may extend it before the first approved release.

### GE-02.2 — Publish flags and session contracts

- RED: `uv run --locked pytest -q tests/test_guest_contracts.py` → 3 failed (`KeyError: 'accountKind'`; `GET /public/experience` 404; `ModuleNotFoundError: app.modules.guests.schemas`).
- GREEN: same command → 3 passed. Regression `test_guest_contracts test_production_settings test_auth_flows test_guest_schema test_guest_provider test_eligibility test_foundation test_readiness` → 90 passed. `ruff` clean, `mypy app` clean (94 files); `export_openapi.py` + `contracts:generate` + `typecheck` clean; `npm.cmd test` 73 passed; `check_docs.py` PASS (101 operations, 67 settings, 45 tables).
- Added: six flags (all `False`), `GUEST_DAILY_BUDGET_USD` (Decimal, unset = paid guest closed), `GUEST_PRICING_JSON`, `GUEST_ABUSE_HMAC_KEY` (≥32 chars), `GUEST_CAPTCHA_SITE_KEY`, the AI/voice quota knobs with `GUEST_AI_GLOBAL_CONCURRENCY ≤ AI_GLOBAL_CONCURRENCY`; `GuestQuota`/`SessionView.{accountKind,guestStartedAt,guestExpiresAt,guestQuota}`/`FeatureView.feedback`; `GuestInput` (CAPTCHA token `repr=False`, `disclosureVersion: 'guest-v1'`, first declaration only) and `PublicExperience`; `GET /api/v1/public/experience` (no identity, `no-store`, availability needs flag + provider + CAPTCHA site key + HMAC key + database; budget/secrets never published); guest-aware `session_view` (database `clock_timestamp()` for `serverTime`, durable usage counters, no staff/moderation/social reads, `matching=false`, AI/voice closed unless `guest_paid_available`).
- Ruling: pulled forward from GE-03.1 a two-line change in `require_actor` so the sliding 12h renewal runs only for `account_kind == 'registered'` (without it the 0016 session-cap trigger would turn every guest request into a 500 and the guest session contract could not be exercised). GE-03.1 still owns the full refresh/clock work and tests (`test_refresh_never_extends_guest`).
- Ruling: `GuestQuota` lives in `contracts.py` (SessionView imports it) and is re-exported from `guests/schemas.py` to avoid a circular import; the public route lives in the new `guests/routes.py`, which GE-04.1 extends rather than re-registers.
- Ruling: under-16/missing-confirmation `GUEST_INELIGIBLE` mapping is deferred to GE-04.2's route (DTO validation would otherwise return `VALIDATION_ERROR`); no provider call can happen before then because no creation route exists yet.
- Env examples (`backend/.env.example`, `deploy/runtime.env.example`) document the new settings with empty/`false` values only — no secret, budget or price.

### GE-03.1 — Enforce core absolute session lifetime (migration 0017_guest_security)

- RED: `uv run --locked pytest -q tests/test_guest_expiration.py` → ImportError `lifetime_allows`/`require_registered_user`, wrong code `SESSION_EXPIRED` instead of `GUEST_EXPIRED`, helper still true after T, no `database_time`.
- GREEN: 7 passed (T−1ms allowed / T and T+1ms denied; real SQL helper flips at T with no cleanup worker; one statement observes `true` then `false` across `pg_sleep` proving `clock_timestamp()`; helper denies kind/provider-flag disagreement, missing provider row, revoked session, version mismatch, ended user; repeated reads and rotation never move start/T/session expiry; registered sliding unchanged; unreadable clock fails closed; expired guest error clears session/CSRF/intent cookies).
- Added: `guests/policy.py` (`database_time` — no override —, pure `lifetime_allows`, `assert_guest_active`, `require_registered_user`), `DomainError(clear_session=...)`, `verify_session` judges guest lifetime first, migration 0017 (`CREATE OR REPLACE is_provider_session_active`: VOLATILE, `clock_timestamp()`, joins `auth.users.is_anonymous`; ACL re-applied), `READY_REVISIONS = ("0017_guest_security",)`; shared fixture installer now builds a reduced `auth.users(is_anonymous, raw_user_meta_data, created_at)` with a trigger that creates the parent row for legacy direct `auth.sessions` inserts (mirrors the real FK; existing tests untouched except `_auth_rows` made `on conflict do nothing`).
- Ruling: **did not modify `provider_session.sql`** (plan lists it) — `scripts/apply_supabase_review.py` asserts the approved hosted initialization artifact embeds that file byte-for-byte, so any edit (even a comment) would break the approved hosted path. The guest-aware helper lives only in migration 0017 (`HELPER_SQL`); `alembic/env.py` now installs the legacy helper only when absent and *before* migrations so a no-op `alembic upgrade` can never overwrite the 0017 version. Cost if wrong: the approved initialization SQL keeps the legacy helper until 0017 is applied (intended).
- Ruling: `scripts/prepare_supabase_migration.py` / `verify_migration_review.py` not modified (plan lists them): the former would regenerate approved initialization SQL; GE-14.3 produces a separate pending review package instead.

### GE-03.2 — Deny guest social access at route and peer gates

- Tests: `tests/test_guest_permissions.py` (61 tests). RED was shown by **mutation** (guards were written before the test file): disabling the six guards (`require_registered_actor`, `match_consent`, `pair_transaction` peer check, `eligible_peers` filter, summary fast path, consent MATCH) made 56 of 59 run tests fail; guards restored (verified no `if False` remains).
- Coverage: exact set equality of OpenAPI operations vs a four-way classification (public / personal / registered_only / summary_zero, plus guest_entry after GE-04) — a new unclassified operation fails; each of the 52 registered-only tuples returns 403 `REGISTERED_REQUIRED` for a live adult guest with forged consents (expired guest → 401 `GUEST_EXPIRED` first); registered users still reach social routes; MATCH enable denied/withdraw allowed; guest summary = deliberate zeros with no social table read; forged guest profile + pair + room never appears for a registered user (candidates empty, rooms hidden, no message stored, no peer UUID in any response); guest-vs-guest and guest-vs-registered private items 404 with no leak; forged staff role never grants a guest; activity worker aborts a forged open guest session (`guest_participant`).
- Changed: `Actor.account_kind`, `require_registered_actor` swapped into social/activities/moderation/reveal/report/staff/notification routes and `POST /auth/reauthenticate` (own identity routes stay personal), `match_consent` + `pair_transaction` + `eligible_peers` + `visible_rooms` (via `room_gate`) deny guests as requester or peer, `social_summary` zero projection, `activities/jobs.abort_guest_sessions`, `hooks.abort_rooms`.
- Full-suite verification at this state: **757 passed** (exit 0; unit DB, 8:53–9:17 min).
- Fix found by the GE-03.1 full run and committed with this group: GE-02.2's `GUEST_AI_GLOBAL_CONCURRENCY ≤ AI_GLOBAL_CONCURRENCY` validator rejected existing configs that only lower the global cap (broke `test_two_workers_share_admission_and_remote_cancellation`); now an explicit guest value above the cap is an error but an unset default is clamped (test `test_guest_input_and_settings_defaults_fail_closed` RED→GREEN).

### GE-04.1 — Owned, durable provisioning intents

- RED: tests written first, run with `intents.py`/`limits.py` withheld → 2 failed, 5 errors (import); GREEN: `tests/test_guest_provisioning.py` 7 passed (missing/foreign Origin, missing/`0` `X-Guest-Intent`, `Sec-Fetch-Site: cross-site` → 403 and no row/cookie; cookie `HttpOnly; SameSite=strict; Path=/api/v1/auth; Max-Age≤600`, no `Domain`, `Secure` only with secure config; reuse of one unbound intent; random correlation never sent to the browser; two independent DB sessions binding one cookie/key/payload → one binding, changed key/payload → 409 `IDEMPOTENCY_CONFLICT`, unknown/expired → 422 `GUEST_INTENT_INVALID`, finished → 409 `GUEST_INTENT_TERMINAL`; 10 intents/IP/10 min then 429 `GUEST_CREATION_LIMIT` with `Retry-After`, spoofed `X-Forwarded-For` ignored, global per-minute ceiling; hour 3 / day 10 creation caps; keys are 64-hex HMACs never containing the address, IPv4-mapped IPv6 normalized, IPv6 bucketed by /64, missing key → `GUEST_DISABLED`).
- Added: `guests/intents.py`, `guests/limits.py` (atomic `INSERT … ON CONFLICT … WHERE count < limit`), `guests/availability.py`, `POST /api/v1/auth/guest-intents`.
- Limitation (recorded, not fixed): the HMAC key has no rotation epoch yet; rotating it mid-window starts new buckets (counters are ≤24 h). The plan's "retain prior key ≤24 h" is deferred to the release runbook.

### GE-04.2 — Grant one trial and recover ambiguous outcomes

- `tests/test_guest_auth.py` + provisioning: 12 → 14 passed with GE-04.3. One database deadline (user `guest_started_at` sampled by a CTE inside the INSERT; T = T0 + 7200 s; session, cleanup job and usage row created; all four consents false; age recorded; distinct internal/provider subject; no provider token or refresh token in any `moodprint` table); lost response recovered by same intent + key with rotated credentials, same user and T, old credential revoked, exactly one signup; concurrent recoveries leave one live credential (a superseded loser is told 409 `GUEST_ATTEMPT_PENDING`, never a stale 401); ambiguous signup (timeout after the provider created the identity) → 5 retries and a changed key produce exactly **1** upstream signup, attempt `ambiguous`, no grant; provider success + grant failure → no app grant, attempt `orphan_pending` with provider ids, unrelated permanent canary intact, retry is terminal; CAPTCHA rejection → `rejected`, creation count refunded, failed-signup counter 1; under-16 or unconfirmed → 422 `GUEST_INELIGIBLE` with **zero** provider calls; registered cookie present → 409 `REGISTERED_SESSION_PRESENT` and never overwritten; live guest cookie → 200 same trial; entry flag off keeps committed-grant recovery but blocks a fresh signup; permanent login rejects anonymous provider identities and guest mappings.
- Ruling: a successful new provider signup is *not* attempted after the flag turns off mid-flight — it is recorded as `orphan_pending` for guarded cleanup (matches the plan); the provider-side deletion/reconciliation itself arrives with GE-06.2.
- Deviation note: GE-04.2's mapped-recovery lock order (owner → attempt) is implemented; the recovery-versus-cleanup deadlock regression test needs the cleanup worker and is therefore scheduled in GE-06.2.

### GE-04.3 — End guest lifecycle safely

- Tests: logout ends every credential (including a second tab) with `status=deleting`, `auth_version+1`, all sessions revoked, **T unchanged**, cleanup job `due_at`/`next_attempt_at` moved to database now, recovery afterwards → 409 `GUEST_INTENT_TERMINAL`, forged CSRF → 403, all three cookies cleared; registered logout still ends only its own session; `POST /auth/guest/end` is guest-only (registered → 403 `GUEST_REQUIRED`), needs `Idempotency-Key`, and a repeat after a lost response returns 401 with cookies cleared.
- Added: `end_guest`, `cleared_response`, `guest_actor`, `POST /api/v1/auth/guest/end`; guest `POST /auth/logout` delegates to `end_guest`. After commit it invalidates AI runtime context and owner exports.
- API contracts regenerated (`openapi.json`, generated TS, docs) — 104 operations; `check_docs` PASS.

### Commit grouping (Ruling)

GE-03.1, GE-03.2, GE-04.1, GE-04.2 and GE-04.3 share files (`core/security.py`, `auth/routes.py`, `guests/routes.py`, `tests/guest_helpers.py`, the operation-classification map) and were only green together, so they were committed as one reviewed group, `5cc8128`; per-task evidence stays in the sections above. From GE-05 on each group is committed right after its own verification. Cost if wrong: a reviewer cannot cherry-pick 03.1 alone.

### GE-05.1 — Fence transaction and private HTTP output

- Tests `tests/test_guest_inflight.py` (8 for 05.1): a write whose body outlives T rolls back mutation **and** receipt together (real DB, held transaction, real time crosses T); a pre-T decision that commits later is unreadable (`401 GUEST_EXPIRED`); `GuestOutputMiddleware` driven with a fake inner app + controllable monotonic clock — body built before T, queue wait pushes the clock past T → sanitized 401 with three cookie deletions and zero private bytes; one tick before T delivered unchanged; non-guest never touched; streamed frames after T suppressed and closed; the event log shows `check` immediately before `send:body` (no await between); end-to-end through the real ASGI stack a handler that outlives the trial returns 401, not its payload; `guard_guest_dispatch` denies at/after T and is a no-op for registered; guest transactions set `statement_timeout`/`lock_timeout` to the remaining grant.
- Mutation check (the guards pre-dated the test file): disabling the final transaction check and the two output checks made 5 of 8 tests fail; restored (no `if False` left).
- Added: `guests/deadlines.py` (`GuestDeadline`, `guest_deadline`, `final_guest_authorization`, `guard_guest_dispatch`), `guests/output.py` (pure ASGI, outermost, after `BodyLimitMiddleware`), `require_actor` records the conservative bound (monotonic sampled *before* the DB round trip), `transaction()` final check + statement/lock bounds. Registered requests bypass all of it.
- Limitation recorded: the monotonic bound is per process; logical authorization at the final check is distinct from physical TCP delivery (documented in `output.py`), and a lock wait that begins before the user kind is known (the owner `SELECT … FOR UPDATE` itself) is bounded only by the pool/lock settings, not by T.

### GE-05.2 — AI runs, tools and every SSE event

- Tests (4 new in `test_guest_inflight.py`): an idle SSE stream closes at T with only the content-free `revoked` frame, the late model answer is never published (no `final` in `run.events`, 1 model dispatch total); a held provider call is cancelled by the deadline task itself, inside the 0.5 s monitor cadence; `ConversationStore` honours a hard deadline (registered sliding TTL unchanged); `AiRuntime.expire_guest` drops runs, events, proposals and context and cancels the held call.
- Finding fixed on the way: the outer guard also suppressed the `revoked` frame (correct per the plan, which allows that one content-free event) — `REVOKED_EVENT` is now the single post-T frame permitted on a started stream.
- Added: `LiveRun.deadline`, `check()` denies at T (monotonic + database), `asyncio.timeout(min(ai_timeout, remaining))`, `_cancel_at_deadline`, a final-authorization inside the persistence transaction and a publication check before RAM/event append, per-event/tick/heartbeat SSE guards, `store.create(hard_deadline=…)`, `end_guest` now calls `expire_guest`.
- Not separately proven: Last-Event-ID replay of a *durable* final after T is covered only by the 401 at `require_actor` plus the middleware; a persistent-chat variant of the held-provider test was not written (the code path is shared). Both are listed for GE-14.1 review.

### GE-05.3 — Cap memory/history and fence embeddings

- Tests `tests/test_guest_embeddings.py` (4): provider answers after T → zero `memory_embeddings`, the job ends `cancelled` (not retried), reconciliation and a new worker tick recreate nothing; an expired guest's memory cannot be enqueued; guest semantic indexing needs its own `GUEST_SEMANTIC_ENABLED`; proposal expiry ≤ T, saved-conversation expiry ≤ T, proposal creation after T fails `GUEST_EXPIRED`.
- Added: `_authorization` denies an expired guest (owner lock + fresh database clock; covers claim, validation and publication), `reconcile_embedding_jobs` skips expired guests, `create_proposal` and saved conversations cap at T.

### GE-05.4 — Voice, exports and guest data controls

- Tests `tests/test_guest_exports.py` (6): export TTL = min(900 s, remaining trial); download at T → 401 with no payload; guest needs `guestConfirmation: "guest-data-v1"` (no password), `social` scope → 403 `REGISTERED_REQUIRED` before any query, second download 410, another trial 404; registered still needs recent reauth and ignores the guest confirmation; guest `scope=account` deletion → 204, revoked, cleanup `due_at` now, **no** `data_jobs` row (hard-purge queue, not the registered tombstone worker); voice: a result arriving after T is discarded (401, zero further dispatch), audio that finishes after T is never dispatched.
- Bug found and fixed while stabilizing: the clamped STT budget timer can fire one Windows clock tick (~15 ms) *before* `remaining()` reaches 0, which reported 503 `TRANSCRIPTION_FAILED`; a guest-budget timeout now reports `GUEST_EXPIRED`. 3 consecutive runs 6/6.
- Contracts regenerated (`guestConfirmation` on `ExportInput`/`DeletionInput`, documented 204 on `POST /data-deletions`).

### GE-06.1 — Purge the full guest footprint atomically

- Tests `tests/test_guest_cleanup.py` (7): `INVENTORY` classifies **all 45 ORM tables** (purged / social / detached / owner) and the test fails on any new or obsolete table; a seeded guest with a row in every guest-reachable store (AI conversation/message/run/turn/usage, memory/proposal, private item, mood, age, consents/events, outbox, identity field, data job, idempotency, matching draft/profile, candidate refs both directions, forged staff role, operation link, provisioning attempt, provider `auth.users` + child session) is purged → **zero** rows in every `users.id` foreign-key column by metadata, zero saved conversation/run/memory ids, zero attempt rows naming the provider ids, provider identity and children gone, while the registered canary's counts and provider rows are byte-for-byte equal before/after; replay of a completed purge is safe; a stale/foreign lease or a still-active trial is `fenced` (nothing deleted, trial stays usable); real registered counterpart evidence (pair, room, registered-authored message) → `incident_required` with the job alerted, the user retained as `deleting` with sessions revoked and the counterpart's message kept; a guest-only malformed graph is removed without touching another guest; a provider-helper refusal (permanent identity) rolls back every row and the retry then completes; late writers fail (FK) or update zero rows and `_authorization` is `None`.
- Mutation check: removing the attempt-row and message deletions made the purge test fail (`no attempt row may keep provider ids`); restored.
- Added: `guests/lifecycle.py` (`INVENTORY`, `purge_guest`), migration-0017 helper `delete_guest_provider_identity` (SECURITY DEFINER, empty search_path, guest-only, nonactive/expired, unique mapping, anonymous-only, returns true only when absent, no PUBLIC/anon/authenticated/service_role execute), fixture `auth.sessions` now has the real `ON DELETE CASCADE` FK so child-row cascade is exercised locally.
- Limitation (recorded): the incident path deletes **nothing** (the plan says mark first and preserve rows), so an incident guest's personal content stays until the owner-approved incident procedure runs. The detached-liability settlement hook is added by GE-07.2.

### GE-06.2 — Recover cleanup and reconcile orphan attempts

- Tests `tests/test_guest_cleanup_recovery.py` (12): a crash before commit rolls the whole purge back, the job becomes `retry` with a 5 s backoff and the retry then completes (provider rows gone); a lost lease cannot finish cleanup (new holder only); 7 consecutive failures with all flags off never reactivate the guest (still `GUEST_EXPIRED`, kind/start/T unchanged, alert raised after the automatic burst, then hourly; backoff 5/15/60/300/900 s); `incident_required` jobs are never reclaimed; a marker lookup recovers an orphan whose process died before the subject was persisted (only the marked identity is deleted, an unrelated permanent canary survives, **one** upstream signup in total); empty lookups never reissue signup and poll at 5 s / 30 s / 300 s / hourly, then `incident_required` after the 24 h window; duplicate markers delete nothing; non-anonymous, out-of-window or mapped identities are never matched; with every flag off expiry, cleanup and reconciliation all still run; the startup scan inserts a missing job without changing access; recovery racing cleanup completes without a deadlock (owner → attempt/job order); metrics are content-free.
- Added: `guests/jobs.py` (`process_guest_cleanup`, `reconcile_guest_provisioning`, `ensure_cleanup_jobs`, `guest_metrics`), migration-0017 helpers `find_guest_orphan_subjects` / `delete_orphan_guest_identity`, and an isolated `guest_worker` task in the lifespan (own try/except per work class, runs regardless of every flag, cancelled and awaited at shutdown) so a guest failure cannot starve activities/retention nor the reverse.
- Not separately tested: "activity worker still advances after a guest purge failure" relies on the two loops being separate tasks with their own exception handling (asserted by structure, not by a running lifespan test; GE-14 fullstack runs the real lifespan).

### GE-07.1 / 07.2 / 07.3 — Durable quotas, detached budget, every paid dispatch gated

- Full-suite checkpoint before this group: **800 passed** (GE-05 state, exit 0, 10:17).
- GE-07.1 tests `tests/test_guest_quotas.py` (7): 25 AI turns then `GUEST_QUOTA_EXHAUSTED`; replay of a client message id returns the claim without a second increment and a different payload conflicts; counters are a lifetime row keyed only by the user (not by session, tab or day); voice 6 clips / exactly 180 000 ms allowed and 180 001 ms refused, `VOICE_ALREADY_PROCESSED` for a processed clip; 6/min→`GUEST_RATE_LIMITED`, 1 active/guest→`GUEST_BUSY` with `Retry-After`, a refused admission consumes nothing; under real contention 12 AI claimants → exactly **10** admitted (2 `GUEST_CAPACITY`) and 5 voice → exactly **3**; stale leases do not hold capacity; the session quota view reads the durable counters. Design choice: per-minute rate is counted from `guest_operation_links.created_at` (column added to the still-unshipped 0016), so no identity-keyed abuse bucket exists to purge.
- GE-07.2 tests `tests/test_guest_budget.py` (11): unset/zero budget, missing/partial/non-integer/boolean prices fail closed per kind; exact upper bounds (`3×(max_input×max(rates)+1200×output)`, voice rounded up to the billing quantum, embed per request); 8 concurrent reservations of 300 against a 1 000 limit → exactly 3 succeed, `spent+reserved ≤ limit`; replay reserves once; uncertain outcome charges the upper bound exactly once and a later "actual" never reduces it; known actual releases the difference once, a definite no-dispatch is released once, an actual above the bound charges it and **halts** paid admission across days; stale reservations become uncertain (dispatched) or are released (never dispatched) and are never replayed; **purging every guest leaves the budget exhausted** (a newcomer gets 429 `GUEST_BUDGET_EXHAUSTED`), the retained tables have no user/run/provider/session/IP column and no FK; a late settlement charges the reservation's original day and recreates no user-linked row; retention removes expired counters, resolved reservations after 24 h and unlinked days after 30 d but never a day with outstanding liability.
- GE-07.3 tests `tests/test_guest_paid_dispatch.py` (4): with AI/VOICE consent and a working test provider but **no approved budget/prices**, AI and voice are refused (`GUEST_PAID_UNAVAILABLE`), the model and transcriber are called **zero** times, no ledger or link row exists, `features.ai/voice` are false; AI order is reservation marker → model call, an exhausted budget or quota refuses before any provider call and consumes nothing, `GuestGuardedModel` never delegates when its guard refuses; voice order is marker → provider, exhausted budget → 429 with zero provider calls, a replay is `VOICE_ALREADY_PROCESSED`; embeddings need the guest-semantic flag, a price, budget and a reservation (zero calls without them, settled once with them); an AI call still in flight when the guest is purged is charged uncertain once, the late answer creates no user, `ai_usage` or link row.
- Added: `guests/pricing.py`, `guests/accounting.py` (`reserve/mark_dispatched/settle/release`, purge and stale hooks), `reserve_guest_quota`/`finish_guest_quota`/`guest_quota_view`, `ai/guest_model.py`, `LiveRun.{quota,reservation,dispatched,before_dispatch}`, `AiRuntime.guest_dispatch_guard/settle_guest`, provider wraps the model for guest runs, AI/voice/embedding fail-closed gates and admissions, worker tasks `settle_stale_liability` and `retention_tick`. `purge_guest` now settles open reservations before deleting links.
- Ruling: guest AI turn admission/AI SDK `before_dispatch` marks the reservation **dispatched before** the final lifetime check; if that last check then fails the bound is still charged (conservative, never a refund). Cost if wrong: a few reserved nano-USD per racing call at T.
- Limitation: only the existing fake providers exercised the dispatch path; no real model/STT/embedding call and no real billing were made. The `_BudgetHooks` ordering the plan mentions (observer vs progress awaits) was not rewritten because the guard now runs inside the model wrapper, after the SDK's own awaits.
- Existing guest tests that call AI/voice (`test_guest_inflight`, `test_guest_exports`, `test_guest_embeddings`) now enable explicit synthetic fixture pricing via `enable_paid_fixture`; no production price/budget is invented anywhere.
- Full-suite after GE-07 (disposable PG on :26432, `uv run --locked pytest -q`): **841 passed**, exit 0, 11:15. (800 at the GE-05 checkpoint + 7 quotas + 11 budget + 4 paid dispatch + earlier GE-06 additions.)
- GE-01.2 (hosted Anonymous Auth compatibility) is committed only as a **skipped-by-default, BLOCKED** gate: `tests/live/hosted_guard.py` refuses before any request unless `RUN_GUEST_AUTH_COMPATIBILITY=1`, `APPROVED_GUEST_AUTH_TARGET` (the approved non-production project ref), a matching `GUEST_AUTH_TARGET_URL` and a key are supplied out of band (D04; `.env` is never read) and `docs/guest-experience/implementation/evidence/hosted-auth.md` is the runbook. No hosted call was made; nothing in this branch claims hosted Auth works.

### GE-08.1 / 08.2 / 09.1 / 09.2 — Public landing and deadline-aware guest experience (frontend)

- GE-08.1: the email-link callback is parsed **once** in `main.tsx` before React mounts (StrictMode can no longer re-parse a cleaned URL) and reaches `RealApp` as an immutable prop; `classifyEntry` (unit-tested, `appEntryRoute.test.ts`) routes `/` to the public page, `#/…` and `/auth/callback` to the lazily loaded app, anything else to a public not-found; `validateSession` rejects malformed sessions. Added an `auth.spec.ts` case: a recovery token never reaches `localStorage`/`sessionStorage`/console, and not the URL after `goBack`.
- GE-08.2: Vietnamese landing (hero, five assistants, privacy, FAQ, skip link, menu), readiness-gated CTA that never creates an identity on load; `index.html` carries a static fallback and Open Graph metadata; the API serves a CSP that stays same-origin unless `GUEST_CAPTCHA_SITE_KEY` is set (then only `https://challenges.cloudflare.com` for script/frame/connect) and marks `/auth/callback` `noindex, nofollow, no-store`; `deploy/Caddyfile` mirrors both (`GUEST_CAPTCHA_ORIGIN`, unset by default) and **validates** (`caddy validate`, and `caddy adapt` shows the exact CSP with the origin set). `scripts/test_staging_proxy.sh` gained header assertions but was **NOT RUN** (the `:ci` images are packaged in GE-14).
- Landing tests `landing.spec.ts` (11): API offline, load sends only readiness/session GETs, closed readiness keeps the CTA disabled, registered visitor sees Continue, keyboard skip link/FAQ, 320/390/768/1440 px with axe (wcag2a/aa) and 200 % text, reduced motion, public not-found. **Defect found by the 200 % check and fixed:** the `minmax(14rem|16rem, 1fr)` grids overflowed a 320/390 px viewport (224 px/154 px) → `minmax(min(Nrem,100%),1fr)` + wrapping.
- GE-09.1 `guest.spec.ts` (11): under-16 and an unconfirmed attestation never reach the network; boundary-year adult attestation; a started trial shows `còn 2 giờ` and leaves no CAPTCHA token/CSRF/attempt key in browser storage; a 5xx retry reuses the **same Idempotency-Key and body with no second intent**; `GUEST_ATTEMPT_PENDING` explains and resumes with the same key; a definitive 422 requires a new token, key and intent; double click = one intent + one creation; dismissal creates nothing; guest `/connect` and `/messages` show the registered-only explanation with **zero** social requests; ending the trial asks first, then shows the content-free end screen. Mutation check: dropping the key reuse and the under-16 guard failed tests 1, 5, 6, 7; restored byte-identical.
- GE-09.2 `guest-expiry.spec.ts` (8, Playwright fake clock): the deadline replaces the private tree and a response that arrives afterwards never renders or triggers a request; rewinding the device clock cannot extend a trial and moving it forward does not end one; a server `GUEST_EXPIRED` ends the trial before the local timer; opening after expiry shows only the end screen; refocus re-reads the session; ending in one tab ends the other; "new trial"/"register" paths. **Two defects found by these tests and fixed:** (1) two overlapping `/session` reads — the first 401 calls `api.reset()`, which aborted the second raw and `SessionRoot` showed "Chưa thể mở MoodPrint" instead of the end screen → results from an older client epoch are now dropped and the error state is cleared when a trial ends; (2) ending the trial never went through the lifecycle hook, so no `ended` signal reached other tabs → the end flow now calls the hook's `expire("ended")`.
- Guest copy: the conversation info panel states that nothing outlives the trial and that long-term history is unavailable.
- Evidence: owned Playwright suite **218 passed** (6.0 min, exit 0, includes the 11 edited `goto("/#/")` calls), `npm run typecheck` clean, Vitest 84/84, `npm run build` OK (main chunk 318.78 kB), real FastAPI/PostgreSQL `journeys.spec.ts` + `local-mvp.spec.ts` 7/7, backend `test_public_headers.py` + `ruff` + `mypy` clean.
- Deviation (ruling): the plan's fullstack `guest-journey.spec.ts` is **not written here** — `tests.e2e_server` has no synthetic anonymous provider or CAPTCHA, which GE-14.1 builds for the integrated journeys. Cost if wrong: the browser→real-backend guest path is first proven in GE-14 instead of GE-09.
- Not done / gaps: `AIData`/`Privacy`/`Voice` guest copy variants were not separately changed (history and voice are unavailable to a guest without an approved budget/consent; revisit in the GE-14 copy pass); SSE streams (`api/stream.ts`) use caller-owned signals, so after expiry they stop because the private tree unmounts and the server emits `revoked` — no dedicated browser test for a late SSE frame; Chrome DevTools/real Turnstile widget not exercised (stub only); no hosted Auth.
- Commit grouping (ruling, as for GE-05): GE-08.1/08.2/09.1/09.2 share `RealApp.tsx`/`client.ts` hunks that cannot be split without interactive staging, so they land as one commit.

### GE-10.1 — Unlinked constrained feedback storage (migration 0018)

- Tests `tests/test_feedback_privacy.py` (54): `app_feedback` columns are exactly the documented set with **no foreign key and no identity column**; receipts cascade from user and from feedback only (no table references a receipt); a rating alone inserts with database defaults (`[]`, NULL, `new`, v1); 15 invalid direct-SQL rows are rejected (rating 0/6/NULL, duplicate/unknown/NULL/oversized categories, 1001-char, C0/DEL/C1 comments, a URL as context, bad kind, NULL version) and 6 boundary rows accepted (1000 chars, 1000 emoji = code points not UTF-16 units, tab/LF/CR, HTML/SQL-looking text stored verbatim, all 8 categories); validators return `false` — never NULL — for NULL/duplicate input; receipt deletion keeps feedback and review events; a user delete cascades only the receipt while a staff user with review events is `RESTRICT`ed; feedback deletion cascades receipts/events; per-owner idempotency key is unique; DTO tests cover bool/string/float/out-of-range ratings, repeated/unknown/NULL/oversized categories (stored in canonical order), comment normalization (trim, empty→NULL, limit before **and** after trimming, controls/C1/DEL/lone surrogates rejected even when trimmable) and rejection of identity/URL/attachment/version fields.
- Mutation check: removing the distinctness rule and the C1 range from the SQL validators made 4 tests fail (`{bug,bug}`, `\x85`, `\x9f`, NULL semantics); restored byte-identical.
- Real upgrade: `tests/test_guest_schema.py::test_upgrade_from_0015…` now upgrades 0015→head (**0018**), asserts the three tables exist with RLS and **zero** grants to PUBLIC/anon/authenticated/service_role, no PUBLIC EXECUTE on the validators, and `alembic check` reports no drift. A bug found there (a naming-convention double prefix when dropping `ck_guest_abuse_buckets_scope`) was fixed with `op.f(...)`.
- Added: `app/modules/feedback/{models,schemas}.py`, migration `0018_app_feedback` (validators with `SET search_path=''`, coalesce-to-false, EXECUTE only for `moodprint_runtime`; tables, indexes, RLS; new HMAC bucket scope `feedback_attempt` for the per-identity minute window; destructive downgrade refused), `tests/feedback_schema.py` (the fixture schema installs the same function SQL before `create_all`, also in the e2e/chat/social load servers), `INVENTORY` entries (receipts `purged`; feedback and review events `detached`), docs (schema, migrations, operations).
- Ruling: `READY_REVISIONS` is now **only `0018_app_feedback`** (0017 → 503). Retention/purge touch the feedback tables even with every flag off, so a 0018 image on a 0017 schema would fail its first purge while reporting ready. Cost if wrong: a rollback to a 0017-only image needs the readiness tuple to list 0017 again (code change, no data impact).
- Ruling: the per-identity attempt window uses a `feedback_attempt` scope whose key is an HMAC of (scope, window, user) that expires with its window and is removed by the existing retention tick; no raw identifier is stored, and the row has no FK. Cost if wrong: a one-minute-lived keyed counter outlives a guest purge by at most that window.
- Not yet done (later GE-10 tasks): submission/limits endpoint (10.2), explicit receipt deletion in purge and retention (10.3).

### Open risk carried from GE-01.1

- Risk (hosted, unverified until GE-01.2): registered login now fails closed if the hosted Auth access token or `GET /user` omits `is_anonymous`; GoTrue is expected to include it, but only the hosted proof can confirm. Do not enable/deploy before G1.

## Codex continuation — 2026-10-28

- Resumed the existing `E:\MoodPrint-guest-experience` worktree on `feature/guest-experience` at `5f2bab2ca0ba08b7d676839b26b8ddfc1934f550`; preserved the uncommitted GE-10.2 implementation and unrelated `docs/plans/` / `frontend/evidence/`. Main remains at `9847533`. No new worktree, reset, cleanup, push, merge, deployment or `.gitignore` change.
- Executed `git status --short`, `git rev-parse HEAD`, `git branch --show-current`, `git worktree list`. `git ls-remote origin refs/heads/main` could not connect from the sandbox; remote freshness is unverified, not assumed.
- Using the installed executing-plans/TDD/debugging/verification/review workflow. The sibling worktree has no portable toolkit files; applicable instructions and skills are read from `E:\MoodPrint`. Located the actual finishing skill in the installed Superpowers 6.4.2 cache; the owner's explicit keep-branch/no-push instruction selects its keep-as-is outcome without another menu.
- Durable remaining order: GE-10.2 verification/commit → GE-10.3 → GE-11.1 → GE-11.2 → GE-12.1 → GE-12.2 → GE-13.1 → GE-13.2 → GE-14.1 → GE-14.2 → GE-14.3 → whole-branch independent review and fixes. Existing task evidence is historical until re-run; no completed task is restarted.
- Pre-flight: 10.2 produces receipt submission/state consumed by 10.3/12.1; 10.3 must explicitly unlink receipts before both account purge paths; 11.1 staff lock precedes 11.2 feedback row; 11.2 generates DTOs before UI; 13.1 either proves the pinned dependency or defers spotlight and 13.2 supplies inline guidance; 14.1 owns missing synthetic anonymous Auth/CAPTCHA and artifact routing. No unresolved interface conflict found in these contracts.
- Ruling: keep the existing specified execution ledger instead of creating a second `.superpowers` ledger or running POSIX task scripts — the prompt explicitly names this durable ledger and Windows/local evidence conventions. Cost: manual per-task ledger updates.
- Initial `uv run` was denied access to its external cache; reran the authorized local test command through sandbox escalation. No real external-provider credentials are used by fixtures. Frontend `npm.cmd run typecheck`: exit 0.

### GE-10.2 — Idempotent bounded feedback submission (continued)

- Base `5f2bab2`; retained Claude's implementation and 31 tests. Initial fresh regression: `uv run --locked pytest -q -p no:cacheprovider tests/test_feedback.py tests/test_feedback_privacy.py tests/test_guest_inflight.py tests/test_guest_budget.py tests/test_guest_permissions.py tests/test_guest_contracts.py` → **1 failed, 171 passed** (152.77s). The operation inventory correctly rejected the two new unclassified feedback routes; explicitly classified both as personal.
- Added RED `test_temporary_storage_failure_is_retryable_and_sanitized`: **1 failed**, expected 503 but observed 500. GREEN: map transient OperationalError/pool timeout to sanitized retryable 503 in feedback route transactions; unexpected programming failures still use the existing sanitized 500. No SQL/body/credentials are returned or logged.
- Final same regression command → **173 passed** (128.38s), includes the new 503 regression; real PostgreSQL concurrency/idempotency/expiry rollback, strict bodies, guest/private/registered permissions, detached budget and HTTP/SSE boundaries. Claude's prior mutation evidence remains attributed historical evidence, not re-claimed as executed by Codex.
- `uv run --locked ruff check app tests evals alembic` → all checks passed; `uv run --locked mypy app` → clean (111 files). `uv run --locked python ../scripts/export_openapi.py`, `npm.cmd run contracts:generate`, `npm.cmd run typecheck` → exit 0. `python scripts/check_docs.py` → PASS (53 docs, 106 operations, 68 settings, 48 tables); `python scripts/check_reviewed_artifacts.py` → PASS (9 historical pinned approvals); `git diff --check` → exit 0.
- Ruling: `submit_feedback(..., request=..., app_version=...) -> (receipt, created)` instead of a precomputed network key — the HMAC is bound to the fresh database-time window. Attempts commit separately so refusals count; accepted counters/feedback/receipt share the final guest-authorized transaction. Guest second submission 409; registered Bangkok daily limit 429 + Retry-After, as required. Server `RELEASE_VERSION` is validated deployment metadata; no client-stamped version. Cost if wrong: API/service consumers must retain these documented signatures.
- D03 is unresolved; collection flags remain false. Known temporary storage failures now satisfy the planned 503 contract; no deviation is needed for them.

### GE-10.3 — Unlink receipts and enforce bounded retention

- Base `f63324c`. RED `uv run --locked pytest -q -p no:cacheprovider tests/test_feedback_retention.py tests/test_feedback_privacy.py` → **5 failed, 55 passed**: missing retention module, scheduler kept expired feedback, registered tombstone kept its receipt. The guest purge already passed through its schema cascade; explicit receipt deletion was still added to the reviewed inventory path.
- Implemented `purge_feedback(db, batch_size=500)` using one fresh DB clock, inclusive 180-day feedback / 30-day registered-receipt cutoffs, bounded ordered SKIP LOCKED batches. Feedback deletion cascades review events and receipts; receipt deletion preserves feedback. Explicit receipt deletion in guest purge and registered account-scope deletion. Normal retention invokes it independently of both flags.
- GREEN/regression `uv run --locked pytest -q -p no:cacheprovider tests/test_feedback_retention.py tests/test_feedback_privacy.py tests/test_guest_cleanup.py tests/test_data_lifecycle.py tests/test_retention.py tests/test_guest_cleanup_recovery.py` → **89 passed** (46.86s). Includes exact cutoff (+1µs retained), bounded/repeated purge, scheduler with flags off, registered tombstone separation, full guest/provider/attempt reference unlinking, lease/retry/canary regressions.
- `uv run --locked ruff check app tests evals alembic` → clean; `uv run --locked mypy app` → clean (112 files); `python scripts/check_docs.py` → PASS (54 docs); `git diff --check` → exit 0.
- Added `feedback-operations.md`: receipt-based identification without account lookup, separately reviewed content-free redaction, backup quarantine and replay of reviewed redactions. No hosted redaction/deletion/restore. `purge_feedback` returns feedback rows removed, with receipt aging independent; rejects batch sizes outside 1–500. D03 still blocks public collection.

### GE-11.1 — Independent live feedback-admin gate

- Base `141cb81`. RED `uv run --locked pytest -q -p no:cacheprovider tests/test_feedback_admin.py -k 'role or reauth or flag'` → **4 failed** (missing routes/gate). Implemented `require_staff(..., feature='feedback')`, independent flag, and `assert_feedback_admin`: eligible current registered actor, current admin role, DB-time 12h password step-up, refreshed session and owner → StaffRole lock order for mutations. Moderation defaults remain unchanged.
- GREEN and required regression `uv run --locked pytest -q -p no:cacheprovider tests/test_feedback_admin.py tests/test_moderation_admin.py tests/test_auth_flows.py tests/test_guest_permissions.py` → **83 passed** (71.03s) before GE-11.2 additions. Includes forged guest role, normal/moderator denial, stale reauth, flag independence, suspension/ineligibility, revocation after an owner-lock barrier with no write/event.
- The barrier test directly exercises the produced gate before a test write; HTTP PATCH/dual-admin coverage is added by GE-11.2, its owning task. No role-assignment API or client metadata authorization was added.

### GE-11.2 — Bounded consistent review metrics and versioned status

- RED `uv run --locked pytest -q -p no:cacheprovider tests/test_feedback_admin.py -k 'filter or summary or review or cursor'` → **5 failed**, missing summary/PATCH and unvalidated cursor. Implemented shared bounded predicates, Bangkok half-open date windows (default 30d/max 180d), strict filter-bound base64url cursor, descending timestamp/UUID pagination, exact category/kind/rating/status/version filters and explicit spam behavior. Metrics include sample count/null empty mean, five rating counts, multi-select categories, kinds, Bangkok dates and at most 50 version buckets (`(other)` explicitly aggregates overflow beyond 49 named versions).
- Additional RED `test_summary_keeps_one_cohort_during_concurrent_review` → count 1 but distribution sum 0 after a concurrent status change. Fixed by a read-only REPEATABLE READ transaction for summary. Initial test setup needed the fully qualified SQL pattern; an intermediate ARRAY `contains` attempt was unsupported on the existing generic ARRAY type and was replaced with parameterized SQLAlchemy `any_` expressions. No failed assertion was weakened.
- PATCH revalidates locked live staff before and after resource waits; CSRF/key/version required, stale 409, same-version/status no-op, replay has one audit event, dual-admin race yields one 200/one 409. Stored idempotency receipt contains only resource ID/version; audit contains no comment copy.
- Final required regression command above → **91 passed** (82.90s). `uv run --locked ruff check app tests evals alembic` / `uv run --locked mypy app` → clean (114 files). Offline OpenAPI export, `npm.cmd run contracts:generate` and `npm.cmd run typecheck` → exit 0. DTO collision with existing activity FeedbackInput is resolved through the generated namespaced schema, preserving both APIs. `python scripts/check_docs.py` → PASS (109 operations); historical reviewed-artifact check → PASS; `git diff --check` → exit 0.
- Measured EXPLAIN ANALYZE/BUFFERS with 2,000 synthetic rows inside a rolled-back loopback transaction: date page uses existing created_at index (0.048ms); status page existing status index + top-N sort (0.676ms). Raw plan is in OS temp, not committed. First measurement failed before connection due to Windows Proactor; using SelectorEventLoop (as repository fixtures do) succeeded. No evidence justifies adding an app-version index at this scope.
- Ruling: GE-11.1/11.2 commit together because the same admin route/test/inventory files were extended through their sequential RED/GREEN gates; per-task evidence above remains distinct. Read summary snapshots are an implementation refinement required for consistent metrics under concurrent review. Cost if wrong: the two API tasks are reviewed/cherry-picked as one group; snapshot reads retain their initial cohort until that short request ends.

### GE-12.1 — Voluntary accessible feedback form (UI verified; integrated check queued for GE-14.1)

- Base `bb41d6c`. Browser RED: `npm.cmd exec -- playwright test --config playwright.owned.config.ts feedback.spec.ts --grep 'rating-only' --reporter=list` → **1 failed**, form/submit route absent. Implemented lazy feedback route, native unselected required radios, optional checkboxes/plain textarea, 1000-codepoint count, proposed retention notice only behind feedback capability, busy/retry/error/receipt states, own-state duplicate suppression and no persistent draft. No-session route explains trial/login before private Shell; existing public footer and new settings entry link to it.
- Initial form suite → **9 passed** (18.6s). Additional RED malformed-success test → **1 failed** (UI thanked without a valid receipt); added runtime receipt validation. Final `... feedback.spec.ts --reporter=list` → **10 passed** (19.2s): exact minimal payload, native keyboard selection, Unicode 1000/1001, text-only markup, same-key/body 503 retry, busy suppression, expiry clearing, disabled/already-submitted, identity-free unauthenticated entry, 320/390/1440px + 200% text + axe. No external providers. Manual screen reader and visual inspection remain for integration QA, not inferred from axe.
- `npm.cmd run typecheck`, `npm.cmd test` → **84 passed**, `npm.cmd run build` → exit 0; feedback separate chunk 5.18kB, initial chunk 318.79kB. Impeccable detector on form/CSS → `[]`. Used existing CSS tokens/native controls and React lazy loading; UI UX Pro Max form/label/keyboard guidance and current Vercel web guidelines reviewed. The approved blueprint supplies design authority; no new product interview/redesign.
- Remote read retried with sandbox escalation: `git ls-remote origin refs/heads/main` still **984753389aa8bd4b3112b19a8beceb1e538fd659**. Worktree/common-dir checks confirm existing linked isolation, no submodule.
- Ruling: pulled the owned Playwright artifact-root override forward from GE-14.1 so new browser runs write only under `MOODPRINT_TEST_ARTIFACT_DIR` in OS temp. Remaining hardcoded suite paths stay assigned to GE-14.1. No `.gitignore` change.
- Ruling: GE-12.1's named fullstack guest test requires the synthetic anonymous provider/CAPTCHA explicitly assigned to GE-14.1. Preserve the mandated task order: commit verified UI now, run/add that integrated guest submit→purge→retained-feedback oracle with its harness in GE-14.1, and do not claim integrated completion before then. Cost if wrong: fixture proof precedes actual HTTP proof; this is an explicit local gate, not a release pass.

### GE-12.2 — Protected feedback dashboard

- Base `07b58b3`. RED owned browser `feedback-admin.spec.ts --grep 'admin sees' --reporter=list` → **1 failed**, dashboard heading/route absent. Implemented lazy admin view with current registered-admin UI gate (server remains authority), independent step-up without logout, URL-backed shared filters, sample/mean/distributions/categories/kinds/date/version metrics, literal escaped comments, versioned status and bounded cursor loading. No private-history drilldown or chart dependency.
- Initial suite **6 passed / 1 failed**: native disabled status button lost focus while awaiting PATCH. Used `aria-disabled` with an execution guard so the visible control retains focus and cannot submit twice. Required combined owned run `feedback-admin.spec.ts admin.spec.ts feedback.spec.ts --reporter=list` → **20 passed** (37.7s), including conflict reload/focus and revocation clearing comments. Added supplementary transient-read/retry and next-cursor cases.
- Visual review of actual OS-temp screenshots (desktop admin and 320px form at 200% root text) found a verbose visible UUID label and raw context enum; translated contexts and made the per-row label SR-only. The 320px regression then caught width **1170 vs 320**: the absolutely positioned hidden label used an outer containing block beyond its scrolling table. A relative containing block on that region fixes the cause; no page overflow suppression or assertion weakening. Final owned `feedback-admin.spec.ts --reporter=list` → **9 passed** (19.3s), including 320/1440, reduced motion, 200% root font, keyboard, axe and fresh screenshots. Desktop final screenshot inspected. Manual screen reader/soft keyboard/browser text-zoom remain explicit external/manual gaps.
- Backend `uv run --locked pytest -q -p no:cacheprovider tests/test_feedback_admin.py` → **10 passed** (12.83s). Frontend typecheck/build → exit 0, dashboard lazy chunk 8.95kB, initial 318.79kB; detector → `[]` before the final label/containing-block polish. Documentation check PASS; diff whitespace clean. Screenshots/traces remain under temp; no generated evidence committed.

### GE-13.1 — Resolve the conditional spotlight gate (deferred)

- Base `ecb124b`. Exact npm metadata/pack for Driver.js **1.10.2 MIT**, integrity independently matched SHA512; checked all 26 archive paths/types, license, scripts and shipped TypeScript declarations before same-origin bundle/CSS use. No package or lockfile change; no installation scripts.
- RED opt-in `onboarding-compatibility.spec.ts --grep 'one overlay' --reporter=list` without fixture → **1 failed**, explicit missing inspected fixture. Final opt-in run with inspected fixture → **3 passed / 2 failed** (15.5s): repeated setup/cleanup, Escape/focus, reduced-motion narrow pass; real native dialog leaves the popover; Vite cannot satisfy the actual serving-mode CSP gate. Corrected an ambiguous dialog locator, then reproduced the actual overlay-count failure without weakening it.
- Ruling: **defer spotlight**, keep Driver absent and flags off, implement inline guidance in GE-13.2 as explicitly allowed. The optional unaccepted-candidate spike is run only with `MOODPRINT_TOUR_COMPATIBILITY=1`; normal product tests cover the shipped inline controller instead. This does not exempt any security/product regression. Cost if wrong: spotlight remains unavailable until a guarded adapter, both CSP modes and the complete manual/device matrix are proved.
- `tour-compatibility.md` records exact integrity, commands, observed limits and future acceptance criteria. Manual SR/soft keyboard, actual React adapter remount and full routing/GSAP/CSP candidate proof are not claimed. Added only the approved TourStep/TourAdapter type contracts for the next task.

### GE-13.2 — Optional route-aware inline guidance

- Base `8b3df75`. RED `npm.cmd test -- src/features/onboarding/tourSteps.test.ts` → missing state module; owned browser `onboarding.spec.ts --grep 'Next Back'` → **1 failed**, launcher absent. Implemented four approved steps, optional eligible registered-adult fifth contract (never guest), RAM-only guest state, versioned registered preference, explicit settings launch, skip/back/next/finish/replay/Escape, content-free activity registry, bounded two-frame/3s target readiness and complete abort/observer/listener/focus cleanup.
- Controller is lazy and inline (no Driver/custom overlay). With the default-off product flag it remains a readable ordered guide. Enabled local fixture navigation requires an explicit Start, checks blockers/dialogs/session epoch, cancels on Back/unrelated navigation/flag-off, skips a later missing target and refuses a missing first target. It never reads target/private text, changes consent or issues a write. AI/voice/mood/feedback drafts register blockers; expiry clears registry and unmounts the controller. Stable targets added to existing intro regions. Guest settings no longer query or promote registered-only publication/MATCH controls.
- Initial browser result **8 passed / 2 failed**: a test pressed a still-disabled keyboard control before readiness, and the new mood fixture used `average` instead of the actual DTO `mean`/date fields, crashing that fixture route. Corrected synchronization/fixture contract without changing assertions; then **10 passed**. Additional RED saved-mood case → **1 failed**: deriving dirty state during initial server hydration falsely stopped the guide. Changed blocker tracking to explicit user edits/saving; genuine unsaved mood remains protected. Required combined `onboarding.spec.ts guest-expiry.spec.ts real.spec.ts auth.spec.ts --reporter=list` → **58 passed** (1.6m).
- Added transparent-target RED → **1 failed** (zero-opacity geometry was accepted). Readiness now rejects hidden/inert/zero-opacity ancestors and watches those attributes. Added closing/expiry while waiting, real app AI request held at synthetic SSE, pending synthetic microphone permission, later missing target, no-mutation/route/draft preservation and extra responsive cases. Final owned `onboarding.spec.ts --reporter=list` → **18 passed** (50.6s); normal product assertions remain intact.
- `npm.cmd test` → **89 passed** (18 files), `npm.cmd run typecheck` / `npm.cmd run build` → exit 0. One test-only ElementHandle `Node.remove` typing error was corrected to HTMLElement before the final pass. Tour chunk 8.94kB, initial chunk unchanged 318.79kB. New module formatted; detector → `[]`; documentation check PASS and diff whitespace clean. Actual 390/1440 screenshots inspected, artifacts remain in OS temp. Manual SR/device keyboard/real media and actual browser text zoom are not inferred from root-font/axe fixtures; spotlight remains deferred.

### GE-14 work in progress — integration, capacity and pending release review

- Base `51bab82`. Added three actual HTTP/PostgreSQL fullstack journeys. RED: **3 failed** (entry closed / missing synthetic anonymous Auth). Extended only `tests.e2e_server`/`LocalAuth` and a separate `vite.fullstack.config.ts` with same-origin synthetic CAPTCHA. No fullstack request interception, production test route, provider key or external provider call. Final selected run **3 passed** (21.0s); full fullstack regression **31 passed** (6.2m), log `$TEMP/moodprint-guest/ge14-fullstack-all.log`.
- Guest settings now explain the trial deadline, export uses an explicit dialog and `guestConfirmation`, excludes social, partial deletion confirms, account control calls the existing end-trial dialog, voice explains lifetime/clip limits. Registered flows preserved. Artifact-root helper RED (missing helper) → GREEN **2 tests**; all known reporter/screenshot legacy destinations honor `MOODPRINT_TEST_ARTIFACT_DIR`. Unrelated existing artifacts remain untouched.
- Full owned browser run **255 passed / 1 failed** (8.5m): definitive CAPTCHA retry lost its widget. Added deterministic RED: StrictMode inserted **2** scripts, expected 1. Shared loader promise now loads exactly once, clears failed loads for retry; targeted guest/expiry suite **20 passed** (33.9s), including new late SSE final and exact `multiple tabs` oracle. Frontend typecheck, **91 unit tests**, build clean; initial chunk 318.79kB.
- Queued/replayed real completed-run SSE regression **2 passed**: delay sits inside the outer output guard; final private frame suppressed at real DB T, one model dispatch. Three mandatory provisioning aliases were added to the original test module without removing its existing tests. An accidental replacement was caught by diff inspection and corrected before commit; no reduced coverage is accepted.
- Ruling: reset only synthetic admission counters between isolated fullstack scenarios, while backend admission tests retain all default limits; fullstack is not a proof of upstream burst capacity. Near-expiry fixture seeds a pre-existing lifecycle whose T0 is in the past and T=T0+7200, never changes a deadline or disables a trigger. Separate public signup proves a fresh full two-hour lifecycle. Ordinary registered identity is independently seeded, not a claimed hosted signup/transfer proof.
- Pending SQL tooling RED **2 failed**, then **2 passed**. Offline 0015→0018 pending SQL: **32061 bytes**, SHA256 `4a5abfbfc6ab09d0ba7ab01dd65bcacea2598abcb07fa12a7da1ffcbbba47606`, under `$TEMP/moodprint-guest/pending-0015-0018.sql`, not approved/pinned. Local empty-review rehearsal **PASS**, DDL rolled back, runtime CRUD/API-role denial/provider helper/expired guest checked. Initial seed failures (required raw-SQL defaults, schema-denied privilege probe) corrected; historical approvals unchanged.
- Environment interruption: initial full backend run was terminated at ~45% with no final result; **NOT a pass**. Docker subsequently had no engine/container at the expected disposable target. Started installed Docker Desktop hidden, observed the old synthetic container absent, stopped only the two owned pytest process trees waiting on that missing DB, created a new loopback-only `moodprint-guest-impl-db` from the same pinned pgvector image and recreated disposable DBs. Other existing containers untouched. A fresh complete backend run remains required.
- GE-14.2 scaffolding is uncommitted and not yet executed: 50-guest one-worker workload, unchanged global 10 AI / 3 STT caps, real PCM route, registered canary, owned kill/restart, detached liability and physical pg_dump→quarantined pg_restore. Safety gate RED (missing module) → **1 passed**. Restore test and complete load runs still pending; no capacity success claim.
- Remaining: finish GE-14.1 full backend/owned/matrix verification and commit; execute/diagnose both 50-visitor loads plus crash/restore; finish G0–G6 release/rollback docs, Linux/proxy/image/package checks, exact mandatory oracles, independent whole-branch review and fixes. Keep all flags false and branch/worktree intact; D01–D04/manual/hosted gates remain open.

### GE-14.1 — Integrated journeys and final authorization regressions

- Fresh full backend `uv run --locked pytest -q -p no:cacheprovider` on explicit local unit DB → **960 passed, 1 skipped** (1246.03s). The skipped test is the owner-target-gated hosted compatibility probe; no PostgreSQL test was skipped. Exact 21 backend commands from the 25-row matrix each exited 0 on a separate local DB; per-row logs/results in `$TEMP/moodprint-guest/oracles/`. Four browser row commands run separately, not inferred from the fixture suite.
- Final fullstack after extending synthetic ordinary signup/login and explicit memory approval → **31 passed** (7.6m). Signup while guest leaves the guest identity unchanged; logout ends it; ordinary password login creates a distinct registered app identity with empty moods. Synthetic confirmation is provider-side fixture behavior, not hosted email verification. Proposal creation is a test-only seed; approval/listing uses production routes. These supersede the earlier seeded-registered-only integration ruling.
- Second full owned run → **254 passed, 2 failed**. The onboarding trace proves two JS module requests failed with `ERR_NETWORK_CHANGED` before React mounted; no onboarding logic/assertion/timeout was changed. The SSE failure led to a distinct deterministic RED: focus refresh held at the network reset the UI timer because the parent callback identity restarted the effect. `useGuestLifecycle` now keeps a monotonic bound and takes the minimum of every observation; re-renders/delayed replies can only shorten a lifecycle. Focus-refresh regression and late SSE now pass; combined expiry/onboarding → **28 passed** (1.1m), including the unchanged transparent-target test. Complete owned rerun remains the final browser gate.
- Node22/Linux web image RED: `src/artifacts.test.ts` imported a test helper absent from production build context. Moved the test to `tests/artifacts.test.ts` and included that exact file in Vitest; no production test fixture copy. Web image GREEN. Latest frontend generated contracts/typecheck, **91 unit tests**, build all exit0; initial318.79kB. Contract/.gitignore diff empty; original nine audits byte-identical; remote main rechecked at `984753389aa8bd4b3112b19a8beceb1e538fd659`.
- Ruling: owned Vite/fixture, actual HTTP+PostgreSQL/fake-provider and hosted proofs remain distinct. No auto-retry, timeout relaxation or assertion removal hides the observed infrastructure/module failure. Packaging/proxy smoke can accept explicit review image tags so existing `:ci` tags are not overwritten. Unrelated untracked evidence/plans preserved.

### GE-14.2 — Bounded 50-visitor load and durable recovery

- Safety gate RED missing runner → GREEN; quarantine/review/rollback targeted suite **5 passed**. Ran exactly one worker/50 visitors, sequentially and without other test suites: registered baseline **PASS**, guest normal **PASS**, guest `--crash-kill` **PASS**. No user-count/cap/timeout change to force a pass. Owned process cleanup only; all output in OS temp.
- Registered baseline:50 validated completions; non-AI p95 1433ms, AI p95 9773ms, RSS192856064 bytes. Guest normal:50 private browse/write/read/conversation flows;10 AI202+40 clean429,3 STT200+47 clean429,10 SSE finals; registered canary successful. Actual provider concurrency peaks8/2 (normal),10/3 (crash), configured caps10/3. No500/privacy mismatch, cleanup observed9.828s, detached liability186315 synthetic nano-USD remains after purge.
- Crash: kill the admitted owned worker, restart, **zero provider replay**; expire cohort, deny all50 sessions and purge while registered canary remains live. Physical `pg_dump -Fc` beforeT → new local `pg_restore` target afterT, no listener exposed; quarantine runs denial/reconciliation/purge/retention, expired+anonymous remaining0 and provider replay0. Dump and uniquely named synthetic restore DB retained as evidence. [Capacity record](capacity-recovery.md) contains latency/pool/RSS/backlog/cleanup limits and scope; no production/paid-concurrency guarantee.
- Hardware observed: Windows host12 logical processors/15.7GiB RAM, Docker Desktop Linux PG17/pgvector0.8.2, Python3.12.13 driver. Actual deployment headroom and D02 remain unapproved.
- Pre-commit interface review removed a reverse dependency from the load CLI to the later GE-14.3 verifier: it now uses the existing test-target validator and independently refuses query overrides. Targeted restore/safety **2 passed** and Ruff clean. No workload parameter/assertion changed; the three measured50-visitor results remain scoped to the same workload implementation.

### GE-14.3 — Pending release and compatible rollback (verification in progress)

- Generator/verifier preserve all historical SQL/MANIFEST, refuse unsafe targets/paths/overwrites, compare exact offline bytes and remove only the exact Alembic transaction scaffold. Local runtime CRUD/API-role denial/helper/expired-session rehearsal PASS with rollback. Additional real-DB RED found public-schema data was not considered nonempty; verifier now refuses all non-system relations and unsafe existing runtime groups. Regression GREEN: **3 passed**; sentinel unchanged; empty-review rehearsal PASS again. SQL checksum remains `4a5abfbfc6ab09d0ba7ab01dd65bcacea2598abcb07fa12a7da1ffcbbba47606`.
- `alembic upgrade head/current/check` on a separate fresh DB →0018, no model drift. Docs58 files/401 links/109 operations/68 settings/48 tables PASS;9 pinned historical approvals PASS. Exact CI lint from backend PASS, mypy114 files clean, npm audit0 vulnerabilities. A root-cwd Ruff invocation selected different inherited rules and failed; corrected to the CI backend cwd, no unrelated edits.
- API and web Linux images built, Compose/Caddy validate PASS, real proxy shell/CSP/callback/API statuses/SSE timing PASS. Linux network-disabled poller/release-gate **14 passed**. Actionlint exact CI digest PASS with explicit workflow paths (minimal mount has no Git root). Combined image/export, final owned browser run, final package inspection and independent whole-branch review still pending at this ledger point.
- Supplementary release/quarantine/rollback/hosted-gate selection → **19 passed, 1 skipped**, explicitly D04 missing approved target. This includes the new public-data refusal regression added after full-suite collection. Browser matrix: row3 **1 pass**, row19 initially selected0 (titles omitted `callback`), then exact preserved callback tests renamed for discoverability → **3 pass**; row20 **11 pass**; row21 initial17/18 due duplicate end-trial buttons during route transition, narrowed locator to the intended guest-status region → **18 pass**. All25 commands now select meaningful tests and pass; no assertion removed or timeout changed.
- Added narrow integrated UI evidence:320px guest export confirmation has zero horizontal overflow/axe violations;390px fake-device browser microphone produces real worklet PCM, actual upload returns editable preview, explicit placement fills the draft and **zero** messages are sent. Selected three journeys → **3 pass** (36.1s). No real microphone/provider access. The fullstack launch flags apply only to the disposable test harness.
- Final package: API/web/combined Linux images all built; inspection via explicit Python subprocess argv proves API/combined UID10001, no.env/no test entrypoints, combined static index and web no source maps. Initial inline PowerShell→sh UID check had quoting errors; not counted as pass, corrected argv inspection succeeded. Node22.16/Linux frontend units **91 passed** (19 files). Combined image IDs are in the release package. Final full owned rerun and independent review remain before completion.

### Whole-branch independent review and one author fix pass

- Dispatched one fresh-context `gpt-6-astra` reviewer read-only on `9847533..6b367ec`, with the exact spec/plans/Review Focus and every ledger ruling. It sent eight concrete Important findings before a service usage-limit failure prevented the final report/verdict/complete declined-scope list. [Review record](code-review.md) preserves that limit and each disposition. No clean independent verdict, second review seat or completed report is invented. Final review remains PARTIAL even after verified fixes.
- Pre-fix final owned run **257 passed** (7.6m); all25 exact mandatory commands pass with individual evidence and manifest. No skipped DB assertions. Review findings still took precedence over these passes.
- Regraded all eight findings Important by effect and reproduced them before implementation. Initial review backend test file **9 failed**; malformed-graph purge **4 failed**; guest end/logout browser **2 failed**. Fixed query embedding funding/flag gates and per-call accounting, final document deadline/cancellation, locked ORM refresh for settlement, terminal dispatch fencing,45s claim heartbeat, truthful end errors and explicit destructive confirmation, registered child-evidence purge detection.
- Query embeddings share the existing embed operation kind/admission lock/rate/global cap and detached pricing, but do not increment the20-document growth counter. Stable run-scoped query keys prevent replayed paid dispatch; input digest only, no raw query stored in coordination. If semantic/price/budget admission is closed, approved memory uses lexical retrieval without an external call. Registered semantic behavior unchanged.
- GREEN broad `tests/test_guest_review_regressions.py tests/test_guest_quotas.py tests/test_guest_budget.py tests/test_guest_embeddings.py tests/test_guest_paid_dispatch.py tests/test_guest_cleanup.py tests/test_voice.py tests/test_embeddings.py` → **81 passed** (89.91s). Query funded replay adds one known11-nano synthetic charge; document count stays1. An initial document guard compared an extra data_version field against the intentional3-field semantic snapshot; corrected before GREEN, and funded-query preconditions now require an actual indexed memory to avoid a vacuous fallback test. One owned paused fixture process was stopped after that diagnostic; no pass claimed for the interrupted run.
- Heartbeat added for AI/STT/embed, renews only current owner/token/nonterminal unexpired claims every5s, caps at T, never recreates a missing link. Stolen-fence test behavior already denied; corrected its DomainError code expectation. Additional RED blocked DB renewal exposed an unbounded wait; heartbeat now uses a conservative monotonic cutoff from the existing lease, so DB/pool/owner-lock stalls cancel work before the slot reopens. Complete final review file **13 passed** (40.54s), Ruff/mypy114 clean.
- Guest end errors preserve confirmation/private lifecycle with an honest error; a confirmed204 is required for the accepted end screen. Settings guest control calls that same confirmation; registered logout unchanged. Targeted auth/guest/expiry browser **33 passed** (52.4s), frontend typecheck/**91 unit tests**/build clean. Minor deferred: confirmed end-and-register requires an extra Create account click from the ended screen; no data transfer. This is explicitly retained for owner review rather than expanding the fix pass.
- Ruling: local safe implementation and tests continue despite the review service quota limit; release and independent final verdict remain PARTIAL. D01–D04/manual/spotlight/hosted holds unchanged. No root budget, paid provider, hosted action, push/merge/deploy or approval flow was introduced.
- Final from the completed fix-pass source: `uv run --locked pytest -q -rs -p no:cacheprovider` → **978 passed, 1 skipped** (1096.73s); only skip is the D04 hosted target gate. Owned browser → **259 passed** (9.2m); actual HTTP/PostgreSQL fullstack → **31 passed** (7.1m). The earlier in-progress backend run predating the blocked-heartbeat cutoff was stopped by verified owned PID and replaced with this complete run; never counted as pass. No assertions/caps/timeouts were relaxed.
- Rebuilt API/web/combined Linux images as `*:guest-review-final`; all build commands exit0 and inspection proves UID10001/no.env/no test entrypoint/static index/no maps. Final local IDs recorded in [release package](release-readiness.md). Normal50/crash50 workloads are rerun sequentially after all suites stopped to refresh capacity evidence after finance/heartbeat changes; final results below.
- Post-fix final normal50 and crash50 load commands both exit0/PASS: actual maxAI10/STT3,10 admitted AI+40 clean429 and3 STT+47 clean429 per cohort, no500/owner leak, registered canary success. Normal cleanup10.547s, crash cleanup+physical restore23.719s; zero provider replay and zero expired/anonymous references in the restored quarantine. Liability remains186315/204915 synthetic nano-USD. [Capacity evidence](capacity-recovery.md) now uses final JSON, keeps original baseline historical and states hardware/synthetic/latency limits.
- Final static/artifacts: exact CI Ruff list plus3 new guest scripts PASS; mypy114 files clean; OpenAPI export/TS generation drift empty. Pending SQL reverified against exact bytes and rollback PASS. Final Node22/Linux **91 unit tests** and final-image Compose/proxy shell/CSP/callback/status/SSE timing all exit0. Docs59 files/408 links/109 operations/68 settings/48 tables and9 historical SQL pins PASS. Original9 audits/.gitignore unchanged; main workspace retains only its original untracked guest docs, feature worktree retains unrelated untracked plans/evidence. No generated browser/media/dump/provider data staged.

### Completion by authorized scope

- GE-14.1 local integration/regressions: **complete**, focused commit `562788e` plus review fixes; exact25 oracles, backend978/1 hosted skip, browser259 and fullstack31 observed green.
- GE-14.2 local capacity/crash/physical quarantine restore: **complete**, commit `e6280ba` plus final post-fix50/50 reruns; baseline registered50 and all capacity/safety assertions retained.
- GE-14.3 local SQL/config/images/evidence/rollback: **complete**, commit `6b367ec` plus final fix/evidence commit. Schema0018/no drift, reproducible pending SQL, existing approvals intact, final Linux artifacts retained. Hosted GE-01.2/D04 not run; no public enablement.
- Independent whole-branch review: **PARTIAL** due reviewer usage limit before final verdict. All8 received Important findings reproduced/fixed/verified in the single author fix pass;1 minor explicitly deferred in [review record](code-review.md). Overall release **PARTIAL/HOLD** for D01–D04, remaining manual/hosted facts and the incomplete independent verdict. Local executable scope **PASS**. Branch/worktree kept; no push, merge, deployment, paid call, hosted mutation or `.gitignore` change.
# Finish/PR/merge run — 2026-10-28

Plan: `../10-codex-finish-pr-merge-prompt.md`. Starting feature SHA
`b8c7efb990447d329599b3bf038430b12aa14084`; fetched remote main
`984753389aa8bd4b3112b19a8beceb1e538fd659`. Expected origin verified.
Original workspace has untracked guest docs; feature has unrelated untracked
`docs/plans/` and `frontend/evidence/`, all preserved. Imported only prompt10 and
the independent review, source/destination SHA-256 identical. GitHub connector
is read-only; authenticated CLI has push permission and all three merge methods.
No ruleset/branch protection exists; all plan gates still apply.

Owned pgvector 0.8.2/PG17 container `moodprint-guest-impl-db` verified at loopback
26432; existing disposable `_test` databases retained. This run's raw artifacts:
`%TEMP%/moodprint-guest-finish`. Focused backend baseline: 59 passed in90.68s
on the dev DB (budget/expiration/provisioning/inflight/paid/review suites).
Frontend typecheck exit0 and existing guest browser13 passed in41.9s.

Pre-flight: Tasks2/3 share financial dispatch/heartbeat boundaries; final
authorization follows awaited markers, with no external I/O under locks.
Tasks5/6 share database-derived time; preserve the immutable 7200-second grant.
Task8 consumes confirmed204 and existing lifecycle invalidation. Task1 must
precede source merge; Tasks9/10 consume exact reviewed SHA and green CI.
Ruling: use this durable evidence ledger and owned OS-temp artifacts instead
of creating a new ignored skill workspace — .gitignore must stay unchanged.
Ruling: follow prompt10's explicit re-review and push/merge authorization where
the generic executing-plans skill prescribes only one review or an approval stop.

| ID | Required regression | State |
| --- | --- | --- |
| REL1 | Hold marker/CLI/workflow both events | RED missing helper → GREEN4 new/18 Linux tests; pinned actionlint exit0 |
| F1 | VOICE/AI withdrawal during upload/dispatch | RED8 disclosures → GREEN10 new/37 targeted tests |
| F2 | Document edit/delete/source/job lease fence | RED5 disclosures → GREEN9 new/68 broad/43 memory-recovery tests |
| F3 | Sample above billing quantum, ceil quota | RED9 → GREEN66 broad/28 boundary+settlement tests |
| F4 | Guest grant/recovery queued past T | RED6 → GREEN6 new/44 inflight+auth+provisioning tests |
| F5 | DB clock vs ahead process clock | RED2 → GREEN5 new/79 expiration+auth+provider+output tests |
| F6 | Guest safe logs, registered observability | RED4 → GREEN5 new/57 runtime+recovery+cleanup+output tests |
| UX1 | One-confirmation signup, honest failure | RED4 → GREEN5 new/38 guest+expiry+auth browser/2 actual HTTP journeys |

Task1 complete: Windows targeted tests4 pass; full Windows discovery cannot
import Linux fcntl, so the complete suite ran in the owned Linux API image with
readonly deploy mount/network disabled:18 pass. Pinned CI actionlint accepts both
workflows. Both release events check the selected commit's marker before
provenance; eligibility defaults false; build/publication/release remain dependent
on eligibility. No live dispatch or AWS operation. Independent wiring review pending.

Task2 complete: `test_guest_voice_revocation.py` uses real consent mutations
and route-stream/dispatch barriers, guest/registered × AI/VOICE. Initial upload
barrier was before body-limit buffering/auth and passed vacuously; moved it to
the actual route stream after authorization, then observed8 failures (provider
called once) and2 controls pass. Final owner-locked transaction checks claim,
marker, consent and original version; withdrawal uses the same owner lock.
The decision commits before external I/O; later withdrawal cannot recall an
accepted send. Pre-send denial rolls back the marker, releases budget and
finishes the claim without reopening consumed quota. Targeted new/paid/voice/
quota/budget suite37 pass in39.64s. A mistyped nonexistent `test_consents.py`
command collected nothing (exit4); corrected suite above is the pass.

Task3 complete: corrected test setup (actual `/memories` prefix and required
retrieval data_version argument), then RED5 provider disclosures/2 controls.
Current owner/job/resource/model/dimension/source/consent/lease checks follow
marker waits; only freshly validated memory text is sent. All documents use the
same internal adapter, including registered documents without guest budgeting;
query tickets remain separate. Unrelated personal data_version changes preserve
valid work. Locks end before provider I/O and publication fencing remains.
New tests9 including registered control/deletion, broad embedding/budget/paid/
review suite68 pass in64.04s; memory/API and AI/guest recovery43 pass in41.68s.
Ruff passes and mypy114 files clean. First broad command named nonexistent memory
and recovery files (exit4, no pass); actual discovered suite names used above.

Task4 complete: RED9 failures showed floored quantum and15000ms quota. Ceil the
original validated PCM duration for billing and milliseconds for quota; no
fractional-millisecond truncation. At <=30s/<=48kHz each sample exceeds float
precision by many orders; exact15/30 integer boundaries remain exact. Supported
8/16/44.1/48kHz tests cover below/at/above15s and exact30/one-sample-over invalid.
Actual route asserts upward quota, full reservation/settlement105 vs210 and
replay single-call. Budget/voice/quota/paid/withdrawal66 pass in57.88s, additional
final boundary+settlement28 pass in26.61s;6 clips/180000ms existing caps retained.
Ruff passed. No price/budget policy or duration response contract changed.

Task5 complete: real ASGI stack queues serialized grant/current-cookie/recovery
responses inside the outer guard; test-only elapsed monotonic offset crosses
the unchanged immutable T. RED3 leaked private responses and3 controls lacked
the bound. GREEN all6 cases; full inflight/provisioning/auth44 pass in54.88s.
One helper installs a DB-sampled GuestDeadline on every live guest session
output. Recovery no longer translates GUEST_EXPIRED into pending. Registered
cookie rejection, one grant/lost-response recovery and end204 remain passing.
Only deletion cookies and content-free expiry reach the client after T.

Task6 complete: RED rejected a DB-valid trial with process clock T+1h and
accepted a legitimately DB-expired app session with process clock behind.
Guest session/suspension comparisons now use fresh database time after the
lifecycle predicate; registered wall-clock/sliding behavior stays intact.
Five new timezone-aware clock/deadline/revocation/end cases and full expiration,
auth flows, provider and output suites79 pass in56.19s. No writes renew guest T;
clock injection exists only in tests, not a runtime setting or endpoint.

Task7 complete: actual runtime caplog success/failure/cancellation/expiry
reproduced run UUIDs in rendered messages and structured arguments (RED4).
Guest-aware source emissions omit activity identifiers while preserving event,
status, duration, progress, tokens and request counters; registered run IDs remain.
All5 new tests plus AI/recovery/cleanup/inflight57 pass in67.61s. Audited other
runtime and embedding emissions: controlled aggregate codes/types only, no raw
exception messages or payloads. D01 historical operational-log retention stays
unresolved; this forward fix makes no claim to erase old logs.

Task8 complete: successful end calls existing lifecycle abort/broadcast/private
unmount, then explicitly clears terminal guest state and selects signup. Ordinary
end/expiry remain terminal; failed/unconfirmed end keeps dialog and retry.
RED4 extra-click failures/1 cancellation control; after fix, first expanded run
failed only2 keyboard assertions using login's label instead of signup's existing
"Mật khẩu mới". Corrected selector, then38 browser tests pass in57.5s.
Frontend typecheck/91 units pass; actual HTTP/PostgreSQL guest journey2 pass
in11.4s (one new confirmed204→signup and existing five-bot/memory/voice flow).
390/1280 screenshots inspected: confirm/signup/error fit, visible keyboard focus,
no horizontal overflow; Escape returns trigger focus. Late session responses
cannot restore private state;503/network ambiguity does not claim success.
Screenshots remain owned temp. Physical keyboard/assistive/mic/hosted gaps remain.

### Task9 — complete branch review and integration checks

Code26ca93d: full backend1042 pass/1 D04 skip (1141.01s), exact CI Ruff/mypy114
clean, npm ci/audit0/contracts/no drift/typecheck/91units/build pass. Full owned
264 pass in8.0m. Default command first timed out600s after256 under competing
build/browser/server work; unchanged sequential rerun264 pass in7.5m. All25
exact negative-oracle commands pass (21backend; browser counts1/3/11/18).
Linux18deploy tests, Node22 91units,3images and Compose/Caddy/proxy/CSP/SSE pass.
Image shell UID check initially hit PowerShell quoting; direct `id -u` and
separate file assertions corrected the command, all pass without product changes.
Fullstack31pass1fail trace504 Outdated Optimize Dep from concurrent Vite optimizer
cache; isolated history rerun1pass. Complete sequential rerun still required.

Fresh independent whole237-file review at26ca93d is complete: CHANGES REQUESTED,
no P0/P1, three P2: R1 original-window signup refund, R2 linked-reservation
retention FK, R3 failed startup repair retry. [Formal scope/verdict](independent-review-26ca93d.md).
R1/R2 RED2 real PostgreSQL failures → first51 targeted pass. R3 test interrupted
when Docker Desktop stopped; stopped only owned test PIDs. Inspected/restarted
the original exited container (recreate attempt125 name conflict, no mutation).
No interrupted command counted as pass. R3 re-run with original code RED1
(repairs1 vs expected2); fixed first=false only on successful repair. Final3new
plus auth/provisioning/budget/recovery52 pass in53.12s. No migration required:
the exact admission DB sample persists in existing signup_started_at; CAS-returning
prevents duplicate/stolen refund. Linked replay fences keep reservation/charge,
other expired counters prune. Original evidence/README/test EOF blanks removed;
prompt09 Markdown hard breaks intentionally preserved.

Final: minor (deferred): forced operation-token tampering between later SDK model
requests is checked by heartbeat rather than reread at each request. Reviewer
found no normal takeover path; normal expiry cancels before lease reopening.
Ruling: preserve this as nonblocking hardening, not expand the authorized fix
pass into unproven fault-injection behavior; residual cost is detection within
the heartbeat interval for out-of-band token tampering. Release remains held.
Later-SHA re-review, complete rerun/load/CI/PR/merge/post-merge gates remain pending.

Scoped review862e036 found an R1 timestamp coupling: original bucket time also
became provider-start/orphan-window origin. Deterministic61s admission delay
RED2 (rejection and successful provider/failed local grant). Corrected by keeping
original bucket sample only in request RAM for definite-rejection refunds, while
sampling provider start separately after admission waits. Missing original sample
retains counts; CAS still gates failed-signup count/refund. No schema/SQL approval
change. Real private orphan helper finds/deletes the delayed successful provider
identity; all5 final-review tests plus auth/provisioning/budget/recovery54 pass
in75.27s. [Scoped review record](independent-review-862e036.md) preserved.
Ruling: open a concrete draft PR while remaining local/CI gates run, to obtain
exact-head Linux CI in parallel; draft is not approval, and merge remains blocked
until all required checks/re-review/50-user recovery evidence pass.

Independent re-review at11538b2: APPROVED for source integration subject to
execution/CI gates; no unresolved material finding. [Approval](independent-review-11538b2.md)
preserves whole-branch scope and all manual/hosted/release holds. Draft
PR20 created with exact head11538b2, full English feature/hold/gap description.

Full backend862e036 completed1044 pass/1 fail/1 D04 skip in1126.19s: deadline
test expected live.terminal atT+150ms, but terminal publication follows awaited
financial settlement. Three unchanged deadline cases isolated pass in18.02s.
Deterministic settlement gate reproduces original terminal assertion RED while
provider is cancelled. Corrected test retains the SAME150ms deadline oracle and
adds an actual provider-cancellation timestamp, verifies no final output during
blocked settlement, then releases and bounds terminal completion separately.
No product deadline, load timing, cap or assertion about external cancellation
was loosened. Reviewer assessed this test-only correction as appropriate;
heartbeat/expiry cancellation race does not require cancel_requested alone.
All inflight20 + final-review5 tests25 pass in47.48s. Exact-head full CI/local
verification remains required; this record does not relabel the failed run PASS.

Final changed deadline case additionally re-run1 PASS8.25s after post-terminal
no-final assertion; no runtime code changed since11538b2. Linux PR CI
40702269445 SUCCESS at11538b2:1047 backend/1 D04 skip453.95s,91 units,264
browser6.1m,32fullstack4.1m,18deploy tests,migration/load/actionlint/images/proxy
and docs/pins/contracts all green. Full job21m48s, original25min bound unchanged.
Sibling push40702226251 failed social-load sessionp95=539.5ms (limit500ms);
same-head PR job passed unchanged. Latest final-head checks must independently
pass, never hide/relax that threshold.

Sequential isolated load11538b2: registered50/1worker PASS (50AI completions,
non-AI p951958.53ms/AI10729.77ms); guest normal50/1worker PASS (10AI+40clean429,
3STT+47clean429,peak10/3,cleanup10.375s); crash50/1worker PASS (owned kill/restart,
physical quarantine restore,replay0,expired/anonymous0,canary success,cleanup+
restore16.86s). Liability186315/204915 synthetic nano-USD retained. No caps,
workload,production deadline or load oracle changed. [Capacity](capacity-recovery.md)
records resource/latency limits; no hosted/paid claim.

Final local images/proxy inspected from11538b2;18Linuxdeploy tests/91Node22
units PASS. Rehearsed exact pendingSQL4a5abfbf hash in empty local review DB:
DDL rolled back/remoteExecuted=false. Migration0018/no drift,9historical pins,
original9audits byte-identical, .gitignore unchanged. Untracked user paths remain.
Final test/evidence-only commit must be reviewed and pass exact-head CI; PR20
stays draft until then. Actual merge/main and post-merge run/release observations
will be reported in PR/final response without a post-merge evidence commit.
