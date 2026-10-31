# Foundation and Guest Authentication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (when authorized/available) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish compatible identity/schema contracts and recoverable guest provisioning without exposing an unsafe trial.

**Architecture:** Preserve Supabase verification → internal UUID → opaque BFF session. Persist intent and attempt before one upstream signup; grant access atomically using database time; recover credentials without storing provider tokens.

**Tech Stack:** Existing FastAPI/Pydantic/SQLAlchemy/Alembic/PostgreSQL, httpx, pytest and generated TypeScript.

**Spec:** [Guest design](../02-guest-auth-design.md), [roadmap GE-00–04](../05-implementation-roadmap.md), [global constraints](00-implementation-index.md#global-constraints).

## Global Constraints

All index constraints apply. Exactly 7200 seconds; 16+ personal/18+ registered social; explicit consent; no production/paid/hosted writes; flags false; no .gitignore changes. New paths below are planned. Commands run from backend unless explicitly prefixed otherwise. Use `uv run --locked`, not the host Python 3.11, for application commands.

## Review Focus

1. Anonymous flag missing/mistyped/inconsistent → fail closed (GE-01.1).
2. Provider outcome unknown → never issue a second signup for the same attempt (GE-04.2).
3. Intent ownership lost or payload changed → no recovery (GE-04.1/04.2).
4. Registered session present or concurrent credentials rotate → no replacement of registered identity; latest valid guest credential only (GE-04.2).
5. Old schema/default rows → remain registered and preserve sliding behavior (GE-02.1/03.1).

## File and migration boundaries

Existing anchors: `auth/provider.py:ProviderSession,SupabaseAuth`; `auth/routes.py:login,session_view,logout`; `auth/age.py:record_age`; `core/security.py:verify_session,require_actor,verify_actor,transaction`; `infrastructure/database/models.py:User,AuthSession`; `core/revisions.py:READY_REVISIONS`. All paths above are under `backend/app/`.

Create focused `backend/app/modules/guests/{models,schemas,policy,intents,service,routes}.py`; later plans own deadlines/jobs/limits/accounting. Keep core security callable signatures unchanged. Do not import guests.routes from core policy.

Reserve these exact new Alembic paths **if HEAD is still 0015**:

| Revision/file                                                                 | Owner                                           | Contents                                                                                                                 |
| ----------------------------------------------------------------------------- | ----------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| `backend/alembic/versions/0016_guest_foundation.py` (`0016_guest_foundation`) | GE-02.1                                         | Identity, attempts, cleanup jobs, usage, abuse counters, detached budget/reservations; immutable trigger; private grants |
| `backend/alembic/versions/0017_guest_security.py` (`0017_guest_security`)     | GE-03.1; helpers completed by GE-04.2/06.1/06.2 | Fresh-time provider helper and guarded identity/orphan functions                                                         |
| `backend/alembic/versions/0018_app_feedback.py` (`0018_app_feedback`)         | GE-10.1                                         | Feedback, receipts, review events                                                                                        |

On rebase, inspect `uv run --locked alembic heads`; if numbers conflict, choose the next free sequential names and update every plan reference/READY_REVISIONS before coding. Do not edit an applied revision. During feature-branch development compose unshipped 0017 helpers before its first approved release; if already applied locally, rebuild only disposable DBs or create a new revision. Never rewrite an applied hosted migration.

## Canonical foundation schema (GE-02.1)

All tables are in private `moodprint`, all times TIMESTAMPTZ UTC, counters nonnegative, UUIDs server generated. New columns use matching ORM/server defaults. Runtime-only RLS/grants follow existing architecture; anon/authenticated/service_role have no CRUD/helper execute. Runtime gets only required tables/functions, not broad auth.* SELECT. SECURITY DEFINER exceptions are narrow private Auth bridges, empty search_path, schema-qualified relations, PUBLIC EXECUTE revoked.

| Entity                        | Exact fields and invariants                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| ----------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `users`                       | `account_kind varchar(10) NOT NULL DEFAULT 'registered'`, check registered/guest; nullable `guest_started_at,guest_expires_at`. Registered requires both NULL; guest requires both non-NULL and `guest_expires_at=guest_started_at+interval '7200 seconds'`. BEFORE UPDATE trigger rejects kind/start/expiry changes (including attempts to null/promote). Partial expiry index for guest rows. Early end changes status, never T.                                                                                                                                                                                                                                                                                                       |
| `auth_sessions`               | Add `created_at NOT NULL DEFAULT clock_timestamp()`. Guest session creation sets expires_at=T, reauthenticated_at=epoch; registered creation remains current behavior. Cross-row lifetime bound enforced by a trigger checking user kind and session expires_at≤T on INSERT/UPDATE.                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| `guest_provisioning_attempts` | `id uuid PK,intent_hash char(64) UNIQUE, idempotency_hash char(64) NULL,payload_digest char(64) NULL,provider_correlation char(64) UNIQUE NOT NULL, provider_subject uuid NULL,provider_session_id uuid NULL,user_id uuid NULL UNIQUE REFERENCES users ON DELETE SET NULL, state varchar(24),created_at,intent_expires_at,signup_started_at NULL,reconcile_until,lease_token uuid NULL,lease_until NULL,attempts int DEFAULT 0,next_attempt_at,last_error varchar(40) NULL`. Correlation=32 random bytes hex, intent expiry=created+600s, reconcile_until≥signup_started+24h once dispatched. No plaintext cookie/key/CAPTCHA/token/age JSON. States below. Index(state,next_attempt_at); check lease token/until both null or both set. |
| `guest_cleanup_jobs`          | `user_id uuid PK REFERENCES users ON DELETE CASCADE,due_at,state,attempts DEFAULT 0,next_attempt_at,lease_token uuid NULL,lease_until NULL,last_error varchar(40) NULL,alerted_at NULL`. State pending/running/retry/incident_required; due_at initially T, may move earlier only for end. Index(state,next_attempt_at), 30s lease.                                                                                                                                                                                                                                                                                                                                                                                                      |
| `guest_usage`                 | `user_id uuid PK REFERENCES users ON DELETE CASCADE,ai_turns int DEFAULT 0,voice_clips int DEFAULT 0,voice_milliseconds bigint DEFAULT 0,semantic_memories int DEFAULT 0`. Lifetime accepted counters, not per-day. No refundable turn/clip after dispatch.                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| `guest_abuse_buckets`         | Composite PK `(scope,key_hash,window_start)`; `count int,reserved int,expires_at`. key_hash=rotating HMAC, never raw IP. scope allowlist for intent/creation/feedback and identity request windows. Index expires_at. Network buckets ≤24h. Per-user bucket digests must be explicitly purged by known derived keys at guest deletion.                                                                                                                                                                                                                                                                                                                                                                                                   |
| `guest_budget_days`           | `day date PK,limit_nano_usd bigint,spent_nano_usd bigint DEFAULT 0,reserved_nano_usd bigint DEFAULT 0,halted_at TIMESTAMPTZ NULL`; positive configured limit, nonnegative amounts; day Asia/Bangkok. No identity. Never create a spend-enabled row from an unset/zero budget. Unresolved halted rows block paid admissions across days until operator review.                                                                                                                                                                                                                                                                                                                                                                            |
| `guest_cost_reservations`     | `id uuid PK,day date REFERENCES guest_budget_days ON DELETE RESTRICT,kind varchar(8) CHECK ai/voice/embed,upper_nano_usd bigint,charged_nano_usd bigint DEFAULT 0,state varchar(16) CHECK reserved/dispatched/settled/uncertain/cancelled,created_at,lease_until,dispatched_at NULL`. No user/run/provider/session/IP/text/model request ID. IDs are random accounting tokens. Index(state,lease_until).                                                                                                                                                                                                                                                                                                                                 |
| `guest_operation_links`       | `user_id uuid REFERENCES users ON DELETE CASCADE,kind,operation_key_hash char(64),payload_digest char(64),reservation_id uuid NULL UNIQUE REFERENCES guest_cost_reservations ON DELETE RESTRICT,state varchar(16) CHECK claimed/dispatched/completed/interrupted,worker_id uuid,lease_token uuid,lease_until TIMESTAMPTZ`; PK(user_id,kind,operation_key_hash), index(kind,state,lease_until). A quota claim may precede financial admission; state dispatched requires reservation_id NOT NULL. Quota and financial reservation are committed in one admission transaction before paid dispatch. Short-lived ownership/replay/concurrency mapping; purge before owner.                                                                  |

Attempt state machine: `intent -> signup_started -> granted` or `ambiguous -> orphan_pending -> resolved`; definitive rejection -> `rejected`; integrity problem -> `incident_required`. A lease can reclaim coordination, **never repeat signup** after signup_started. The only signup transition is a fenced compare-and-set from intent. Terminal rejected/resolved intents cannot retry signup. Failed-before-dispatch attempts can return to intent only if it is proven no external request was invoked. No recovery after intent's 600s browser window; unresolved reconciliation remains independent up to/after 24h with alerts, not silent abandonment.

## Canonical HTTP/DTO contracts (GE-02.2)

Prefix every API below with `/api/v1`. DTO base remains camelCase, extra=forbid. New `GuestInput` = `{eligibility: EligibilityInput,captchaToken: string(1..4096),disclosureVersion:'guest-v2'}`; CAPTCHA repr=False and never persisted. Existing age policyVersion is `self-declared-age-v1`, expectedVersion=0; call existing age rules before provider signup. Under 16 or missing confirmation ->422 `GUEST_INELIGIBLE`, **no provider call**.

| Method/path                | Auth/input                                                                                                                         | Result                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| -------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| GET `/public/experience`   | Public read, no identity, no-store                                                                                                 | `{guestAvailable:boolean,guestUnavailableReason:'disabled'\|'configuration_missing'\|'temporarily_unavailable'\|null,feedbackAvailable:boolean,productTourAvailable:boolean,captchaSiteKey:string\|null}`; public key only. Availability requires configured CAPTCHA/provider/abuse controls; paid capabilities may remain unavailable independently. Never expose budget/secret configuration.                                                                                                                                                                                                                                                                                                      |
| POST `/auth/guest-intents` | Exact Origin required; application/json `{}`; `X-Guest-Intent: 1`; no cross-origin CORS; optional same-origin Fetch-Metadata check | 204 + host-only `moodprint_guest_intent` cookie (HttpOnly, Strict, Secure production, Path=/api/v 1/auth, Max-Age=600). Reuse current live unbound intent. No signup.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| POST `/auth/guest`         | Same public-write guards + intent cookie + stable Idempotency-Key(1..128) + GuestInput                                             | 201 SessionView first grant; 200 same grant/recovery/live guest. 409 `REGISTERED_SESSION_PRESENT` if registered cookie valid, `IDEMPOTENCY_CONFLICT` if bound payload/key changes, `GUEST_ATTEMPT_PENDING` while dispatched/ambiguous (Retry-After:2), `GUEST_INTENT_TERMINAL` when explicit new intent needed. 422 invalid/expired intent; 429 `GUEST_CREATION_LIMIT`; 503 `AUTH_UNAVAILABLE` or `GUEST_DISABLED`. Entryoff blocks new signup/grant, but permits recovery of an already committed active grant within its original intent/T window; a provider-only success when entry turns off becomes orphan cleanup. Never automatically change key or create intent on a 409/ambiguous result. |
| POST `/auth/guest/end`     | Active guest, ordinary CSRF + Idempotency-Key, `{}`                                                                                | 204, set status=deleting/auth_version++, revoke all sessions, due_at/next_attempt_at=DB time, invalidate RAM, clear cookies/intent. Registered ->403 `GUEST_REQUIRED`. Deadline unchanged.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| GET `/session`             | Existing cookie                                                                                                                    | Existing fields plus `accountKind:'guest'\|'registered',guestStartedAt:string\|null,guestExpiresAt:string\|null,guestQuota:{aiTurnsRemaining:int,voiceClipsRemaining:int,voiceSecondsRemaining:number}\|null`. Keep existing serverTime, features.aiStatus enum; unavailable paid guest AI maps to existing configuration_missing/disabled status and false features.ai/voice. New features.feedback boolean. Guest matching=false, staff=null.                                                                                                                                                                                                                                                      |

Null timestamps/quota are required for registered responses, not omitted. Guest serverTime comes from DB; quota reflects durable counters. Session serialization must not query guest moderation/social rows. At T returns 401 `GUEST_EXPIRED` and clears cookies where possible; after hard purge unknown cookie may return existing SESSION_EXPIRED (UI previously aware of a guest still shows expired). No retained expired-cookie tombstone solely for error text.

### Task GE-00.1 — Freeze execution baseline

**Objective:** Reproducible isolated branch and recorded current checks. **Priority:** P0. **Dependencies:** none.

**Architecture:** Read-only discovery precedes source edits; local synthetic DBs separated by suite.

**Files:** Create `docs/guest-experience/implementation/evidence/execution.md`; read existing README/CLAUDE/AGENTS/ARCHITECTURE/manifests, `scripts/load_chat_memory.py`, `.github/workflows/verify.yml`. **Test:** existing suites; no artificial failing test for documentation/setup.

**Interfaces:** Produces baseline SHA, named worktree, explicit known failures, D01–D04 ledger. Consumes none.

- [ ] Step 1: Run root `git status --short`, `git rev-parse HEAD`, `git ls-remote origin refs/heads/main`, `git worktree list`; read instructions and skill versions. Record initial state.
- [ ] Step 2: Use available worktree skill; create `feature/guest-experience` in a new external sibling worktree (e.g. `E:\MoodPrint-guest-experience`, only if absent). Do not alter ignore rules. The current audit/plans are untracked: transfer **only** these planning Markdown files into the new worktree with hashes, preserving originals; otherwise they will be missing from HEAD. Commit copied docs on the feature branch before code.
- [ ] Step 3: Establish separate loopback disposable *_test DBs per plan 07, external keys blank. Run the baseline command table there. Expected GREEN is actual success, not historical counts; diagnose existing failures separately.
- [ ] Step 4: Reproduce isolated 50-user command from plan 07; preserve audit's failed overlapping result and isolated pass as historical evidence. Do not run load concurrently with fullstack.
- [ ] Step 5: Record blocked hosted/manual/Linux checks and proposed safe defaults; review `git diff --check` and privacy of evidence.
- [ ] Step 6: Commit only evidence/planning files with `docs: record guest implementation baseline`.

**Acceptance:** No user work lost; current source/remote divergence known; genuine commands/counts recorded. **Edge cases:** untracked plans, occupied worktree path, missing Docker, schema skips, newer main. **Rollback:** leave original tree/worktree intact. **Completion evidence:** baseline output/target identifiers without secrets; missing DB means PARTIAL, never a passing integration baseline.

### Task GE-01.1 — Verify anonymous provider contract locally

**Objective:** Classify provider identities only after verification. **Priority:** P0. **Dependencies:** GE-00.1.

**Architecture:** Extend httpx adapter, not a new SDK; separate definitive HTTP rejection from transport ambiguity.

**Files:** Create/Test `backend/tests/test_guest_provider.py`; modify `backend/app/modules/auth/provider.py`, `backend/tests/test_auth_flows.py` fake JWT/user responses, `backend/tests/conftest.py`, `backend/tests/{e2e_auth,e2e_server,chat_load_server,social_load_server}.py` synthetic users. LocalAuth lives in e 2e_auth.py; local_provider_server.py is an opt-in live-provider smoke entry and is not the synthetic Auth adapter.

**Interfaces:** Produces `SupabaseAuth.anonymous_session(captcha_token: str, *, correlation_id: str) -> ProviderSession`; extend ProviderSession with `is_anonymous: bool` and hide access_token from repr. Add `AnonymousSignupError(DomainError)` with `outcome: Literal['rejected','ambiguous']`, no raw response. Wire: POST /signup body `{data:{moodprint_guest_attempt:correlation_id},gotrue_meta_security:{captcha_token:captcha_token}}`, no email/password. POST success then GET /user; verify id/sub, exact issuer, aud authenticated (string or list containing authenticated), future numeric exp, UUID session_id and strict boolean is_anonymous agreement in claims/user. Missing flag fails closed; registered fakes must explicitly say false. Permanent password login/update/reset/reauth methods reject verified anonymous sessions before grant or PUT /user with 403 REGISTERED_REQUIRED; direct token input must not become an implicit conversion route.

- [ ] Step 1: Write `test_anonymous_signup_is_verified_and_correlated` and parameterized `test_anonymous_claim_mismatch_is_denied`. Assertions: one signup, exact fields above, returned.is_anonymous is True; mismatched sub/iss/aud/exp/session/bool/missing flag produces no ProviderSession; repr excludes token.

Representative assertions (arranged entities/responses/observations from the named tests):

```python
assert provider.is_anonymous is True
assert provider.access_token not in repr(provider)
assert signup_calls == 1
```

- [ ] Step 2: Run `uv run --locked pytest -q tests/test_guest_provider.py`; expect missing method/explicit contract assertion failures.
- [ ] Step 3: Implement the signatures above. For signup transport timeout/disconnect, invalid success body or unverifiable success classify ambiguous; explicit non-2xx rejection rejected (5xx remains ambiguous unless provider proves no creation). No auto retry. Keep sanitized auth/rate codes.
- [ ] Step 4: Rerun same command; expect all cases PASS with zero external requests.
- [ ] Step 5: Run `uv run --locked pytest -q tests/test_auth_flows.py tests/test_runtime_provision.py`; registered login/reset/step-up fixtures now explicitly permanent. Update conftest.add_actor, LocalAuth and both synthetic load servers to insert matching auth.users with is_anonymous=false as well as sessions; the new SQL helper joins both. Add anonymous recovery-token rejection assertion with zero provider PUT /user.
- [ ] Step 6: Review token/CAPTCHA repr/log/error paths and publishable-key headers; do not send sb-forwarded-for with existing key.
- [ ] Step 7: `git diff --check`; stage only listed files; commit `feat(auth): verify anonymous provider sessions`.

**Acceptance:** Signup response alone never authorizes; permanent path rejects anonymous sessions; anonymous path requires true. **Edge cases:** /user timeout after signup is ambiguous; metadata is correlation only. **Rollback:** provider method unused while entry off. **Completion evidence:** exact pytest counts and sanitized wire assertions.

### Task GE-02.1 — Add compatible durable foundation

**Objective:** Encode the schema table above. **Priority:** P0. **Dependencies:** GE-01.1.

**Architecture:** Expand migration, private tables, immutable lifecycle; no startup migration.

**Files:** Create `backend/app/modules/guests/__init__.py`, `models.py`, migration 0016; Test `backend/tests/test_guest_schema.py`; modify `backend/app/infrastructure/database/models.py`, `backend/alembic/env.py` model registration, `backend/tests/conftest.py`, `backend/app/core/revisions.py`, `docs/supabase/schema.md`.

**Interfaces:** Produces `GuestProvisioningAttempt,GuestCleanupJob,GuestUsage,GuestAbuseBucket,GuestBudgetDay,GuestCostReservation,GuestOperationLink` ORM classes with the canonical fields. Consumes verified anonymous test fixtures. 0016 requires 0015.

- [ ] Step 1: Write `test_guest_lifetime_constraints_and_immutability`: for delta in (7199,7201) assert IntegrityError; 7200 succeeds; registered timestamps fail; runtime UPDATE kind/T fails; session expires_at>T fails; old rows default registered. Write `test_guest_tables_are_private`: four CRUD grants denied for anon/authenticated and intended runtime operations allowed.

Representative assertions (arranged entities/responses/observations from the named tests):

```python
assert guest.guest_expires_at - guest.guest_started_at == timedelta(seconds=7200)
assert existing_user.account_kind == "registered"
assert rejected_lifetime_deltas == {7199, 7201}
```

- [ ] Step 2: Run `uv run --locked pytest -q tests/test_guest_schema.py`; expect missing schema/constraint failures.
- [ ] Step 3: Implement canonical model/migration; register all new metadata before drop_all/create_all. Install trigger/functions in fixtures as well as Alembic; ORM create_all alone cannot prove triggers.
- [ ] Step 4: Run same tests; then on separate empty disposable migration DB run `uv run --locked alembic upgrade head`, `uv run --locked alembic current`, `uv run --locked alembic check`; expect 0016 and no drift. Exercise upgrade from seeded 0015 in test too.
- [ ] Step 5: Run `uv run --locked pytest -q tests/test_readiness.py tests/test_database_operations.py tests/test_auth_flows.py`; update readiness to require compatible current feature head as migrations advance.
- [ ] Step 6: Inspect indexes/FKs/defaults/private grants and runtime-role negative cases; review generated SQL offline, never apply hosted.
- [ ] Step 7: Commit explicit files with `feat(guests): add immutable lifecycle schema`.

**Acceptance:** Empty/upgrade schemas agree, trigger bypass attempts fail, registered data unchanged. **Edge cases:** nullable SQL CHECKs use explicit IS NULL/non-NULL predicates; UTC intervals/DST; applied revision conflict. **Rollback:** retain expand schema; never downgrade with live guests. **Completion evidence:** real DB/runtime role results; skipped Postgres is PARTIAL.

### Task GE-02.2 — Publish flags and session contracts

**Objective:** Backend and generated frontend agree before UI consumes guests. **Priority:** P0. **Dependencies:** GE-02.1.

**Architecture:** Pydantic source, generated TS; availability independent of consent.

**Files:** Create `backend/app/modules/guests/schemas.py`; Test `backend/tests/test_guest_contracts.py`; modify `backend/app/contracts.py`, `backend/app/core/config.py`, `backend/app/modules/auth/routes.py`, `backend/app/main.py`, `backend/.env.example`, `deploy/runtime.env.example`, `docs/backend/configuration.md`, `docs/backend/api-reference.md`, `backend/openapi.json`, `frontend/src/api/contracts.ts`, `frontend/src/api/generated/schema.d.ts`, `frontend/tests/e2e/ux-fixtures.ts`.

**Interfaces:** Produces canonical DTOs/public experience endpoint; flags and config in plan 03. Public route temporarily lives in main.py or guests.routes when created in 04.1, never duplicate registration.

- [ ] Step 1: Write `test_registered_and_guest_session_contracts`: registered null fields, guest exact T and nonnegative counters, false matching/null staff; default public guestAvailable=False; no create/signup calls on GET /public/experience.

Representative assertions (arranged entities/responses/observations from the named tests):

```python
assert guest_body["features"]["matching"] is False
assert guest_body["staff"] is None
assert registered_body["guestExpiresAt"] is None
```

- [ ] Step 2: `uv run --locked pytest -q tests/test_guest_contracts.py` -> expected missing DTO/field failure.
- [ ] Step 3: Add flags false and DTOs; session_view uses server-owned kind and fresh DB time; avoid guest staff/social reads. New migration paths are still planned, not an excuse to accept old schema as ready.
- [ ] Step 4: Same pytest ->PASS; run `uv run --locked python ../scripts/export_openapi.py`; from frontend `npm.cmd run contracts:generate`, `npm.cmd run typecheck`.
- [ ] Step 5: Backend `uv run --locked pytest -q tests/test_production_settings.py tests/test_auth_flows.py`; frontend `npm.cmd test`; root `python scripts/check_docs.py`.
- [ ] Step 6: Verify no secrets in public readiness; policy flags cannot turn off enforcement.
- [ ] Step 7: Commit `feat(guests): expose compatible trial contracts`.

**Acceptance:** Generated types and docs current; no invented aiStatus enum mismatch. **Edge cases:** unavailable paid dispatch, under 16, runtime config off. **Rollback:** compatible nullable fields retained, flags off. **Completion evidence:** contract diff, test/type outputs.

### Task GE-03.1 — Enforce core absolute session lifetime

**Objective:** Make app/provider/transaction authorization guest-aware before provisioning. **Priority:** P0. **Dependencies:** GE-02.2.

**Architecture:** Fresh DB clock with no guest sliding. SQL helper changes from STABLE/statement timestamp to VOLATILE/clock_timestamp, joining verified provider anonymous state.

**Files:** Create `backend/app/modules/guests/policy.py`, migration 0017; Test `backend/tests/test_guest_expiration.py`; modify `backend/app/core/security.py`, `backend/app/infrastructure/database/provider_session.sql`, `backend/app/core/revisions.py`, `backend/tests/conftest.py`, `scripts/prepare_supabase_migration.py`, `scripts/verify_migration_review.py`.

**Interfaces:** Produces `database_time(db: AsyncSession) -> datetime`; `lifetime_allows(user: User, at: datetime) -> bool` pure; `assert_guest_active(db: AsyncSession,user: User) -> None` fresh clock, raises 401 GUEST_EXPIRED; `require_registered_user(user: User) -> None` raises 403 REGISTERED_REQUIRED. Keep Actor/require_actor/transaction public signatures. SQL `is_provider_session_active(uuid,uuid)->boolean` also requires live app mapping/provider row, user active/version, session expiry and (registered with auth.users.is_anonymous IS FALSE OR guest with flag IS TRUE and clock<T). Clock wrapper has **no production at override**.

- [ ] Step 1: Write `test_deadline_boundary` with assertions `lifetime_allows(guest,T-1ms) is True`, at T/T+1ms False. Add `test_refresh_never_extends_guest`, `test_provider_helper_checks_current_time_and_kind`, `test_registered_sliding_unchanged`; missing provider row/revoked/auth-version mismatch denies.

Representative assertions (arranged entities/responses/observations from the named tests):

```python
assert lifetime_allows(guest, T - timedelta(milliseconds=1)) is True
assert lifetime_allows(guest, T) is False
assert refreshed_expiry == original_expiry
```

- [ ] Step 2: `uv run --locked pytest -q tests/test_guest_expiration.py` -> missing lifetime/renewal behavior fails.
- [ ] Step 3: Implement interfaces; branch registered renewal explicitly. Check guest lifetime before generic session expiry so retained guest at T gets GUEST_EXPIRED. Guest core failure clears browser cookies in error response where available. Use helper CREATE OR REPLACE in 0017 and bootstrap source consistently; strict private grants.
- [ ] Step 4: Same pytest ->PASS; use test-only clock replacement for pure/SQL predicate cases, real DB time for boundary integration. Do not expose duration/clock API.
- [ ] Step 5: `uv run --locked pytest -q tests/test_auth_flows.py tests/test_eligibility.py tests/test_enforcement.py tests/test_readiness.py`.
- [ ] Step 6: Review final transaction/output gap; explicitly leave GE-05.1 as mandatory consumer before entry enablement. Add trigger/SQL-review cases with runtime permissions, not superuser-only proof.
- [ ] Step 7: Commit `fix(auth): enforce absolute guest authorization`.

**Acceptance:** Session start/retry/tab/restart cannot change T; time at T denied even with cleanup stopped. **Edge cases:** revoked provider/guest metadata contradiction, DB unavailable fail closed. **Rollback:** guest-aware enforcement must remain deployed. **Completion evidence:** controlled clocks plus real SQL helper boundary/registered regression.

### Task GE-04.1 — Create owned, durable provisioning intents

**Objective:** Persist and bind a browser-owned attempt before external signup. **Priority:** P0. **Dependencies:** GE-03.1, GE-03.2.

**Architecture:** Intent cookie is short-lived coordination, not an app identity. One attempt per cookie; one key/payload binding.

**Files:** Create `backend/app/modules/guests/intents.py`, `routes.py`, `limits.py` (creation-only); Test `backend/tests/test_guest_provisioning.py`; modify `backend/app/main.py`, `backend/app/modules/guests/schemas.py`.

**Interfaces:** Produces `create_guest_intent(request: Request,response: Response)->None`; `claim_guest_attempt(db: AsyncSession,*,intent_token: str,key: str,payload_digest: str)->GuestProvisioningAttempt`. Also produces the creation-only subset of limits.py: `reserve_guest_creation(db: AsyncSession,request: Request,attempt_id: UUID)->None` and `canonical_client_key(request: Request,window_start: datetime,scope: str)->str`. GE-07.1 extends this module for paid/request quotas. No provider call under row lock.

- [ ] Step 1: Write `test_intent_requires_origin_custom_header_and_cookie`: missing/foreign Origin or X-Guest-Intent denied 403, no identity; same cookie reuses one unbound intent. `test_intent_binds_one_key_and_payload`: concurrent same cookie/key leaves one bound attempt; different key/payload 409.

Representative assertions (arranged entities/responses/observations from the named tests):

```python
assert signup_calls == 0
assert bound_attempt_count == 1
assert changed_payload_response.status_code == 409
```

- [ ] Step 2: `uv run --locked pytest -q tests/test_guest_provisioning.py -k intent` -> missing route/binding fails.
- [ ] Step 3: Implement endpoint/claim, canonical normalized eligibility digest excluding CAPTCHA (tokens expire/change); bind CAPTCHA verification to the one signup invocation. Random correlation never returned. Use short locked transactions and unique constraints to arbitrate concurrency.
- [ ] Step 4: Same command ->PASS. Cookie flags/path/lifetime exactly above; flag off returns 503, still no identity.
- [ ] Step 5: `uv run --locked pytest -q tests/test_guest_provider.py tests/test_auth_flows.py`.
- [ ] Step 6: Review credential ownership, shared-NAT/spoofing and bounded failures; cap intents 10/IP/10min and 100/global/min, failed signup attempts 10/IP/10min; successful/reserved trials 3/IP/hour and 10/IP/day, upstream burst separately gated.
- [ ] Step 7: Commit `feat(auth): add durable guest creation intents`.

**Acceptance:** Key alone cannot recover; double clicks serialize. **Edge cases:** concurrent first no-cookie requests may create separate intents, but durable network/global admission still bounds them; Web Locks is UX only. **Rollback:** stop new intents, retain unresolved attempt reconciliation. **Completion evidence:** independent DB sessions/HTTP cookie jars and quota assertions.

### Task GE-04.2 — Grant one trial and recover ambiguous outcomes

**Objective:** Atomic app grant and safe retry without provider-token persistence. **Priority:** P0. **Dependencies:** GE-04.1, GE-01.1.

**Architecture:** Commit signup_started before dispatch; fence completion; grant in one transaction; never reconstruct provider sessions from metadata.

**Files:** Create `backend/app/modules/guests/service.py`; Test `backend/tests/test_guest_auth.py`; extend `backend/tests/test_guest_provisioning.py`; modify `backend/app/modules/guests/routes.py`, `backend/app/modules/auth/routes.py` session/cookie helpers, migration 0017 narrow orphan SQL declarations (worker owns behavior in GE-06.2).

**Interfaces:** `create_guest(request: Request,body: GuestInput,response: Response)->SessionView`; `grant_guest(db: AsyncSession,attempt_id: UUID,fence: UUID,provider: ProviderSession,eligibility: EligibilityInput)->Actor`; `recover_guest_credentials(request: Request,attempt_id: UUID,response: Response)->SessionView`. Produces scheduled cleanup/usage rows in grant and cookies Max-Age=max(0,floor(T−DBtime)), HttpOnly session/Strict/secure, CSRF readable. Registered login explicitly rejects provider.is_anonymous or mapping kind guest.

- [ ] Step 1: Write `test_guest_grant_has_one_database_deadline`: assert T-start=7200, all four consents false, age recorded, distinct independent subjects/users, cleanup.due_at=T. `test_lost_grant_response_recovers_same_user_and_deadline`: drop HTTP response then same intent/key rotates credentials, no signup, same T. `test_ambiguous_signup_never_retries_upstream`: fake accepts then times out; N retries cause exactly 1 signup and no app grant.

Representative assertions (arranged entities/responses/observations from the named tests):

```python
assert recovered.user_id == original.user_id
assert recovered.guest_expires_at == original.guest_expires_at
assert signup_calls == 1
```

- [ ] Step 2: `uv run --locked pytest -q tests/test_guest_auth.py tests/test_guest_provisioning.py` -> missing grant/recovery fails.
- [ ] Step 3: Validate age/disclosure first; claim attempt then call anonymous_session once outside transaction. On verified success, lock/fence attempt; create internal user with T0 from fresh clock_timestamp immediately at grant INSERT, T0+7200, record_age, disabled consents, session, usage, cleanup; commit before cookies. Discard tokens. If grant rollback, persist orphan_pending with provider subject/session where possible; crash-before-persist is recovered via marker. No successful authorization before grant.
- [ ] Step 4: Same tests ->PASS; add barriers for two recoveries, DB rollback after provider success, failure after commit/before Set-Cookie and expired intent/T. Fence invalidated by reconciler means grant rejected and orphan cleaned. Initial grant locks only the attempt before inserting a new owner; mapped recovery first reads mapping without lock, locks owner, then locks/revalidates attempt to match cleanup's owner-before-attempt order. No attempt lock may wait on an already-existing owner; add recovery-versus-cleanup deadlock regression.
- [ ] Step 5: `uv run --locked pytest -q tests/test_guest_provider.py tests/test_guest_expiration.py tests/test_guest_permissions.py tests/test_auth_flows.py`.
- [ ] Step 6: Verify token-free recovery: stored provider session ID must still pass helper; rotate/revoke previous app credentials while preserving lifecycle; no anonymous/permanent promotion. A live guest cookie returns same session/T without another grant.
- [ ] Step 7: Commit `feat(auth): provision recoverable isolated guest trials`.

**Acceptance:** Retries are bounded, registered cookies never overwritten, upstream orphan has durable target. **Edge cases:** marker duplicates ->incident; response lost after cookie header uncertain; 10min window expired ->explicit new intent, old account queued for normal expiry/purge; stale fence cannot grant. **Rollback:** disable creation; reconcile started attempts and expire existing users. **Completion evidence:** fault-injection points and exact signup/grant counts.

### Task GE-04.3 — End guest lifecycle safely

**Objective:** Guest logout/end permanently revokes the trial without password. **Priority:** P0. **Dependencies:** GE-04.2.

**Architecture:** Preserve immutable deadline; set deleting/revoke versions and expedite durable cleanup.

**Files:** Modify `backend/app/modules/guests/service.py`, `routes.py`, `backend/app/modules/auth/routes.py`; Test `backend/tests/test_guest_auth.py`.

**Interfaces:** `end_guest(request: Request,actor: Actor)->None`; guest /auth/logout delegates to this; registered logout stays session-only. Recovery checks user status and cannot reopen ended user.

- [ ] Step 1: Add `test_guest_logout_ends_all_sessions_and_expedites_cleanup`: two rotated/tab credentials fail, attempt recovery denied, T unchanged, job due now; registered logout leaves other registered session valid; CSRF forged 403.

Representative assertions (arranged entities/responses/observations from the named tests):

```python
assert ended_user.status == "deleting"
assert all(row.revoked for row in guest_sessions)
assert ended_user.guest_expires_at == original_deadline
```

- [ ] Step 2: `uv run --locked pytest -q tests/test_guest_auth.py -k 'logout or end'` -> expected missing end behavior.
- [ ] Step 3: Under owner lock revalidate, set status=deleting/auth_version++, revoke sessions and update job; after commit invalidate AI/exports, clear intent/session/CSRF cookies. Best-effort idempotent repeated missing/expired request gets 401 with clear cookies; no password/reauth.
- [ ] Step 4: Same command ->PASS.
- [ ] Step 5: `uv run --locked pytest -q tests/test_auth_flows.py tests/test_data_lifecycle.py tests/test_ai_recovery.py`.
- [ ] Step 6: Ensure registered account deletion/partial private deletions do not accidentally enter guest purge. Later GE-05.4 handles guest account deletion/export contract.
- [ ] Step 7: Commit `feat(auth): end guest lifecycles on logout`.

**Acceptance:** Ended state never becomes active through retries/worker failures. **Edge cases:** expiry concurrent with end ->denied but cleanup already scheduled; lost end response ->subsequent 401 safe. **Rollback:** retain revocation and jobs. **Completion evidence:** session/version/job/registered assertions.

### Task GE-01.2 — Prove approved hosted compatibility

**Objective:** Verify the boundaries local fakes cannot establish. **Priority:** P0 release checkpoint. **Dependencies:** GE-06.2, GE-07.3; D04 approval before execution.

**Architecture:** Local test skeleton/runbook may proceed; hosted execution is a named hold, not implied by an enabled Dashboard setting.

**Files:** Create/Test `backend/tests/live/test_guest_auth_compatibility.py`; create `docs/guest-experience/implementation/evidence/hosted-auth.md`; modify `scripts/verify_migration_review.py` only for concrete new helper checks.

**Interfaces:** Hosted test requires explicit `APPROVED_GUEST_AUTH_TARGET` identifier and `RUN_GUEST_AUTH_COMPATIBILITY=1`; verifies selected target matches authorized non-production database/Auth pair. Never selects .env/production as fallback. Helper contracts in plan 03.

- [ ] Step 1: Add `test_hosted_target_guard`: absent approval/mismatched target refuses before any request. Run `uv run --locked pytest -q tests/live/test_guest_auth_compatibility.py -k target_guard`; prove guard fails before implementing it, then passes.

Representative assertions (arranged entities/responses/observations from the named tests):

```python
assert unapproved_target_mutations == []
assert synthetic_auth_children_after_cleanup == 0
assert unrelated_canary_after == unrelated_canary_before
```

- [ ] Step 2: Implement explicit opt-in synthetic creation/verification/delete probe with finally cleanup and bounded one-identity attempt. Default full file reports explicit skipped hosted case; skip is PARTIAL.
- [ ] Step 3: **Only after D04**, run `uv run --locked pytest -q -m live tests/live/test_guest_auth_compatibility.py` with authorized target supplied out of band; expected one synthetic identity and all intended Auth children removed, unrelated target canary unchanged.
- [ ] Step 4: Prove provider CAPTCHA, upstream BFF egress burst ≥60, app IP controls, auth.sessions lifetime ≥7200s, helper privileges/all CRUD denial and any other Data API/Storage/Realtime surface denies guest bypass. A provider setting change needs its own explicit approval; do not silently increase limits.
- [ ] Step 5: Check current TLS/cipher compatibility and actual provider/log/backup retention; attach sanitized observations, not keys/tokens/identities.
- [ ] Step 6: Review D01/D04 outcomes and registered hosted regression on synthetic permanent actor if separately approved; clean up only owned synthetic resources.
- [ ] Step 7: Commit test/runbook only with `test(auth): document hosted anonymous compatibility gate`.

**Acceptance:** Unapproved target never mutated; hosted proof distinct from mocks. **Edge cases:** absent target, CAPTCHA interactive step, cascade privileges, ambiguous cleanup ->hold/alert. **Rollback:** no enabling flag; compensate only exact synthetic identities. **Completion evidence:** target authorization reference, actual request counts/results and remaining blocked items.

## External evidence and implementation checks

Rechecked 2026-10-28: [Supabase anonymous auth](https://supabase.com/docs/guides/auth/auth-anonymous) confirms authenticated-role use and lack of automatic cleanup; [rate limits](https://supabase.com/docs/guides/auth/rate-limits) defines CAPTCHA/IP controls; recheck exact wire API using current [official auth client source](https://github.com/supabase/supabase-js/tree/master/packages/core/auth-js) before implementation (the old standalone auth-js repository is archived). The changelog index was fetched read-only; [CBC TLS notice](https://supabase.com/changelog/cbc-tls-ciphers-deprecated) remains a staging watch item. None proves hosted configuration.

Foundation completion requires `uv run --locked ruff check app tests evals alembic`, `uv run --locked mypy app`, relevant pytest suites, Alembic/drift and generated frontend typecheck. GE-03.2 and GE-05–07 are mandatory before guest entry enablement.
