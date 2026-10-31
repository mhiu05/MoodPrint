# Guest Expiry and Permissions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (when authorized/available) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deny cross-user/social access and prevent late private output, writes or paid work at the absolute deadline.

**Architecture:** Reuse centralized actor/owner/purpose gates; enforce registered kind on requester and peer. Add final transaction and output boundaries, deadline cancellation and background publication fencing.

**Tech Stack:** FastAPI/ASGI, asyncio, PostgreSQL fresh clocks/locks, existing Agents SDK, pytest barriers and synthetic providers.

**Spec:** [Guest design §§4–6](../02-guest-auth-design.md), [audit social/storage inventory](../01-current-architecture-audit.md), [index constraints](00-implementation-index.md#global-constraints).

## Global Constraints

Exactly 7200s, no grace. Only a pre-T final authorization can permit a mutation/output; physical DB commit/TCP completion may occur later. Never promise remote provider cancellation or universal erasure. Default-deny guests across social/staff; preserve own eligible personal functions. No paid/hosted test calls.

## Review Focus

1. Forged guest peers in valid registered rooms/candidates → suppress/deny (GE-03.2).
2. Transaction waits on locks across T → rollback final mutation (GE-05.1).
3. Buffered SSE final waits after polling authorization → check again at dispatch (GE-05.2).
4. Embedding response arrives after purge → no job/vector resurrection (GE-05.3).
5. Slow audio upload/export response crosses T → no dispatch/private result (GE-05.4).

## Authorization and endpoint classification

GE-03.1 owns core lifetime and SQL helper; **do not duplicate it here**. GE-03.2 owns social integration. Classify every (method,path) from generated OpenAPI in a test-owned map; assert exact set equality so a new unclassified operation fails. Groups expand to explicit tuples, never an exemption by URL prefix alone.

| Existing operation group (all /api/v 1)                                                                                                                                                                                       | Guest behavior                                                                                          | Enforcement anchors                                      |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- | -------------------------------------------------------- |
| health/live, health/ready, bots, taxonomy; new public/experience                                                                                                                                                              | Public; no identity creation                                                                            | Existing public routers                                  |
| session, users/me/eligibility, auth/logout, consent writes except MATCH enable                                                                                                                                                | Live guest; existing eligibility/body/CSRF rules                                                        | security/auth/consent                                    |
| moods, moods/summary, moods/{local_date}; AI preferences/conversations/messages/events/cancel/export/end; memories/proposals/confirm/reject/edit/delete; voice; own exports/data jobs | Own data only, lifetime+purpose; other owner 404                                                        | Existing personal transaction/owned_* helpers plus GE-05 |
| GET/PATCH users/me/identity                                                                                                                                                                                                   | Own private identity settings allowed, no reveal to peers                                               | moderation/routes own identity functions                 |
| profiles/matching-draft GET/PUT/preview; profiles/published/current GET/DELETE; profiles/published POST; matching/candidates GET, matching/skips POST                                                                         | 403 REGISTERED_REQUIRED before profile/consent lookups                                                  | social/routes and match_consent                          |
| connection-requests GET/POST and accept/decline/cancel; connections GET/list/detail/read/messages GET/POST/end/block/events; blocks POST                                                                                      | 403 REGISTERED_REQUIRED, including read/SSE                                                             | social/routes/notifications, pair_transaction/room_gate  |
| activities/catalog; connections/{id}/activities POST/GET/current; activities/{id} GET and accept/decline/cancel/end/focus pause/resume/leave/join/responses/ready/feedback                                                    | Registered-only; no synthetic peer workaround                                                           | activities/routes, hooks, sweeper                        |
| connection peer-reference, reveal requests POST/GET, grant/decline/value/revoke                                                                                                                                               | Registered-only both sides                                                                              | moderation/routes and room gates                         |
| reports POST/detail GET; admin/reports/list/claim/resolve; admin/users/{ref}/lift                                                                                                                                             | Guest denied; staff/admin also permanent/live role+reauth                                               | moderation/routes/staff/admin_routes                     |
| GET social/summary                                                                                                                                                                                                            | Explicit zero projection; no social SQL reads                                                           | social/summary fast path before aggregation              |
| auth/login/signup/confirmation/password-recovery/reset                                                                                                                                                                        | Public Auth behavior; no anonymous grant through permanent path; guest transition requires explicit end | auth/provider/routes and frontend transition             |
| auth/reauthenticate                                                                                                                                                                                                           | Registered-only; no guest password step-up                                                              | auth/routes                                              |
| new guest intent/create/end, feedback/admin endpoints                                                                                                                                                                         | As canonical contracts in plans 01/05                                                                   | Their owning tasks                                       |

Personal data: journals require current eligibility, AI requires AI consent, memory needs AI/MEM consent and approval, VOICE needs AI+VOICE. Disable MATCH enable for guests even if fabricated adult/consent rows exist. Disabling MATCH may be permitted as a harmless withdrawal; no side effect creates social resources. No notification query/poll for guests. Registered users must not observe guest existence via candidate/ref/room errors.

### Task GE-03.2 — Deny guest social access at route and peer gates

**Objective:** Close every real-user entry and selection path. **Priority:** P0. **Dependencies:** GE-03.1.

**Architecture:** Shared registered dependency for requester plus service predicates for both users; existing sorted-users→pair→resource lock order.

**Files:** Create/Test `backend/tests/test_guest_permissions.py`; modify `backend/app/core/security.py`, `backend/app/modules/consent/routes.py`, `backend/app/modules/auth/routes.py`, `backend/app/modules/social/{routes,service,retrieval,summary,notifications}.py`, `backend/app/modules/activities/{routes,hooks,jobs}.py`, `backend/app/modules/moderation/{routes,staff,admin_routes}.py`. The inspected activity worker is jobs.py.

**Interfaces:** Consumes `require_registered_user(user)`. Produces `require_registered_actor(request: Request)->Actor` (may be composed as dependency with Depends(require_actor)); service `match_consent`, `base_eligibility`, `room_gate`, `eligible_peers` explicitly require both kinds registered. Retain existing return types. Own identity routes remain personal.

- [ ] Step 1: Write `test_every_operation_has_guest_policy`: actual OpenAPI tuple set equals classified set. `test_guest_direct_social_routes_denied`: parameterize exact restricted tuples with valid body/CSRF/forged adult consent/profile/room rows; status 403/code REGISTERED_REQUIRED, expired actor 401 first. `test_registered_cannot_select_guest_peer`: candidates omit guest, legacy room/reveal/activity denies without peer content. `test_guest_summary_does_not_query_social_tables`: instrument SQL and assert zeros/no social table reads.

Representative assertions (arranged entities/responses/observations from the named tests):

```python
assert response.status_code == 403
assert response.json()["error"]["code"] == "REGISTERED_REQUIRED"
assert actual_operations == classified_operations
```

- [ ] Step 2: `uv run --locked pytest -q tests/test_guest_permissions.py` -> policy assertions fail before implementation.
- [ ] Step 3: Apply requester guards before resource lookup; add both-kind predicates in SQL retrieval and locked pair policies. Filter background invalidation/notifications/activity processing so malformed guests cannot publish, receive or revive social work; abort invalid existing activity without delivering private events.
- [ ] Step 4: Same command ->PASS, including guest A/B and registered UUID ownership attempts returning 404 for personal resources.
- [ ] Step 5: `uv run --locked pytest -q tests/test_social.py tests/test_matching_privacy.py tests/test_enforcement.py tests/test_activities_api.py tests/test_moderation_admin.py tests/test_notifications.py`.
- [ ] Step 6: Review complete tuple map vs current OpenAPI, helper calls bypassing routes, retired/legacy rows and staff rows. UI hiding is not evidence.
- [ ] Step 7: Commit `fix(guests): deny social and peer access by default`.

**Acceptance:** All classified operations exercised, no guest social queries via summary, all five assistant IDs still personal. **Edge cases:** flags off may 404 staff endpoints; test flags on to prove authorization, then off to prove concealment; forged moderation role never grants guest. **Rollback:** retain gates. **Completion evidence:** route count/classification coverage and real DB pair tests.

## Deadline contracts (GE-05.1)

Create `backend/app/modules/guests/deadlines.py` with:

- `GuestDeadline(expires_at: datetime, remaining_seconds: float, monotonic_deadline: float)` immutable. A DB clock sample plus elapsed local monotonic time gives a **conservative cancellation/output bound**, never a new lifetime grant. Capture local monotonic before requesting DB time so DB round-trip cannot extend T. Never trust browser time.
- `async guest_deadline(db: AsyncSession,user: User)->GuestDeadline | None`, uses GE-03.1 database_time and asserts active; None for registered.
- `async final_guest_authorization(db: AsyncSession,user: User)->None`, refreshes current row/lifetime immediately before final conditional content write/commit. Full actor revalidation remains required where a request actor exists.
- `async guard_guest_dispatch(database: Database,actor: Actor)->GuestDeadline | None`, revalidate actor/consents as appropriate in caller, fresh DB sample; synchronous deadline comparison immediately before invoking send/provider call.

Create pure-ASGI `backend/app/modules/guests/output.py:GuestOutputMiddleware`. require_actor (and successful guest grant) places actor/kind/deadline context in request scope state; public errors/health/static are not private output. Middleware wraps the **outermost app send**, revalidates private guest output after any response-building/queue awaits. Buffer ordinary response headers until first body authorization; if expired before headers, send sanitized 401 GUEST_EXPIRED and clear cookies. If streaming headers already sent, suppress private bytes and close; SSE route may send only content-free revoked event. Check each outgoing body frame, including JSON/export frames; no whole-file unbounded buffer.

Final output boundary: after async validation, perform immediate conservative monotonic expiry check, then invoke underlying ASGI send with **no intervening await**. Awaiting send itself is physical transport and outside the logical guarantee. If a queue/middleware awaits after validation and before invoking actual send, move/repeat the guard after that await. Test using a fake send/queued iterator. Missing/denied/DB-error context fails closed; never output a previously built private payload after failure.

Transactions: retain canonical owner lock from transaction entry through commit. Flush intended ORM mutations; fresh final lifetime check before leaving transaction. If T crossed, rollback mutations/receipts together. For conditional SQL publication, include owner/current lifetime/lease/version in final statement. A valid pre-T decision may physically commit later; purge acquires same owner lock and follows committed write or makes late writer fail. Do not assert impossible disk/TCP precision.

### Task GE-05.1 — Fence transaction and private HTTP output

**Objective:** Close request-start-to-finalization authorization gaps. **Priority:** P0. **Dependencies:** GE-04.3.

**Architecture:** Canonical deadline helpers plus shared transaction/output middleware; existing API schemas unchanged.

**Files:** Create `backend/app/modules/guests/{deadlines,output}.py`; Test `backend/tests/test_guest_inflight.py`; modify `backend/app/core/security.py`, `backend/app/main.py`, `backend/app/modules/guests/service.py`.

**Interfaces:** Produces deadline/ASGI contracts above; consumes GE-03.1 actor/lifetime. No production clock override.

- [ ] Step 1: Write `test_waiting_mutation_rolls_back_at_deadline`: two independent DB sessions/barrier hold owner lock until T, then mutation/receipt count unchanged and 401. `test_private_output_guard_runs_after_queue_wait`: build body before T, block send iterator, advance controlled clock to T, assert no secret bytes and 401/revoked. `test_predeadline_decision_then_commit_is_purged`: decision pre-T, physical commit later allowed but next read 401 and purge removes data.

Representative assertions (arranged entities/responses/observations from the named tests):

```python
assert b"private-canary" not in sent_body
assert mutation_count_after == mutation_count_before
assert receipt_count_after == receipt_count_before
```

- [ ] Step 2: `uv run --locked pytest -q tests/test_guest_inflight.py -k 'mutation or output or commit'` -> expected missing final guard failures.
- [ ] Step 3: Implement deadline interfaces, transaction final revalidation and outer send guard. Bound lock/statement timeouts to remaining grant; retryable DB unavailable fails closed. Registered responses bypass extra guest checks.
- [ ] Step 4: Same command ->PASS; assert final dispatch-check sequence using event log in fixture, not wall-clock sleeps.
- [ ] Step 5: `uv run --locked pytest -q tests/test_guest_expiration.py tests/test_mood.py tests/test_context_privacy.py tests/test_auth_flows.py`.
- [ ] Step 6: Inspect middleware ordering (including existing BaseHTTPMiddleware) and no awaited queue between guard and final send. Static/public error responses remain usable; callback tokens never logged.
- [ ] Step 7: Commit `fix(guests): fence transaction and response deadlines`.

**Acceptance:** At/post-T final decisions fail; DB error does not release cached content. **Edge cases:** disconnected client, multi-frame JSON/export, headers already sent, no actor on expired error. **Rollback:** keep guard and schema. **Completion evidence:** deterministic barriers plus one small real-DB boundary test, no 7200s sleep.

### Task GE-05.2 — Fence AI, tools and every SSE event

**Objective:** Stop new work and buffered/replayed output after T. **Priority:** P0. **Dependencies:** GE-05.1.

**Architecture:** Keep runtime.check and SDK hooks; enforce at each model/tool dispatch and final publication, plus deadline task.

**Files:** Modify `backend/app/ai/{runtime,provider,chat_routes,store,persistence}.py`; Test `backend/tests/test_guest_inflight.py`, `backend/tests/test_sdk_adapter.py`.

**Interfaces:** LiveRun stores optional GuestDeadline; ConversationStore expiry capped at T. `AiRuntime.check(run)` remains callable; `SdkProvider.run` signature unchanged: current `_BudgetHooks.on_llm_start` invokes on_progress (runtime.check) **before each model call**. Tool wrappers from `AiRuntime.tools` recheck before/after; don't invent a second provider protocol. Add `AiRuntime.expire_guest(user_id: UUID)->None` clearing events/proposals/context/mood evidence and cancelling tasks. No raw deltas sent.

- [ ] Step 1: Add `test_queued_sse_final_is_dropped_at_expiry`, `test_replayed_durable_final_after_expiry_is_denied`, `test_idle_sse_closes_at_deadline`, `test_tool_and_second_model_call_not_dispatched_after_t`: fake provider barrier at T, zero late calls/final text; only content-free revoked allowed. Both persistent and ephemeral paths required.

Representative assertions (arranged entities/responses/observations from the named tests):

```python
assert not any(event["type"] == "final" for event in events_authorized_at_or_after_T)
assert model_dispatches_after_T == 0
assert tool_dispatches_after_T == 0
```

- [ ] Step 2: `uv run --locked pytest -q tests/test_guest_inflight.py -k 'sse or model or tool'` -> existing batch authorization fails cases.
- [ ] Step 3: Clamp timeout to min(existing timeout,T−DBtime), cancel on deadline independent of 0.5s monitor; check before each inner SSE yield including terminal batch and after iterator waits (outer send guard still final authority). Recheck after final DB transaction before RAM/event publication. No late in-memory append.
- [ ] Step 4: Same command ->PASS; test cancellation-resistant fake late result discarded, not retried.
- [ ] Step 5: `uv run --locked pytest -q tests/test_ai.py tests/test_ai_recovery.py tests/test_chat_persistence.py tests/test_scoped_mood_tool.py tests/test_sdk_adapter.py`.
- [ ] Step 6: Verify all five bots; Cầu Nối has no social tool; max 3 model turns/1200 output tokens/call and no auto retry preserved. Expired client cannot retrieve completed saved run.
- [ ] Step 7: Commit `fix(ai): fence guest tools streams and publication`.

**Acceptance:** Each event checked, idle stream cancelled, no paid replay on restart. **Edge cases:** Last-Event-ID, terminal cache, cancelled monitor, timeout while waiting slot. **Rollback:** preserve fences; stop new entry. **Completion evidence:** captured synthetic events/call counts, no model success claim.

### Task GE-05.3 — Cap memory/history and fence embeddings

**Objective:** Temporary personal memory remains explicit and cannot reappear after expiry/purge. **Priority:** P0. **Dependencies:** GE-05.2.

**Architecture:** Existing source/consent/data/preference/lease fencing plus guest lifetime; memory itself stays user-owned.

**Files:** Modify `backend/app/ai/{memory,embeddings,chat_routes,store}.py`; Test `backend/tests/test_guest_embeddings.py`, `backend/tests/test_guest_inflight.py`.

**Interfaces:** `embeddings._authorization(db,user_id)->Authorization | None` returns None for expired/ended/missing owner; preserves existing fields. `create_proposal` expires at min(now+900,T), saved conversations at min(normal retention,T); ephemeral store also caps T. `enqueue_memory/process_embedding_jobs/reconcile_embedding_jobs` never recreate expired work. Guest semantic feature remains false unless GUEST_SEMANTIC_ENABLED, explicit opt-in and paid/retention gates.

- [ ] Step 1: Write `test_late_embedding_cannot_recreate_deleted_memory`: pause provider, expire/purge, release; vectors/jobs remain zero. `test_guest_proposal_and_history_expiry_capped`: assert each expires_at≤T and approval at T fails; source/version/consent revocation still fails.

Representative assertions (arranged entities/responses/observations from the named tests):

```python
assert embedding_count_after_late_response == 0
assert embedding_job_count_after_reconcile == 0
assert proposal.expires_at <= guest.guest_expires_at
```

- [ ] Step 2: `uv run --locked pytest -q tests/test_guest_embeddings.py` -> missing owner deadline cap fails.
- [ ] Step 3: Implement final owner-lock+clock+lease+version checks in publication; remove expired job rather than retry it. Pure lexical retrieval and ordinary approved memory remain available with consent when semantic off.
- [ ] Step 4: Same command ->PASS, including reconcile-after-expiry and claim-before-T/publish-after-T.
- [ ] Step 5: `uv run --locked pytest -q tests/test_memory.py tests/test_embeddings.py tests/test_context_privacy.py tests/test_retention.py`.
- [ ] Step 6: Check proposal approval limits and memory retrieval failure propagation; no authorization exception is caught and converted into usable cached content.
- [ ] Step 7: Commit `fix(memory): cap guest data and fence embedding jobs`.

**Acceptance:** No late upsert; opt-ins/approval unchanged; missing owner fails closed. **Edge cases:** RAM restart loss, multi-bot memory, semantic flag changes, source deletion. **Rollback:** semantic off; lifetime fences remain. **Completion evidence:** counts/expiry assertions against real DB and fake embed transport.

### Task GE-05.4 — Bound voice and guest data controls

**Objective:** Voice/upload/export/delete honor lifetime without password dead ends. **Priority:** P0. **Dependencies:** GE-05.3.

**Architecture:** Existing bounded WAV preview and RAM exports, guest-specific confirmations, existing registered step-up unchanged.

**Files:** Modify `backend/app/modules/voice/routes.py`, `backend/app/modules/users/{routes,schemas,export}.py`, `backend/app/ai/chat_routes.py`; Test `backend/tests/test_guest_exports.py`, `backend/tests/test_guest_inflight.py`.

**Interfaces:** Add optional `guest_confirmation: Literal['guest-data-v1'] | None` to ExportInput/DeletionInput; registered ignores guest confirmation and still requires 5min reauth for account/export. Guest requires confirmation+CSRF/idempotency; account deletion delegates end_guest and returns an empty 204, explicitly documented as an alternate OpenAPI response; registered remains 202 DataJobView. Partial deletions use existing personal worker; account goes guest hard purge. Guest exports reject scopes containing social with 403 REGISTERED_REQUIRED; cap RAM TTL=min(900,T−DBtime). Chat export uses same final guard. No password reauth for guest.

- [ ] Step 1: Add `test_guest_export_cannot_download_at_t`, `test_export_reauth_registered_only`, `test_guest_account_delete_uses_hard_purge_queue`; assert 401/no payload at T, other owner 404, social scope 403. Add `test_voice_upload_and_result_crossing_t`: slow body/provider barriers cause zero late provider dispatch/output and audio buffer emptied.

Representative assertions (arranged entities/responses/observations from the named tests):

```python
assert expired_download.status_code == 401
assert expired_download.content.find(b"private-canary") == -1
assert voice_dispatches_after_T == 0
```

- [ ] Step 2: `uv run --locked pytest -q tests/test_guest_exports.py tests/test_guest_inflight.py -k 'export or delete or voice'` -> expected guard/confirmation failures.
- [ ] Step 3: Check deadline while reading chunks and immediately before STT dispatch; cancel/discard late result. Clamp existing 35s STT timeout to remaining grant, preserve 30s/3MB validation. Add confirmations/expiry caps, invalidate all owner exports on end/purge. No guest social export query.
- [ ] Step 4: Same command ->PASS.
- [ ] Step 5: `uv run --locked pytest -q tests/test_voice.py tests/test_data_lifecycle.py tests/test_privacy_lifecycle.py tests/test_chat_persistence.py`; regenerate OpenAPI/TS and typecheck as in GE-02.2.
- [ ] Step 6: Check guest account-delete/end 204 have no private body after revocation (output guard permits empty revocation responses), and removal of an exported server payload does not falsely promise revocation of downloaded copies. Paid voice quotas follow GE-07.
- [ ] Step 7: Commit `fix(guests): bound voice exports and data controls`.

**Acceptance:** No new STT after T; existing registered export/account-delete step-up unchanged; guest partial/private deletion remains available. **Edge cases:** upload stalls, second download 410, memory-only deletion, T during confirmation. **Rollback:** retain deadline/cookie revocation. **Completion evidence:** voice/provider call counts, export RAM and DB checks, registered tests.
