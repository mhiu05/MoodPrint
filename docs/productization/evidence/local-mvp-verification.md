# MoodPrint local MVP verification

Verification window: 25–26 October 2026, Asia/Bangkok. Local development only.
Overall status: **PARTIAL**. No hosted write, migration, deployment, PR or merge.

## Provenance and isolation

Fetched `origin/feat/moodprint-product-experience` before creating the isolated
worktree `.worktrees/local-mvp`, branch `fix/moodprint-local-mvp`, at
`e5c8929336be7ff7a362f31b06162735d7e83a05`. The original checkout stays on
`docs/productization-plan`; the previous product-experience worktree is preserved.
No `.gitignore`, developer `.env`, production secret or dependency lock was changed.
Installed locked dependencies were reused through ignored directory junctions.

The task-owned PostgreSQL container uses `pgvector/pgvector:0.8.2-pg17`, loopback
port 18432. Separate disposable databases isolate backend, browser, migration,
targeted and load checks. No hosted Supabase URL is used as an application test DB.
No agent architecture or matching formula was redesigned.

## 1. Root causes of AI/history states

The old chat UI combined `session.consents.AI.enabled` and
`SessionView.features.ai` into one `allowed` boolean and displayed the same
"AI disabled or unavailable" message for both. `AiRuntime.available` previously
combined the global/development-actor flag, key and model presence into a boolean;
provider failures were reduced to one generic failed-stream message.

The existing root developer configuration reports OpenAI/model/Voyage present,
AI/history on, accounting off, activities off and scorer v1. The previous isolated
worktree reports no provider credentials/model and AI off. These were **presence
checks only**, not credential validation. There was no running original 8001 API
to tie the reported screenshot to an actual process configuration. Therefore the
precise provider validity and configuration loaded by that earlier process remain
unverified; missing consent cannot legitimately be diagnosed as a provider outage.

History defaults off **per user**, despite global `CHAT_HISTORY_ENABLED=true`.
That is intentional privacy behavior. The toolbar previously described any
missing/off preference as "saving disabled", even if the preference request was
still loading or the server capability was off.

A confirmed restoration race also existed: opening an assistant could select the
latest thread before `/ai/preferences` completed, skip persistent threads because
`preferences` was undefined, and never reconsider after loading. The late-response
browser regression now proves the thread opens after preferences resolve.

## 2. Local configuration matrix

See [local setup](../../development/local-mvp.md) and
[`backend/local-mvp.env.example`](../../../backend/local-mvp.env.example).

| Layer | Required local setting / choice | Observed behavior |
|---|---|---|
| Environment | `APP_ENV=development` | Normal local configuration; synthetic harness explicitly uses `test` |
| AI service | `AI_ENABLED=true`, actual `OPENAI_API_KEY`, actual `OPENAI_MODEL` | Required for real provider; no fake fallback |
| Accounting | `AI_ACCOUNTING_ENABLED=false` | Existing user/minute/concurrency/daily admission limits remain enforced |
| History capability | `CHAT_HISTORY_ENABLED=true` | Does not opt a user in |
| Personal choices | AI consent and history opt-in separately enabled | New conversations can persist; old temporary ones are never converted |
| Activities / matching | `ACTIVITIES_ENABLED=true`, `MATCHING_SCORER=v2` | Tested with local state; v1.1 rollback also retained |
| Approved memory | AI + MEM consent; explicit proposal approval | Local persistence/retrieval works without Voyage |
| Semantic memory | Server capability + Voyage key + separate user opt-in | Real worker, query, re-indexing, revocation and deletion verified after authorization |

The example intentionally leaves real keys/model/Auth empty. `check_config.py`
reports variable presence and service configuration status without values or
network calls. `ready` means syntactically plausible, **not** remote validation.
No user-owned `.env` was created, overwritten or copied.

## 3. Implementation

- `AiRuntime.status_for` separates disabled, missing configuration, invalid
  whitespace configuration, ready and explicit test-provider states. Actor-scoped
  development access remains enforced. `features.ai` stays backward compatible;
  `features.aiStatus` adds the reason independently of consent/quota.
- Safe failure classification distinguishes provider authentication/model/request
  configuration, provider rate limiting, connection/outage, timeout and database
  failure. Public stream messages never include provider bodies, SQL or secrets.
  Client code uses an allowlist of safe messages rather than rendering raw errors.
  Error categories follow the documented [OpenAI SDK exceptions](https://developers.openai.com/api/docs/guides/error-codes).
- Chat presents missing consent with a direct settings action. Temporary, new saved,
  existing saved, loading, user opt-out and service-unavailable states are distinct.
  Failure to load preferences prevents accidentally sending under an unknown
  persistence choice. Saved history remains manageable with AI/saving disabled.
- Assistant auto-resume waits for preferences. URL selection and an active stream
  remain stable while the newly created thread receives its URL.
- The synthetic UI explicitly labels fake-model responses. The test-only Auth
  transport exercises real application login/logout, opaque cookies, CSRF,
  provider-token verification and durable session checks with two isolated users.
  It is never installed by the application entrypoint.
- Compose now includes pgvector (plain PostgreSQL could not supply migration 0009's
  extension). The combined Docker build now uses Node 22.16.0, meeting the installed
  Vite/toolchain requirement instead of the old unsupported 22.11.0.
- Retention regression uses a fixed UTC/Bangkok day disagreement. The previous test
  used host `date.today()` against UTC statistics and failed after local midnight.
  The same 364-day keep / 366-day purge assertions remain; product policy is unchanged.

## 4. Five assistants and AI conversations

**MOCK_TESTED + LOCAL_FULLSTACK_VERIFIED.** Mây, Gương, Nhịp, Rủ Rê and Cầu Nối
each create a real PostgreSQL-backed conversation, complete the SDK streaming path,
refresh and restore their messages. A second independently logged-in browser is
denied each foreign conversation. The UI identifies the provider as synthetic.

Five parameterized backend regressions replace the runtime and inspect the next
SDK invocation: correct instructions, correct tools, previous user and assistant
messages, new input, and only eligible approved memory. Nhịp gets the mood-reading
tool only with the existing explicit date scope. Cầu Nối and Rủ Rê cannot access
private-memory tools. Existing SDK tests cover cancellation, timeouts, no automatic
provider replay, guardrails and consent revalidation; these are deterministic tests,
not real-provider cancellation or response-quality evidence.

## 5. Persistent history

**LOCAL_FULLSTACK_VERIFIED.** New users begin with history off. Explicit opt-in,
saved creation, PostgreSQL messages, browser refresh, actual UI logout, a new login,
opening the assistant root without a conversation URL, and continuing the same
conversation all pass. No transcript is stored in browser local/session storage.

The existing history journey additionally passes rename, export, deletion,
read-only management after AI/history withdrawal, mobile history navigation and
keyboard Escape. PostgreSQL tests cover ordered message pagination, expiration,
idempotent sends, concurrent admission, remote cancellation and ownership denial.
Backend context reconstruction after runtime replacement is observed separately.
The live smoke also resumes saved PostgreSQL data in a new API process, logs
out/in and confirms OpenAI recalls the original synthetic marker. A synthetic
crash-recovery harness kills an actual worker and checks interruption without replay.

## 6. Memory

**LOCAL_FULLSTACK_VERIFIED** for approved memory UI: edited proposal approval,
no automatic save, persistence after refresh, editing/deletion and privacy actions.
**MOCK_TESTED** for model tool execution, bounded lexical retrieval, scoped context,
consent withdrawal and external embedding lifecycle. PostgreSQL suite checks stale
versions, duplicate approval, foreign-owner denial, index revocation/deletion and
re-indexing with synthetic embeddings. Five assistant context tests confirm approved
memory reaches only the appropriate bots even without a real Voyage credential.

**REAL_PROVIDER_VERIFIED:** real Voyage document/query embeddings, worker indexing,
approved-memory retrieval, editing/re-indexing, index revocation and deletion pass.
Retrieval is checked through an authenticated aggregate probe in the test-only
entrypoint, calling the unchanged production retriever and exposing counts only.
A live AI answer using semantic memory was not completed; model-facing memory
integration remains deterministically tested. No ranking-quality claim is made.

## 7. Matching

**LOCAL_FULLSTACK_VERIFIED.** Profile draft/edit/preview/publication, consent,
candidate eligibility and explanations, empty/sparse state, mutual acceptance,
stable aliases and existing connections after profile edits are covered by real
API/PostgreSQL/browser tests. Both v2 and rollback `rules-v1.1` browser specs run.
The frozen oracle/vocabulary regression remains intact. No private memory,
transcript, mood or activity answer is used for matching. No artificial candidate
was added to application code.

## 8. Two-account human messaging

**LOCAL_FULLSTACK_VERIFIED.** Separate browser contexts discover each other,
publish reviewed profiles, invite/accept, share the same room, exchange genuine
test-user messages and retain them after refresh. SSE catch-up, polling fallback,
read markers/unread summaries, room termination, blocking, consent withdrawal and
third-party denial are covered. No partner reply is fabricated by the application.

## 9. Shared activities

**LOCAL_FULLSTACK_VERIFIED** for Icebreaker independent answers/reciprocal reveal,
Cooperative Quiz shared questions/server scoring and Shared Focus server timer.
Browser Focus coverage now includes pause by one member, peer-observed pause,
reload while paused, resume by the peer, completion and explicit early stop.
These use independent browser sessions and real local backend/PostgreSQL.

An additional 15-case PostgreSQL matrix checks all three kinds: simultaneous
invitations, duplicate request receipts, exactly one persisted session, expired
invitation refusal, stale versions, outsider denial, ending, blocking and consent
withdrawal. Existing tests retain simultaneous answers, server scoring, locked-room
handling and sweeper races. The first expiry probe incorrectly set a nonmapped
`expires_at` test attribute; it was corrected to advance the real sweeper and assert
the persisted `expired/invite_expired` state before testing refusal. No application
assertion or security gate was weakened.

## 10. Database, migrations and Docker

Fresh local Alembic upgrade applies the entire chain, including 0011–0014.
`alembic current` returns `0014_moderation (head)` and `alembic check` reports no
upgrade operations. PostgreSQL suite includes actual migration/runtime-role and
RLS/privilege tests, concurrency, isolation and database constraints. These local
role fixtures are not a claim about hosted Supabase grants or Auth configuration.

The combined UI/API Docker image builds and runs in `APP_ENV=production`, nonroot
UID 10001, with synthetic Auth configuration and no provider credentials. UI root,
five-bot API, liveness and readiness return 200 on loopback port 18001. Readiness
queries the migrated database and required private Auth helper. Graceful stop exits
0; restart returns ready. Restarting the disposable PostgreSQL container causes an
observed transient `NOT_READY` 503 and content-free worker retry logs, followed by
automatic recovery to readiness 200. The application container is stopped afterward.
This is packaging/reconnection proof, not real hosted login or provider proof.

## 11. Commands and outcomes

Commands run from this worktree using installed `backend/.venv/Scripts/python.exe`
(Python 3.12.13) and locked frontend dependencies. Tests receive only explicitly
assigned local `TEST_DATABASE_URL`; migrations receive a separate local
`DATABASE_MIGRATION_URL`. No command relies on a hosted developer DB setting.

| Cwd | Exact command / scope | Observed outcome |
|---|---|---|
| Root | `git fetch origin feat/moodprint-product-experience` | Latest base fetched before branch creation |
| Backend baseline | `.venv/Scripts/python.exe -m ruff check app tests`; `-m mypy app` | PASS, 86 original source files |
| Backend baseline | `.venv/Scripts/python.exe -m pytest -q --tb=short` | 482 passed, 365.79 s |
| Frontend baseline | `npm.cmd run typecheck`; `npm.cmd test`; `npm.cmd run build` | PASS; 49 tests; entry 490.12 kB / 159.22 kB gzip |
| Backend targeted | `-m pytest -q tests/test_ai_availability.py tests/test_chat_persistence.py tests/test_memory.py tests/test_sdk_adapter.py --tb=short` | 49 passed before later added cases |
| Backend context | `-m pytest -q tests/test_ai_availability.py tests/test_chat_persistence.py --tb=short` | 29 passed |
| Backend activity matrix | `-m pytest -q tests/test_local_mvp_activities.py --tb=short` | 15 passed |
| Backend first broad rerun | `-m pytest -q --tb=short` | 499 passed, 1 host-date retention fixture failure; preserved in local logs |
| Backend retention repair | `-m pytest -q tests/test_retention.py --tb=short` | 4 passed with deterministic UTC fixture |
| Backend final | `-m pytest -q --tb=short` | **515 passed**, 412.57 s, no skipped database checks |
| Backend static | `-m ruff check app tests evals alembic ../scripts/check_config.py ../scripts/test_fullstack.py ../scripts/verify_local_providers.py`; `-m mypy app` | PASS, 87 source files |
| Migration DB | `-m alembic upgrade head`; `-m alembic current`; `-m alembic check` | PASS, 0014, no drift |
| Contracts | `.venv/Scripts/python.exe ../scripts/export_openapi.py`; frontend `npm.cmd run contracts:generate` | PASS, updated service-state contract |
| Frontend | `npm.cmd run typecheck`; `npm.cmd test`; `npm.cmd run build` | PASS, **54 tests**; entry JS 492.39 kB / 159.97 kB gzip, build 6.95 s |
| Frontend HTTP-mocked browser | `node node_modules/@playwright/test/cli.js test --reporter=list --output=.cache/local-mvp/mocked` | 62 passed, 1.3 min |
| Backend / v2 full stack | `.venv/Scripts/python.exe ../scripts/test_fullstack.py --reporter=list --output=.cache/local-mvp/fullstack` (`E2E_MATCHING_SCORER=v2`) | 25 passed, 4.2 min |
| Backend / focused activities | `.venv/Scripts/python.exe ../scripts/test_fullstack.py activities.spec.ts --reporter=list --output=.cache/local-mvp/focus` | 5 passed, 1.5 min, including added Focus pause/resume/stop |
| Backend / final v1.1 full stack | `.venv/Scripts/python.exe ../scripts/test_fullstack.py --reporter=list --output=.cache/local-mvp/fullstack-final` | **26 passed**, 4.6 min |
| Docker | `docker build -t moodprint-local-mvp:verified .` | PASS after correcting Node version; production-mode startup/health/shutdown checked separately above |
| Backend load | `.venv/Scripts/python.exe ../scripts/load_social_mood.py --users 50 --think 1 --scorer v2 --output ../docs/productization/evidence/local-mvp-load-50.json` | Exit 1: functional integrity passes; latency gate fails |
| Provider preflight | `.venv/Scripts/python.exe ../scripts/check_config.py --env-file E:/MoodPrint/backend/.env` | Configuration present; no outbound call, no values printed |
| Initial authorized provider smoke | `.venv/Scripts/python.exe ../scripts/verify_local_providers.py --provider-env E:/MoodPrint/backend/.env --allow-live-openai --allow-live-voyage` | Five real bots, proposal/approval and first Voyage index pass; helper then fails as explained below |
| Bounded provider resume | Same command plus `--resume --model-request-limit 1 --voyage-request-limit 3` | **1 passed, 1 deliberately skipped**: fresh suite preserved rather than repeated; remaining real stages pass |
| Synthetic AI crash recovery | `.venv/Scripts/python.exe ../scripts/load_chat_memory.py --workers 1 --users 10 --crash-kill --output ../docs/productization/evidence/local-mvp-ai-recovery.json` | PASS after Windows permission retry; details below |
| Final focused browser replay | `node node_modules/@playwright/test/cli.js test tests/e2e/chat-history.spec.ts tests/e2e/real.spec.ts --reporter=list --output=.cache/local-mvp/mocked-final` | **28 passed**, 39.3 s |
| Plan integrity | `backend/.venv/Scripts/python.exe scripts/check_plans.py` | PASS, 12 plans / 39 tasks / 43 IDs / 76 links / acyclic DAG |

Local logs are under `.cache/local-mvp/`; generated browser evidence stays in
`frontend/.cache/local-mvp/`. Desktop 1440×960 and mobile 390×844 history screenshots
were visually inspected. Broader journeys check 390/430/768/1280/1440 and 390×480,
keyboard access, reduced motion, overflow and axe WCAG 2.1 AA. Existing tracked
screenshots/reports are restored before commit rather than publishing generated
images or traces.

## 12. Real-provider smoke status

**REAL_PROVIDER_VERIFIED: YES, bounded synthetic-data smoke after explicit owner
authorization for OpenAI and Voyage.** No hosted Auth/database operation occurred.
All five real assistant outputs were reviewed from synthetic local transcripts:
listening, a short paper game, voluntary profile publication, a private emotion
check-in, and an actual proposal tool call without saving before approval.
Saved replies survive refresh.

The first smoke failed because its send helper counted bot messages before a
restored conversation finished loading. The old response could satisfy the count
assertion while a new turn had only just been admitted. The helper now waits for
the send button to be ready before counting old responses. Assertions for actual
Voyage query calls were retained. The fresh suite was **not rerun from scratch**
because that would unnecessarily repeat billable work.

Resume mode preserves only the explicitly selected disposable local database,
starts a new API process and allows just **one** additional model request and
**three** Voyage requests. It verifies real semantic retrieval, edited-memory
re-indexing, another retrieval, index revocation, approved-memory deletion, actual
UI logout/login and OpenAI recalling `LÁ-XANH-47` from the saved conversation.
The authenticated aggregate retrieval probe exists only in the smoke entrypoint.

There are **7 confirmed model request starts** and at most **one additional cancelled
dispatch** not captured by the first final metrics snapshot: **at most 8** overall.
Confirmed received usage is 7,713 input and 453 output tokens; usage for the possible
cancelled dispatch is unknown, not assumed free. Voyage performs exactly **4** real
requests (two documents, two queries). The 1,200-output-token cap is unchanged.
[Aggregate provider evidence](local-mvp-provider-smoke.json) preserves both attempts.
No broad live quality, cancellation, retry or provider-performance claim is made.

The synthetic crash harness separately kills an actual worker holding a turn:
terminal state becomes `interrupted` after 25.0 seconds with a 25-second lease,
zero provider replays and an SSE interruption event. It also checks 30 indexed
synthetic memories, history operations, two explicit cancellations and consent
revocation. [Aggregate recovery evidence](local-mvp-ai-recovery.json) is committed.
Its first Windows sandbox attempt could not perform taskkill; the explicitly
owned-worker test succeeds with the required OS permissions. A stale report
description and hard-coded timeout were corrected to report the actual settings.
This run overlapped functional checks and is not a separate capacity benchmark.
`wall_seconds` covers the main workload, not the later lease-recovery wait; sampled
worker observations include both the killed and replacement process.

**HOSTED_UNVERIFIED:** Supabase Auth/database/RLS, SMTP, hosted infrastructure,
provider production readiness and release procedures were not exercised.

## 13. Performance

Single-worker FastAPI, 50 synthetic authenticated users, local pgvector PostgreSQL,
one-second randomized mean think time, default 8+4 pool, v2. No other suite/build or
task-owned application container was active during this run. The driver performs
moods, profiles, discovery, invitations, chat/idempotent retries, SSE/polling,
isolation probes, consent changes and 25 Icebreakers. No real model is involved.

3,379 requests in 101.36 s (33.3 rps), 25/25 rooms, zero unexpected HTTP statuses,
flow exceptions, integrity failures, discovery misses or transport retries. Peak
pool checkout 12. Instrumentation reports 55,589 SQL statements, 306.945 summed
concurrent SQL seconds and 67.5 API CPU seconds; SQL seconds are not wall time.

| Operation | p50 ms | p95 ms | Original p95 budget | Result |
|---|---:|---:|---:|---|
| Session | 578.5 | 878.1 | 500 | FAIL |
| Discovery | 708.0 | 922.4 | 500 | FAIL |
| Connection invitation | 385.6 | 1497.1 | 800 | FAIL |
| Human message send | 264.8 | 810.8 | 800 | FAIL |
| Activity answer | 97.5 | 326.4 | 800 | PASS |

Other failing p95 operations: connections 519.9 ms, message poll 702.9 ms and
idempotent message retry 803.9 ms. The unchanged thresholds are enforced; the
runner exits 1. Full [aggregate measurements](local-mvp-load-50.json) are committed.

The inherited branch already records 50-user latency failures and query/CPU/pool
pressure. This run again reaches the pool cap with substantial query and CPU work.
No controlled profiler experiment isolates a new bottleneck caused by this patch,
so there is no invented improvement claim and no speculative concurrency/security
rewrite. Capacity remains an outstanding local issue. These measurements do not
establish hosted capacity or a production SLA.

## 14. Remaining local gaps

- 50-user read/write latency gates do not pass.
- Broad live five-assistant quality, cancellation/retry, and a fresh single-run
  replay of the corrected whole provider suite remain unverified. The bounded
  continuation does verify the specific real-provider stages described above.
- Full local Supabase Auth is not installed; the real application auth path is
  exercised against a test-only provider transport, not a real GoTrue server.
- Automated accessibility checks and selected rendered inspection do not replace
  a human screen-reader assessment or a sustained multi-device/network soak.

## 15. Deferred external prerequisites and Git delivery

Keep SMTP, moderation operations expansion, legal/privacy approval, billing-cap
optimization, production monitoring, AWS, hosted migrations and release procedures
for a separately authorized stage. Existing authentication, authorization, consent,
moderation enforcement, reporting/blocking, quotas, isolation, export and deletion
remain in place. No hosted readiness follows from a local PASS or Git push.

The owner should review this diff, the bounded provider evidence and the failing
capacity gate before creating their PR. Delivery is restricted to
`origin/fix/moodprint-local-mvp`; no `main` write, merge, force-push or automatic PR.
The final commit and verified remote SHA are reported in the session's final response.
