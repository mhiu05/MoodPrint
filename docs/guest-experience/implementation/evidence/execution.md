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

### Open risk carried from GE-01.1

- Risk (hosted, unverified until GE-01.2): registered login now fails closed if the hosted Auth access token or `GET /user` omits `is_anonymous`; GoTrue is expected to include it, but only the hosted proof can confirm. Do not enable/deploy before G1.
