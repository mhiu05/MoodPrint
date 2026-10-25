# 01 — Codebase Audit

Audit date: 2026-10-25 · Git revision audited: `5689dd9c725d625acfc7bc3a322548295a29608b` (`main`) · Working tree: only `.gitignore` modified by the user (not touched).

Method: every claim below was checked against source in this session. Older documents under `docs/plans/` and `docs/mvp-validation/` were cross-checked rather than trusted. Commands actually executed in this session are listed in [§9](#9-verification-executed-in-this-session).

Classification legend: **REAL_AND_VERIFIED** (real code path, executable evidence exists) · **REAL_BUT_INCOMPLETE** (real, but missing behavior required for a real multi-user product) · **MOCK_OR_SIMULATED** · **DEAD_CODE** (not reachable from the production entry point) · **MISSING** · **BLOCKED** (needs an external prerequisite).

Severity legend: **S1** blocks a real-user beta · **S2** materially harms the product goal or operations · **S3** quality/maintainability.

## 1. Architecture as built

| Layer | Implementation | Evidence |
|---|---|---|
| Frontend entry | `main.tsx` mounts **only** `features/real/RealApp` (HashRouter) | [main.tsx:3](../../frontend/src/main.tsx#L3) |
| Frontend production modules | `features/real/*`, `api/*`, `components/UI.tsx`, `companions/{Avatar,registry}.tsx/ts`, `styles/*` | import graph traced in this session (see [02](02-prototype-removal-inventory.md)) |
| Legacy prototype | `App.tsx`, `pages/*`, `state/*`, `mocks/*`, `domain/*`, `companions/{Cards,Companions,scenarios}` — reachable only from `tests/harness/legacy-main.tsx` and two unit test files | [legacy-main.tsx:4](../../frontend/tests/harness/legacy-main.tsx#L4) |
| Backend | FastAPI modular monolith, one process, one uvicorn worker; routers mounted under `/api/v1` | [main.py](../../backend/app/main.py) |
| Background work | In-process loops: `sweep_context` (deletions, retention, AI recovery, 1 s cadence) and `embedding_worker` | [main.py:47](../../backend/app/main.py#L47) |
| Database | Supabase PostgreSQL 17, schema `moodprint`, Alembic head `0010_account_deletion`; 32 tables, all RLS-enabled, one permissive `backend_access` policy for `moodprint_runtime`, no anon/authenticated grants | hosted `list_tables` (read-only, this session); [0006_ai_usage.py](../../backend/alembic/versions/0006_ai_usage.py) |
| Auth | Supabase password auth → backend opaque `moodprint_session` cookie (HttpOnly, SameSite=Strict) + CSRF header + live `auth.sessions` check through a SECURITY DEFINER helper | [security.py](../../backend/app/core/security.py), [provider_session.sql](../../backend/app/infrastructure/database/provider_session.sql) |
| Realtime | Per-connection SSE (`/connections/{id}/events`) that polls a DB watermark row every second; AI run SSE | [notifications.py:27](../../backend/app/modules/social/notifications.py#L27) |
| AI | OpenAI Agents SDK, 5 bots, versioned prompts, 3 scoped tools, proposal-only memory, Voyage embeddings (flagged) | [registry.py](../../backend/app/ai/registry.py), [prompts.py](../../backend/app/ai/prompts.py) |
| Deploy | Single image (SPA + API, same origin) and a two-image Caddy staging compose; gated GitHub staging workflow; no AWS resources exist | [Dockerfile](../../Dockerfile), [deploy-staging.yml](../../.github/workflows/deploy-staging.yml), [verification-report.md](../deployment/verification-report.md) |

Hosted data volume (read-only row counts, 2026-10-25): 2 users (synthetic fixtures A/B), 4 connections, 8 human messages, 63 outbox rows. **No real users yet.**

## 2. Feature classification

### 2.1 Pillar A — AI self-discovery

| Feature | Status | Evidence | Notes |
|---|---|---|---|
| Five AI companions (Mây, Gương, Nhịp, Rủ Rê, Cầu Nối) | REAL_AND_VERIFIED | [registry.py](../../backend/app/ai/registry.py), live evals in [live-ai](../plans/validation-artifacts/live-ai) | Prompt variants selected per bot (`SELECTED_VARIANTS`) |
| Streaming runs, cancel, crash recovery, idempotent turns | REAL_AND_VERIFIED | [runtime.py](../../backend/app/ai/runtime.py), `tests/test_ai_recovery.py` | Single-worker RAM context; restart loses in-flight context only |
| Persistent conversation history (opt-in) | REAL_AND_VERIFIED | [chat_routes.py](../../backend/app/ai/chat_routes.py), [persistence.py](../../backend/app/ai/persistence.py) | 30-day default retention; hosted `ai_conversations` = 0 rows (never used by real users) |
| Explicitly approved memories | REAL_AND_VERIFIED | [memory.py](../../backend/app/ai/memory.py), [memory_models.py](../../backend/app/ai/memory_models.py) | Model can only propose; owner approves |
| Semantic memory retrieval (Voyage + pgvector) | REAL_BUT_INCOMPLETE | [embeddings.py](../../backend/app/ai/embeddings.py), [embedding_config.py](../../backend/app/ai/embedding_config.py) | Capability flag `SEMANTIC_MEMORY_ENABLED`; hosted embeddings = 0 rows; provider retention/region not certified |
| Mood tracking + insights (7/30/90 d) | REAL_AND_VERIFIED | [mood/routes.py](../../backend/app/modules/mood/routes.py), [Mood.tsx](../../frontend/src/features/real/Mood.tsx) | Account timezone; missing days never imputed |
| Nhịp scoped mood tool (per-turn consent) | REAL_AND_VERIFIED | [runtime.py:355](../../backend/app/ai/runtime.py#L355) | Notes never shared |
| Private profile items | REAL_AND_VERIFIED | [profiles/routes.py](../../backend/app/modules/profiles/routes.py) | Never a matching source |
| Voice transcription | REAL_BUT_INCOMPLETE / BLOCKED | [voice/routes.py](../../backend/app/modules/voice/routes.py) | `STT_MODEL` unconfirmed; native mic not verified |
| AI cost controls | REAL_BUT_INCOMPLETE | [persistence.py:166](../../backend/app/ai/persistence.py#L166) | Only concurrency + per-minute rate; **no daily per-user quota and no spend ceiling**, although `ai_usage.estimated_nano_usd` exists |

### 2.2 Pillar B — Human connection

| Feature | Status | Evidence | Notes |
|---|---|---|---|
| Age eligibility (self-declared 16+ private, 18+ social) | REAL_AND_VERIFIED | [age.py](../../backend/app/modules/auth/age.py) | Self-declaration only (risk, see [13](13-risks-and-decisions.md)) |
| MATCH consent, versioned | REAL_AND_VERIFIED | [consent/routes.py](../../backend/app/modules/consent/routes.py) | Withdrawal closes rooms and invalidates requests |
| Matching profile draft → preview → publish/withdraw | REAL_AND_VERIFIED | [social/routes.py](../../backend/app/modules/social/routes.py) | Taxonomy has 7 interests, 4 values, 3 styles, 2 goals, 2 languages ([taxonomy.py](../../backend/app/modules/profiles/taxonomy.py)) |
| Candidate scoring | REAL_BUT_INCOMPLETE | [scoring.py:11](../../backend/app/modules/matching/scoring.py#L11) `SCORING_VERSION = "mock-v1"`; formula [scoring.py:92](../../backend/app/modules/matching/scoring.py#L92) | Production ranks with the **frontend-parity oracle** (45 % interest Jaccard + 35 % value Jaccard + 20 style points, threshold 30). Goal is a hard equality filter. See §3 |
| Candidate retrieval | REAL_BUT_INCOMPLETE | [retrieval.py](../../backend/app/modules/social/retrieval.py) | Correct eligibility; ties broken by peer UUID ([retrieval.py:117](../../backend/app/modules/social/retrieval.py#L117)) → systematic exposure bias |
| Mutual connection consent (request/accept/decline/cancel, reciprocal send) | REAL_AND_VERIFIED | [social/routes.py](../../backend/app/modules/social/routes.py), `tests/test_social.py`, `tests/test_matching_lifecycle.py` | Recipient cannot see who invited them (§3) |
| Human messaging (persistent, idempotent, seq cursor, 90-day retention) | REAL_AND_VERIFIED | [social/routes.py](../../backend/app/modules/social/routes.py), [retention.py:60](../../backend/app/jobs/retention.py#L60) | No unread counts, no last-message preview, no per-user inbox signal |
| Realtime updates | REAL_AND_VERIFIED | [notifications.py](../../backend/app/modules/social/notifications.py), [Social.tsx:572](../../frontend/src/features/real/Social.tsx#L572) | SSE + polling fallback; requests list polls every 5 s and connections every 15 s ([Social.tsx:54](../../frontend/src/features/real/Social.tsx#L54), [Social.tsx:520](../../frontend/src/features/real/Social.tsx#L520)) |
| Identity reveal (display name / gender, per-field consent) | REAL_AND_VERIFIED | [moderation/routes.py](../../backend/app/modules/moderation/routes.py) | |
| Blocking | REAL_AND_VERIFIED | [social/routes.py](../../backend/app/modules/social/routes.py) `block_peer` | Irreversible in-app (by design) |
| Reporting (user side) | REAL_AND_VERIFIED | [moderation/routes.py](../../backend/app/modules/moderation/routes.py) `report`; 5/day ([L36](../../backend/app/modules/moderation/routes.py#L36)) | |
| Moderation workflow (staff side) | **MISSING** | `Report.status` defaults to `received` and nothing ever changes it ([moderation/models.py:53](../../backend/app/modules/moderation/models.py#L53)) | No staff role, queue, action, suspension or reporter feedback |
| Shared activities (Icebreaker, Quiz, Focus) | **MISSING** in production; MOCK_OR_SIMULATED in legacy prototype | Prototype only: scripted peer reply job ([reducer.ts:989](../../frontend/src/state/reducer.ts#L989)), "Mô phỏng đối phương" buttons ([Chat.tsx:394](../../frontend/src/pages/Chat.tsx#L394)) | No schema, API or production UI |

### 2.3 Privacy, platform and operations

| Feature | Status | Evidence | Notes |
|---|---|---|---|
| Export (scoped, re-auth, one-time, 15 min) | REAL_AND_VERIFIED | [users/routes.py:155](../../backend/app/modules/users/routes.py#L155) | Payload held in process memory: tied to the single-worker topology |
| Deletion (scoped + account, lease-fenced worker, provider identity removal) | REAL_AND_VERIFIED | [lifecycle.py:58](../../backend/app/modules/users/lifecycle.py#L58) | Provider backups out of scope (documented) |
| Retention jobs | REAL_AND_VERIFIED | [retention.py](../../backend/app/jobs/retention.py) | Outbox rows are never purged (below) |
| Outbox | **DEAD_CODE** (write-only) | Written at [social/routes.py:177](../../backend/app/modules/social/routes.py#L177), [:218](../../backend/app/modules/social/routes.py#L218), [:548](../../backend/app/modules/social/routes.py#L548), [:651](../../backend/app/modules/social/routes.py#L651), [consent/routes.py:66](../../backend/app/modules/consent/routes.py#L66); no reader anywhere (`grep select(Outbox` = 0 hits) | Unbounded growth (63 hosted rows from 2 fixtures) |
| Code sandbox | DEAD_CODE in production | `app/infrastructure/sandbox/executor.py` imported only by `tests/test_sandbox.py`; `SANDBOX_ENABLED=false` | Keep disabled |
| Rate limiting | REAL_BUT_INCOMPLETE | [limits.py:9](../../backend/app/core/limits.py#L9), [streams.py:8](../../backend/app/core/streams.py#L8) | In-process: valid only with one worker |
| Readiness probe | REAL_AND_VERIFIED | [main.py:196](../../backend/app/main.py#L196) hard-codes `0010_account_deletion` | Every new migration must update this literal |
| CI | REAL_AND_VERIFIED (definition) | [verify.yml](../../.github/workflows/verify.yml) | Includes `check_plans.py` (legacy plan integrity) |
| Staging deploy | BLOCKED | [verification-report.md](../deployment/verification-report.md) | No AWS resources, domain, environment reviewer |
| Monitoring/alerting | REAL_BUT_INCOMPLETE | `deploy/aws/cloudwatch-agent.json`; content-free logs | No alarms, no SLOs, no dashboards |
| Backup/restore | REAL_BUT_INCOMPLETE | manual logical backups existed before 0006/0010 (operator notes) | No scheduled backup, no restore drill |
| Leaked-password protection | BLOCKED | hosted security advisor WARN (this session) | Requires a paid Supabase plan |

## 3. Confirmed defects and product gaps

| ID | Severity | Finding | Evidence | Impact | Recommended action (task) |
|---|---|---|---|---|---|
| DEF-01 | S1 | **Republishing or withdrawing the matching profile closes every open human connection** and invalidates every pending request with a 30-day cooldown. `publish` and `withdraw` call `invalidate_user_social`, which runs `interaction(db, pair, {})`; an empty snapshot never matches, so rooms close | [social/routes.py:160](../../backend/app/modules/social/routes.py#L160), [:201](../../backend/app/modules/social/routes.py#L201), [service.py:214](../../backend/app/modules/social/service.py#L214), [service.py:176](../../backend/app/modules/social/service.py#L176); observed during the hosted E2E run ("an A/B room … was closed when the test republished A … by design", [MVP README](../mvp-validation/README.md)). No test asserts it directly: despite its name, `test_republish_and_match_reenable_never_resurrect_room` ([test_social.py:253](../../backend/tests/test_social.py#L253)) only toggles MATCH consent | Editing interests destroys friendships; users are not warned | Decision DR-03 + task B-02 |
| DEF-02 | S1 | **Incoming connection requests are anonymous**: `RequestView` has no peer card; UI says only "Một lời chào dành cho bạn" | [service.py:217](../../backend/app/modules/social/service.py#L217), [Social.tsx:459](../../frontend/src/features/real/Social.tsx#L459) | Recipients must accept blindly; consent is not informed | B-03 |
| DEF-03 | S2 | **Inconsistent pseudonymous aliases**: candidate alias uses `sha256(sorted ids)[:6]`, connection/export alias uses `pair_id[:6]` — the same person appears under two names | [social/routes.py:309](../../backend/app/modules/social/routes.py#L309), [service.py:231](../../backend/app/modules/social/service.py#L231), [export.py](../../backend/app/modules/users/export.py) | Confusing; undermines trust | B-01 |
| DEF-04 | S2 | Production matching is the parity oracle labelled `mock-v1`, while the DTO advertises `rules-v1-id` | [scoring.py:11](../../backend/app/modules/matching/scoring.py#L11), [social/schemas.py:75](../../backend/app/modules/social/schemas.py#L75) | Weak ranking; version telemetry is wrong | C-01…C-05 |
| DEF-05 | S2 | Goal equality is a hard filter; with 2 goals the ~50-user pool is split in half | [retrieval.py](../../backend/app/modules/social/retrieval.py), [service.py](../../backend/app/modules/social/service.py) `base_eligibility` | Low candidate coverage in a small beta | C-03/C-04 |
| DEF-06 | S2 | Ties ordered by peer UUID string → the same users are always shown first; no exposure balancing | [retrieval.py:117](../../backend/app/modules/social/retrieval.py#L117) | Unfair exposure, "rich get richer" | C-04 |
| DEF-07 | S2 | No moderation workflow; reports are never reviewed | [moderation/models.py:53](../../backend/app/modules/moderation/models.py#L53) | Unsafe for real users | I-01…I-03 |
| DEF-08 | S2 | No daily AI quota or spend ceiling | [persistence.py:189](../../backend/app/ai/persistence.py#L189) | Cost exposure with real users | I-05 |
| DEF-09 | S2 | No unread indicators or inbox signal; Messages list shows only "Mở cuộc trò chuyện" | [Social.tsx:557](../../frontend/src/features/real/Social.tsx#L557) | Conversations die silently | B-05, H-01 |
| DEF-10 | S3 | Outbox write-only, unbounded | §2.3 | Table growth, misleading design | A-05 |
| DEF-11 | S3 | `PublicProfile` validators import private constants from the scoring oracle | [social/schemas.py:8](../../backend/app/modules/social/schemas.py#L8) | Taxonomy has two sources of truth (`taxonomy.py` and `scoring.py`) | C-01 |
| DEF-12 | S3 | 77 of 89 frontend unit tests exercise the legacy prototype (`domain.test.ts` 65, `companions.test.ts` 12); production React modules have no unit tests | vitest JSON report (this session) | False confidence; maintenance drag | A-02, D-07, E-03 |
| DEF-13 | S3 | Frontend package is still named `me2we-prototype` | [package.json:2](../../frontend/package.json#L2) | Naming confusion | A-04 |
| DEF-14 | S3 | Two FK columns unindexed (`blocks.blocked_id`, `candidate_references.peer_id`) | hosted performance advisor (this session) | Minor at 50 users | B-04 |

## 4. Unverified risks (not confirmed defects)

| ID | Risk | Why unverified | Mitigation |
|---|---|---|---|
| R-U1 | Per-connection SSE polls the DB once per second per open stream (up to 4 streams/user) | Load evidence exists only to 50 users on a dev host ([mvp-validation](../mvp-validation/README.md)) | Keep one stream per room; activity watermark rides the same row (D-04) |
| R-U2 | Supabase plan backup entitlement | Not inspected (no billing access) | Scheduled logical backup + restore drill (I-07) |
| R-U3 | Email delivery for signup/recovery | Fixtures were admin-confirmed | Configure SMTP, verify (external) |
| R-U4 | Provider (OpenAI/Voyage) retention and region for private content | Account-level settings not accessible | Legal/privacy review (Q-02) |
| R-U5 | Self-declared age can be falsified | Policy choice | Report → suspension path (I-03); document risk |

## 5. Authentication and eligibility

- Opaque session cookie plus CSRF double-submit (header digest compared to stored hash) plus Origin check on writes ([security.py](../../backend/app/core/security.py)). Sliding idle expiry written at most every 15 minutes. **Strong; keep.**
- Every request re-checks the live Supabase session via `moodprint.is_provider_session_active` — logout or revocation is effective immediately.
- `lock_actor` enforces eligibility (`teen|adult`) and `deletion_pending` on every transaction; `assert_purpose` enforces consent + adult for MATCH.
- `session.alias` defaults to "Bạn" (literally "you"); it is shown only to the owner. Not a defect.

## 6. Data model and Supabase security

- All domain tables live in `moodprint`, which is **not** exposed through the Supabase Data API; RLS is enabled on all 32 tables with a single permissive policy for the backend role. Tenant isolation is enforced in FastAPI. This is consistent and should be preserved: every new table must repeat the ACL/RLS block used in [0006_ai_usage.py](../../backend/alembic/versions/0006_ai_usage.py).
- Migrations are expand-only; `downgrade()` raises. Hosted migrations run only through reviewed offline SQL (`scripts/apply_supabase_review.py` `UpgradePlan`, [apply_supabase_review.py:55](../../scripts/apply_supabase_review.py#L55)).
- Registration points that every new model/migration must update: `backend/alembic/env.py` imports ([env.py:20](../../backend/alembic/env.py#L20)), `backend/tests/conftest.py` imports ([conftest.py:69](../../backend/tests/conftest.py#L69)), the readiness revision literal ([main.py:196](../../backend/app/main.py#L196)), `scripts/inspect_database.py` head check ([inspect_database.py:195](../../scripts/inspect_database.py#L195)) and a new `UpgradePlan`.

## 7. Testing coverage

| Layer | Count (this session) | Notes |
|---|---|---|
| Backend pytest (real PostgreSQL) | 278 passed | Strong two-actor social, consent, privacy, AI recovery coverage |
| Frontend unit (vitest) | 89 passed — only 12 on production code | See DEF-12 |
| Mocked Playwright | 34 (last recorded run, not re-run here) | `tests/e2e/{real,social,chat-history,auth}.spec.ts` |
| Full-stack Playwright | 13 (last recorded run, not re-run here) | Real FastAPI + PostgreSQL + Chromium; two synthetic users |
| Hosted Supabase journeys | 3 (last recorded run) | Synthetic fixtures only |
| Live AI | 2 journeys (last recorded run) | Billable; not re-run |

Gaps: no tests for shared activities (none exist), matching quality evaluation, moderation workflow, unread state, or a 50-user mixed social load with activities.

## 8. CI/CD, Docker and AWS readiness

- CI ([verify.yml](../../.github/workflows/verify.yml)) is comprehensive: Ruff, mypy, pytest on pgvector PostgreSQL, Alembic chain + drift, synthetic load, contract drift, vitest, build, mocked E2E, full-stack E2E, plan integrity, actionlint, Docker images.
- Production topology is deliberately **single process** (in-memory rate limits, SSE slots, export payloads, AI RAM context). For ~50 users this is acceptable and is retained ([04](04-target-architecture.md)).
- AWS staging is fully scripted but **BLOCKED** on account resources and approvals.

## 9. Verification executed in this session

| Command | Result |
|---|---|
| `git status --short`; `git rev-parse HEAD` | ` M .gitignore`; `5689dd9c…` |
| `uv run --locked ruff check app tests` (backend) | PASS — "All checks passed!" |
| `uv run --locked mypy app` | PASS — "no issues found in 61 source files" |
| `uv run --locked pytest -q` with `TEST_DATABASE_URL` → local disposable `moodprint_mvp_test` | PASS — 278 passed in 238 s |
| `npm run typecheck` (frontend) | PASS (exit 0) |
| `npx vitest run` | PASS — 89/89 (5 files) |
| Supabase MCP read-only: `list_tables`, `get_advisors(security|performance)`, `list_extensions` | 32 tables RLS on; 1 Auth WARN (leaked-password protection); 2 unindexed FK INFO; 23 unused-index INFO; pgvector 0.8.2 installed |
| Import-graph trace from `frontend/src/main.tsx` (grep) | Legacy modules unreachable from production entry |

Not run (by design): mocked/full-stack Playwright (the full-stack harness rewrites tracked visual baselines), live AI (billable), hosted journeys (writes hosted data), Docker builds.
