# 10 — Testing and Evaluation Strategy

Principles (from `CLAUDE.md`): baseline first; reproduce before fixing; tests before implementation where practical; real PostgreSQL (never SQLite) for locks/concurrency; never weaken assertions; report PASS only with executed evidence.

## 1. Test layers and commands

| Layer | Location | Command (from repo root unless noted) | Notes |
|---|---|---|---|
| Backend unit + integration | `backend/tests/` | `cd backend && uv run --locked pytest -q` with `TEST_DATABASE_URL` → disposable `*_test` DB | `tests/database_target.py` refuses non-local targets |
| Backend static | — | `uv run --locked ruff check app tests evals alembic` · `uv run --locked mypy app` | |
| Migrations | `backend/alembic` | fresh `*_test` DB: `DATABASE_URL='' DATABASE_MIGRATION_URL=<local> uv run alembic upgrade head && uv run alembic check` | `env.py` refuses non-local hosts |
| Contracts | — | `uv run --locked python ../scripts/export_openapi.py` → `cd frontend && npm run contracts:generate` → `git diff --exit-code -- src/api/generated/schema.d.ts ../backend/openapi.json` (CI) | |
| Frontend unit | `frontend/src/**/*.test.ts` | `cd frontend && npm test` | add pure-logic tests (clock, reducers, projections) |
| Frontend type/build | — | `npm run typecheck` · `npm run build` | |
| Mocked browser | `frontend/tests/e2e/` | `npm run test:e2e` | `page.route` only in tests |
| Full stack | `frontend/tests/fullstack/` + `scripts/test_fullstack.py` | `cd backend && uv run --locked python ../scripts/test_fullstack.py` | real FastAPI + PostgreSQL + Vite + Chromium; SDK fake model; do not edit `frontend/` during the run (Vite HMR) |
| Load | `scripts/load_social_mood.py` | `uv run --locked python ../scripts/load_social_mood.py --users 50 --think 1 --output <tmp>` | synthetic users only |
| Matching evaluation | `backend/evals/matching/` | `uv run --locked python -m evals.matching.benchmark --out evals/matching/report.json` | offline, no provider calls |
| Hosted (approval) | `scripts/test_supabase_fullstack.py` | only with explicit approval | writes hosted fixture data |

Local DB: Docker container `moodprint-ai-memory-pg` on `127.0.0.1:16432`; create a fresh `<purpose>_test` database per run; read the password from the container env, never print it. **Never** let `backend/.env` drive tests or Alembic (it points at the hosted project).

## 2. Test catalog

IDs referenced by [03 §7](03-product-requirements.md#7-traceability-requirement--tasks--tests) and by tasks.

| ID | Layer | Scenario | Pass condition |
|---|---|---|---|
| T-CLEAN-01 | FE unit | Guard: no production import of `mocks/`, `state/`, `domain/`, `pages/`, `companions/{Cards,Companions,scenarios}` | Test fails if any import is reintroduced |
| T-CLEAN-02 | build | Built bundle has no prototype strings (`Mô phỏng`, `bản mẫu`, `fixture=`) | grep count 0 |
| T-CLEAN-03 | static | Package renamed; no `test:e2e:legacy` | grep count 0 |
| T-REG-01 | all | Existing suites (backend 278+, mocked E2E, full-stack 13) stay green | all pass |
| T-AIQ-01 | BE | 61st turn of the day → 429 `AI_DAILY_QUOTA`; next local day → allowed | assertions on status/code |
| T-AIQ-02 | BE | Budget ceiling reached (seed `ai_usage`) → 503 `AI_BUDGET_EXHAUSTED`; ceiling 0 disables | assertions |
| T-MATCH-01 | BE | Each exclusion rule (block either way, cooldown, open room, pending request, teen, MATCH off, stale consent version, invalid profile, inactive 31 d, profile 181 d, restricted) removes the peer | one parametrized test per rule |
| T-MATCH-02 | BE | v2 validation: min/max per facet, unknown tags 422, v1 payload accepted, strictGoal reciprocal filter | |
| T-MATCH-03 | BE unit | Scorer: worked example = 0.690 ± 0.001; symmetry over 1,000 random pairs; bounds [0,1]; missing facets renormalize; reasons ⊆ shared items (property) | |
| T-MATCH-04 | BE unit | Ranking: daily tie-break deterministic per day and different across days; load penalty; cold-start boost; MMR picks diverse set | |
| T-MATCH-05 | BE | `MATCHING_SCORER` v1/v2/shadow; `candidate_references.scoring_version` stored; DTO reports it | |
| T-MATCH-06 | BE static | `matching/*` and `social/retrieval.py` import no private models (`Mood`, `PrivateItem`, `Memory`, `AiConversation`, `AiMessageRecord`, `MemoryProposal`, `MemoryEmbedding`, `IdentityField`, activity models) | AST import scan |
| T-EVAL-01 | eval | Benchmark gate ([05 §12](05-matching-design.md#12-evaluation-datasets-and-benchmark-methodology)) | report shows gate met before enabling v2 |
| T-METRIC-01 | BE | `matching_stats_daily` increments on impression/request/accept; report script suppresses cells < 5 | |
| T-CONN-01 | BE + E2E | Pending request returns `peer` card; card disappears once ineligible (block / MATCH off) | |
| T-CONN-02 | BE | Republish (different interests, different goal) and withdraw keep open rooms, messaging and pending requests; MATCH off still closes; re-enable never resurrects | new tests in `tests/test_connection_durability.py`; existing `test_republish_and_match_reenable_never_resurrect_room` stays unchanged (it only covers MATCH toggling) and is renamed `test_match_reenable_never_resurrects_room` for accuracy |
| T-CONN-03 | BE | Same alias in candidate card, request peer card, connection list, export | |
| T-CONN-04 | BE + E2E | Unread count increments on peer message, resets after `read`; monotonic; summary counts; nav badge renders | |
| T-ACT-01 | BE unit | Machine: every allowed transition; every forbidden transition raises; terminal immutability | table-driven |
| T-ACT-02 | BE | Concurrent invites from both sides → exactly one session; accept vs cancel race → one outcome; idempotent replay returns same view | `asyncio.gather` on real PG |
| T-ACT-03 | BE + full stack | `activity_changed` emitted on each mutation; two browsers see state within 2 s; stream killed → polling keeps parity; reload resumes same round | |
| T-ACT-04 | BE | Block, end, MATCH off, deletion, suspension abort non-terminal sessions and deny access | |
| T-ACT-05 | BE | Invite quotas (6/h per connection, 20/day per user) and decline cooldown → 429 + `Retry-After` | |
| T-ACT-06 | BE | Feedback stored; peer projection never includes it; only after completion | |
| T-ICE-01 | BE | Independent answers; peer sees only `peerSubmitted`; reciprocal reveal incl. skip cases; response conflict 409; mutual ready advance; completion after 3 | |
| T-ICE-02 | full stack | Two users play all 3 rounds incl. one skip; summary on both; feedback | |
| T-QUIZ-01 | BE | `correctIndex` absent before reveal (assert on raw JSON); scoring table (0/1/3 per round); total 15 max; 5 rounds | |
| T-QUIZ-02 | full stack | Two users complete quiz; team score equal on both screens | |
| T-FOCUS-01 | BE unit | Timer math with injected clock: starting→focus→break→done; pause/resume remaining; presence minutes; both-away/pause expiry | |
| T-FOCUS-02 | full stack | Two users start 1×(1 min test plan via `FOCUS_TEST_PLAN_SECONDS` setting allowed only in `APP_ENV=test`), pause/resume, leave/rejoin, summary minutes consistent on both | |
| T-MOD-01 | BE | Non-staff 403 on admin routes; claim/resolve CAS; actions recorded; flag off → 404 | |
| T-MOD-02 | BE | Suspend → sessions revoked, login 403; restrict → discovery hidden, requests/messages/activities 403, rooms closed; lift restores | |
| T-MOD-03 | BE | Report with activity responses: only pair's own sessions, ≤ 2, copied text | |
| T-SAFE-01 | FE unit + E2E | PII advisory dialog appears for phone/email/URL; "Vẫn gửi" sends; "Sửa lại" keeps draft | |
| T-PRIV-01 | BE | Export contains own activity data/read markers, excludes peer answers; deletion removes own answers/feedback/reads and aborts sessions | |
| T-DOC-01 | doc | Privacy notice draft exists and lists every provider and retention row | review checklist |
| T-UX-01 | full stack | Journey: publish → discover → request (sender card) → accept → chat → icebreaker → continue chatting | |
| T-UX-02 | full stack | Viewports 390/430/768/1280/1440 + 390×480: no horizontal overflow; targets ≥ 44 px; axe 0 violations on listed screens | |
| T-UX-03 | mocked E2E | Loading/empty/error/offline/feature-off states for Discovery tabs, Messages, Chat, Dock | |
| T-MIG-01 | migration | `upgrade head` + `check` on fresh DB; offline SQL for 0011–0014 executes verbatim on a restored snapshot; ACL/RLS present for each new table | |
| T-OPS-01 | ops | Restore drill evidence; alarm config validated (JSON parse + dry-run where possible) | |
| T-OPS-02 | staging | Deploy + rollback rehearsal evidence (approval) | |
| T-PERF-01 | load | 50 users, think 1 s, chat + one activity per pair: p95 targets met, 0 integrity failures | |
| T-REL-01 | release | Go/no-go checklist complete with evidence links | |

## 3. Two-actor test patterns (backend)

Use the existing fixtures: `clients` yields `(app, [(client, user_id), (client, user_id)])`; add a third actor with `add_actor(app, 2)` for isolation checks. Reuse helpers from `tests/test_social.py` (`consent`, `publish`, `open_room`) by moving them to `tests/social_helpers.py` (task B-02) so new test files share them.

Race tests: `await asyncio.gather(a.post(...), b.post(...))` against real PostgreSQL; assert DB invariants with direct `select(func.count())`.

Clock control: activity machine/timer functions take `now` explicitly; route-level tests patch `app.modules.activities.service.now` (single import point).

## 4. Full-stack two-browser pattern

Extend `frontend/tests/fullstack/helpers.ts` with `twoUsers()` (two browser contexts, synthetic login via the test server) and `openRoom()` (publish both, request, accept). Each activity spec drives both pages in lockstep and asserts each page's visible state. A stream-drop test uses `page.route('**/events*', r => r.abort())` mid-activity, then unroutes and asserts recovery.

## 5. Matching evaluation methodology

See [05 §12](05-matching-design.md#12-evaluation-datasets-and-benchmark-methodology). Datasets are synthetic and committed; labels record rater IDs as `r1..r3` only. Re-run the benchmark whenever taxonomy, weights or ranking change; attach the report to the PR.

## 6. Beta evaluation

Weekly `scripts/report_beta_metrics.py` (read-only aggregated SQL, approval required to run against hosted), plus 5–10 user interviews. Do not A/B test at N≈50; use shadow logging for scorer comparisons.

## 7. What must never be done

- No SQLite, no mocked database for concurrency tests.
- No live OpenAI/Voyage calls in CI or default runs.
- No hosted writes without approval; no `alembic upgrade` online against hosted.
- No updating tracked visual baselines silently; no weakening existing assertions (T-CONN-02 adds coverage for a reviewed behavior change, DR-03; it removes no existing assertion).
