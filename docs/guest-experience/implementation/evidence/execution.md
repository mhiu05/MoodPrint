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
| 50-user isolated load | `load_chat_memory.py --workers 1 --users 50 --port 8017` (load DB) | see "Baseline load" below |

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

### Open risk carried from GE-01.1

- Risk (hosted, unverified until GE-01.2): registered login now fails closed if the hosted Auth access token or `GET /user` omits `is_anonymous`; GoTrue is expected to include it, but only the hosted proof can confirm. Do not enable/deploy before G1.
