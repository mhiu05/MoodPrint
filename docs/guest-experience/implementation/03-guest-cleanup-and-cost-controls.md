# Guest Cleanup and Cost Controls Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (when authorized/available) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Purge the complete temporary footprint durably and bound guest abuse and paid liability across deletion/restart.

**Architecture:** Dedicated guest worker/reconciler reuses owner locks and lease fencing, not registered tombstone behavior. PostgreSQL quotas and detached integer cost reservations survive process restarts and guest removal.

**Tech Stack:** PostgreSQL/SQLAlchemy, existing one-worker asyncio lifespan, pytest real-DB concurrency, synthetic AI/STT/embed providers.

**Spec:** [Guest design §§5/7](../02-guest-auth-design.md), [data audit](../01-current-architecture-audit.md#5-data-lifecycle-and-exhaustive-footprint), [decisions](../07-risks-and-open-decisions.md), [foundation schema](01-foundation-and-guest-auth.md#canonical-foundation-schema-ge-021).

## Global Constraints

Authorization cutoff at T independent of sweeper. Healthy-service targets proposed: start≤60s, complete≤5min, alert>5min; outages require retries, never access restoration. No universal backup/provider erasure promise. Guest AI budget unset/unapproved; fail closed with flags off. Preserve registered records/capacity. No external calls in purge transaction.

## Review Focus

1. Crash after claim/before purge commit → lease retry with no partial erasure (GE-06.1/06.2).
2. Correlation lookup finds zero/multiple/unexpected subjects → no signup repeat or broad deletion (GE-06.2).
3. Corrupted guest/registered social graph → retain counterpart evidence and raise incident (GE-06.1).
4. Concurrent quota/budget reservations → no overshoot/double charge (GE-07.1/07.2).
5. Identity deleted before uncertain usage returns → detached charge remains; no owner recreation (GE-07.2/07.3).

## Lock and fencing contract

Use sorted users → guest global admission advisory lock → guest_usage → budget day → reservation → operation link → AiUsage → AiRun/resource. Quota claim code checks existing link without locking while owner/admission gates serialize; insert an uncommitted claim or use existing claim, attach budget reservation before locking/updating that existing link. Never lock an existing operation link and then wait for budget. Preserve existing sorted users→pair→resource for social. A settlement holding only budget/reservation locks must **never then acquire a user or operation-link lock**. Finish the quota claim in a separate owner-ordered transaction after settlement; a missing/deleted claim is a no-op. Read reservation.day without lock to locate budget; then acquire budget and reservation in canonical order. Cleanup claim transaction locks only job, commits lease, then processing transaction locks owner before rechecking job/fence. Never hold job lock while waiting for owner in a separate claim path. Mapped intent recovery also follows owner→attempt (initial grant has no existing owner). Existing registered accounting lock order is not rewritten.

No network/provider I/O while DB locks held. 30s cleanup lease, attempts/backoff below; lease token checked before every publication/commit, missing owner/job fails closed. Late workers use UPDATE existing-only, never upsert a deleted owner/usage/job.

## Exhaustive active-store deletion inventory

This inventory was checked against all 38 ORM tables at the inspected SHA, including FK variants. GE-06.1 test must derive an ownership/FK coverage set from metadata and fail when a new table is unclassified. One user canary and one registered peer canary per applicable store. Query via SQLAlchemy bound parameters, never string interpolation of identity data.

| Resource / ownership                                                                                                                           | Creation path                   | Purge order/action and verification oracle                                                                                                                                                                                            |
| ---------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| auth_sessions.user_id / provider_session_id                                                                                                    | Auth BFF                        | Revoke first; hard-delete after private rows, count user_id=0. No FK cascade today.                                                                                                                                                   |
| age_declarations.user_id                                                                                                                       | record_age                      | Delete after content; count 0.                                                                                                                                                                                                        |
| consents.user_id; consent_events.user_id                                                                                                       | consent routes/grant            | Delete events then consents, count 0; registered worker currently leaves these.                                                                                                                                                       |
| ai_messages.conversation_id/run_id                                                                                                             | persistent AI finalization      | Delete conversations cascades messages; verify by saved pre-purge conversation/run IDs too.                                                                                                                                           |
| ai_conversations.user_id; ai_preferences.user_id                                                                                               | AI routes                       | Delete; count 0; both user cascade exists but verify explicitly.                                                                                                                                                                      |
| ai_turns.user_id/session_id/run_id/conversation_id                                                                                             | AI admission                    | Explicit delete including temporary turns without conversation; session_id is plain UUID, verify saved IDs; remove before runs.                                                                                                       |
| ai_usage.user_id/run_id; ai_runs.user_id                                                                                                       | AI accounting/runtime           | Settle detached liability first, delete usage then runs; late snapshots update 0 rows. Never delete detached daily totals.                                                                                                            |
| memory_proposals.user_id                                                                                                                       | proposal preview/confirm        | Delete owner rows with AI data; private-item source links were removed in migration 0020.                                                                                     |
| memory_embeddings.user_id/memory_id; memory_embedding_jobs.user_id/memory_id                                                                   | approved semantic memory        | Cancel runtime work; memory delete cascades both; verify user_id and saved memory IDs 0, late publish 0.                                                                                                                              |
| memories.user_id/proposal_id                                                                                                                  | explicit approval               | Delete memory rows with AI data; proposal_id is a UUID without FK and still checked.                                                                                         |
| moods.user_id                                                                                                                                  | journal route                    | Delete/count 0; no cascade assumed.                                                                                                                                          |
| identity_fields.user_id                                                                                                                        | own identity settings           | Delete/count 0. Guest reveal permissions forbidden.                                                                                                                                                                                   |
| idempotency_keys.user_id; outbox.user_id/resource_id                                                                                           | write receipts; retired outbox  | Delete all owner rows, not only 24h expired; count 0.                                                                                                                                                                                 |
| data_jobs.user_id                                                                                                                              | exports/partial deletion        | Delete after cancelling work and clearing RAM; no queued user work may reinsert.                                                                                                                                                      |
| matching_drafts.user_id; published_profiles.user_id; candidate_references.user_id/peer_id                                                      | forbidden social routes         | Expected 0. Delete guest-owned drafts/profiles and derived candidate refs either side. Never remove unrelated registered drafts.                                                                                                      |
| blocks.blocker_id/blocked_id; connection_reads.user_id/connection_id                                                                           | forbidden social writes         | Expected 0. Guest-only/derived rows may be deleted in reviewed dependency order; reads belonging solely to peer stay if parent retained as incident.                                                                                  |
| pairs.low_user_id/high_user_id; connection_requests.sender_id/recipient_id/pair_id; connections.low_user_id/high_user_id/pair_id               | forbidden pairing               | Expected 0. For purely disposable malformed graph, delete child refs/reveals/activity/message/read rows then requests/connections then pairs. If counterpart-authored records/evidence exist, incident_required; no blind cascade.    |
| human_messages.sender_id/connection_id                                                                                                         | forbidden human messages        | Expected 0. Delete guest-authored messages in disposable corruption fixture. Preserve registered-authored content; nonnullable FK to retained guest then prevents hard delete until reviewed incident resolution.                     |
| activity_responses.user_id/session_id; activity_participants.user_id/session_id; activity_sessions.inviter_id/invitee_id/pair_id/connection_id | forbidden shared activities     | Expected 0. Guest-only malformed graph: responses/participants then session. Real counterpart participation ->incident, retain evidence.                                                                                              |
| reveal_access.owner_id/recipient_id/connection_id                                                                                              | forbidden reveal                | Expected 0. Revoke at cutoff; remove guest-only/derived grants, never disclose field values; any safety evidence remains incident-held.                                                                                               |
| reports.reporter_id/subject_id/connection_id; moderation_actions.subject_id/staff_id/report_id; staff_roles.user_id                            | forbidden safety/staff activity | Expected 0. Unexpected role revoked; content/evidence retained under incident_required, alert operator. Synthetic guest-only corrupted rows can be deleted explicitly in tests; do not erase real peer report to force purge success. |
| matching_stats_daily (no identity)                                                                                                             | registered aggregate workers    | Do not delete/reset; guest must not contribute personal/social rows. Existing aggregate retention unchanged.                                                                                                                          |
| guest_usage.user_id; guest_operation_links.user_id                                                                                             | guest admission                 | Reconcile liability, delete links then usage, count 0. No refund of prior spend.                                                                                                                                                      |
| guest_abuse_buckets keyed identity digest or network HMAC                                                                                      | admission/rate limits           | Delete computed identity scopes; retain network security buckets≤24h with no direct UUID link. Never store IP on user/feedback.                                                                                                       |
| feedback_submission_receipts.user_id/feedback_id                                                                                               | GE-10 submission                | Delete receipt, retained app_feedback has no identity FK/column. Feedback review events reference feedback/staff only; guest staff impossible.                                                                                        |
| guest_provisioning_attempts.user_id/provider_subject/provider_session_id/provider_correlation                                                  | intent/grant                    | Delete entire granted/resolved attempt during purge; do not leave SET NULL row containing provider IDs/correlation. Ambiguous unrelated attempts remain targeted retry work until resolved.                                           |
| guest_cleanup_jobs.user_id; users.id/auth_subject                                                                                              | grant                           | Guarded provider delete, dependent rows then cleanup/session/user hard delete in same DB transaction; all counts 0. Completed jobs do not retain tombstone UUID.                                                                      |
| auth.users and child identities/sessions/refresh/MFA                                                                                           | Supabase signup                 | Delete only verified mapped anonymous subject, confirm absence; hosted cascade must be proven GE-01.2. Fake child cascade only proves local fixture.                                                                                  |
| ConversationStore, AiRuntime.runs/events/proposals/mood evidence; exports; voice tasks/bytes                                                   | personal runtime                | At T/end and purge cancel/drop all owner references including terminal runs (invalidate currently leaves some run metadata). No forensic RAM-zeroization claim. Worker registry prevents late publication.                            |
| React caches/drafts/audio/blob URLs/tour; downloaded copies                                                                                    | browser                         | GE-09.2 abort/unmount/revoke URLs; copied/downloaded content cannot be recalled remotely.                                                                                                                                             |
| guest_budget_days; guest_cost_reservations (no identity)                                                                                       | paid admission                  | Retain spent/uncertain liability; resolved random reservation records≤24h after terminal plus settlement completion; daily totals proposed 30d. Never cascade from users.                                                             |
| Logs/provider data/backups/storage                                                                                                             | operations/external services    | Verify redaction/retention, isolated restore filter; no active object-storage integration found. Inventory hosted Storage/Realtime exposure under GE-01.2. Do not infer backups erased from SQL counts.                               |

**Unexpected social evidence policy:** valid guests cannot create it after GE-03.2. Cleanup may remove guest-only synthetic/derived data. If a real registered counterpart or safety audit must be retained, keep the guest permanently nonactive, set job incident_required, preserve minimal restricted retry target, raise an alert. Full purge is not complete until an owner-approved incident procedure resolves nonnullable references. This is an explicit failure state, not an undeclared tombstone exception or reactivation. Release proof seeds both clean purge and incident paths.

## Provider helper contracts

Migration 0017 owns private reviewed helpers and matching fixture installation:

- `moodprint.delete_guest_provider_identity(app_user_id uuid) RETURNS boolean`: lock/map internal guest nonactive/expired, ensure provider subject is anonymous and no registered mapping; delete exact auth.users row, return true only if absent afterward. Missing already-deleted subject is true; permanent/mismatched/multiply-mapped identity raises controlled error and aborts purge.
- `moodprint.find_guest_orphan_subjects(attempt_id uuid) RETURNS TABLE(subject_id uuid)`: lookup stored random correlation only, dispatched/ambiguous/orphan_pending state, stale lease, auth.users.is_anonymous IS TRUE, created_at between signup_started_at−5s and signup_started_at+60s, no app user mapping. Do not accept raw subject/marker from browser. Window bounds are engineering defaults matched to 10s request timeout; late unexpected row outside window triggers investigation, never broad deletion.
- `moodprint.delete_orphan_guest_identity(attempt_id uuid) RETURNS text`: repeat **all** guards under locks; one match ->deleted; zero ->not_found; multiple/unexpected ->incident_required. Never delete registered/mapped identity, never auth-wide anonymous purge.

These narrow bridges need SECURITY DEFINER because runtime cannot read Auth directly; empty search_path, schema-qualified tables, no PUBLIC/anon/authenticated/service_role execution, intended runtime role only. Returned subject is internal worker data, never HTTP/log. Current registered `delete_provider_identity` behavior stays unchanged.

### Task GE-06.1 — Purge the full guest footprint atomically

**Objective:** Hard-delete allowed active stores and safe provider identity. **Priority:** P0. **Dependencies:** GE-05.4.

**Architecture:** Dedicated guest lifecycle; owner/fence guarded single shared-DB transaction and best-effort RAM invalidation.

**Files:** Create `backend/app/modules/guests/lifecycle.py`; Test `backend/tests/test_guest_cleanup.py`; modify migration 0017, `backend/tests/conftest.py`, `backend/app/ai/runtime.py`, `backend/app/modules/users/lifecycle.py` only to exclude guest account jobs/reuse narrow primitives. Registered tombstone worker remains separate.

**Interfaces:** `purge_guest(db: AsyncSession,user_id: UUID,lease_token: UUID)->Literal['removed','incident_required','fenced']`; helper above. Produces exhaustive inventory assertions; consumes expire_guest, existing deadlines, detached accounting settlement interface from GE-07.2 (until producer lands, paid flags remain off and no paid rows exist; integration dependency explicitly completed in 07.3).

- [ ] Step 1: Write `test_purge_removes_every_guest_owned_store`: seed currently produced allowed inventory+fake Auth child rows, expire, purge, assert zero across all owner/FK variants and saved IDs; registered canaries unchanged. GE-10.3 later adds feedback-survival/receipt-unlink assertions when those models exist. Add `test_purge_preserves_peer_evidence_as_incident` and `test_late_writer_cannot_resurrect`.

Representative assertions (arranged entities/responses/observations from the named tests):

```python
assert all(count == 0 for count in guest_reference_counts.values())
assert registered_after == registered_before
assert second_purge_created_rows == 0
```

- [ ] Step 2: `uv run --locked pytest -q tests/test_guest_cleanup.py` -> missing purge/helper fails.
- [ ] Step 3: Implement inventory deletion order and guarded helper. Since feedback tables are produced later GE-10.1, initial test covers current metadata only; GE-10.3 adds the final receipt/feedback assertion. Do not add placeholder feedback ORM/table. For unexpected counterpart evidence mark incident before destructive processing, preserve rows. Remove attempt/provider/correlation metadata and all sessions/jobs before user deletion.
- [ ] Step 4: Same pytest ->PASS; transaction injection midway/provider helper failure rolls back all SQL; repeat completed purge is safe.
- [ ] Step 5: `uv run --locked pytest -q tests/test_data_lifecycle.py tests/test_retention.py tests/test_guest_embeddings.py tests/test_guest_inflight.py`.
- [ ] Step 6: Run inventory meta-coverage test under runtime privileges, inspect helper delete result and registered identity canary; no .env/real Auth rows.
- [ ] Step 7: Commit `feat(guests): purge temporary identities and active data`.

**Acceptance:** Clean path leaves no app identity or linked metadata; incident path never claims deletion complete. **Edge cases:** duplicate helper call, provider absent, FK anomaly, in-flight accounting. **Rollback:** stop entry, keep worker/denial. **Completion evidence:** bound zero-count queries and registered canary equality, no identifiers printed.

### Task GE-06.2 — Recover cleanup and reconcile orphan attempts

**Objective:** Durable progress after failure without starvation/reactivation/signup repetition. **Priority:** P0. **Dependencies:** GE-06.1.

**Architecture:** Dedicated worker/reconciler tasks isolated from activity/retention failures.

**Files:** Create `backend/app/modules/guests/jobs.py`; Test `backend/tests/test_guest_cleanup_recovery.py`; modify `backend/app/main.py`, migration 0017, `backend/app/jobs/retention.py`.

**Interfaces:** `process_guest_cleanup(app: FastAPI)->int`; `reconcile_guest_provisioning(app: FastAPI)->int`; orphan helpers above. Bounded claim batches 10, one purge transaction at a time, every 1s; independent try/catch per work class. Error codes allowlisted, no SQL/provider payload. Metrics content-free: guest_cleanup_lag_seconds, guest_cleanup_retry_count, guest_orphan_count, guest_incident_count.

- [ ] Step 1: Write `test_worker_crash_rolls_back_then_retries`, `test_lost_lease_cannot_finish_cleanup`, `test_failure_never_reactivates_guest`, `test_marker_recovers_crash_before_subject_persist`, `test_empty_orphan_lookup_never_reissues_signup`. Assert 401 at T with worker stopped and activity worker still advances after guest purge failure.

Representative assertions (arranged entities/responses/observations from the named tests):

```python
assert expired_request.status_code == 401
assert signup_calls_for_attempt == 1
assert stale_worker_committed_changes == 0
```

- [ ] Step 2: `uv run --locked pytest -q tests/test_guest_cleanup_recovery.py` -> missing recovery/marker guards fail.
- [ ] Step 3: Implement 30s fenced leases and exponential bounded retries (5s,15s,60s,300s,900s, then hourly alerted retry). attempts never clears status/deadline; no existing _release_exhausted reactivation logic. Pending/ambiguous signup lease stale ->reconcile; zero-match polls at 5s/30s/5min then hourly for 24h, thereafter incident_required with continued operator/reconciliation visibility. Never resend signup on same attempt.
- [ ] Step 4: Same tests ->PASS; duplicate/mismatched/modified markers trigger no delete and alert; valid unmapped anonymous target removed once; stale grant fence denied.
- [ ] Step 5: `uv run --locked pytest -q tests/test_activity_sweeper.py tests/test_ai_recovery.py tests/test_retention.py tests/test_guest_cleanup.py`.
- [ ] Step 6: Startup scans expired users missing a job and inserts missing cleanup only after verifying immutable kind/T; no access repair/renewal. Entry flag off still runs both tasks; cancellation on app shutdown awaited.
- [ ] Step 7: Commit `feat(guests): recover cleanup and reconcile provider orphans`.

**Acceptance:** Start/completion lag monitored, retries durable, ambiguous work not abandoned, no broad auth scan. **Edge cases:** helper permission denied, DB outage, process dies after provider deletion before transaction commit, clock/lease loss. **Rollback:** guest workers remain on compatible version. **Completion evidence:** restart/lease/fault tests and content-free alert output.

## Quota/configuration contract

GE-02.2 defines Settings fields, GE-07 owns behavior. Flags listed in index default false; additional settings:

| Setting/default                                                                                                                     | Validation/semantics                                                                                                                                                                                                  |
| ----------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| GUEST_DAILY_BUDGET_USD=null                                                                                                         | Decimal string -> integer nano-USD, positive when paid enabled. Unset/zero is unavailable, never unlimited. Owner D02 numerical approval still required.                                                              |
| GUEST_PRICING_JSON={}                                                                                                               | Validated server-only mapping kind/model→pricing_version, input/cached/output nano rates, max input/context tokens, voice rate+rounding quantum, embed request bound. Unknown/missing ->paid unavailable. No secrets. |
| GUEST_ABUSE_HMAC_KEY unset                                                                                                          | SecretStr,≥32 random bytes, required for public guest/feedback admission. Explicit rotation epoch; retain prior key only≤24h as needed for existing windows. Never expose.                                            |
| GUEST_CAPTCHA_SITE_KEY unset                                                                                                        | Public readiness key; provider CAPTCHA verification occurs upstream; if adding app verification, separate server secret never exposed.                                                                                |
| GUEST_AI_TURNS=25; GUEST_AI_PER_MINUTE=6; GUEST_AI_CONCURRENCY=1; GUEST_AI_GLOBAL_CONCURRENCY=10                                    | Positive integer, cannot exceed existing AI global cap. Also enforce existing global 50/user registered policy.                                                                                                       |
| GUEST_VOICE_CLIPS=6; GUEST_VOICE_SECONDS=180; GUEST_VOICE_PER_MINUTE=2; GUEST_VOICE_CONCURRENCY=1; GUEST_VOICE_GLOBAL_CONCURRENCY=3 | Per clip≤30s and≤3MB; use integer milliseconds, upward rounding for cost.                                                                                                                                             |

Other engineering limits remain constants with tests: creation 3/IP/hour,10/IP/day; intent 10/IP/10min,100 globally/min; failed signup 10/IP/10min; max 2 AI SSE/guest,10 live conversations,50 approved memories,100 pending proposals,20 distinct approved semantic memory IDs/trial. AI/voice request rate windows are fixed UTC minute buckets; network creation hour/day windows use Asia/Bangkok civil boundaries. No hidden midnight reset of lifetime counters. Document fixed-window burst behavior and monitor it; financial/concurrency caps still reserve every call.

Network keys canonicalize request.client after configured trusted proxy processing; ignore arbitrary forwarded headers. IPv 4-mapped IPv 6 normalized. No device fingerprint. Count in-progress trial reservations against successful creation caps; release only when proven no upstream dispatch, otherwise retain until resolution/window end. Hour/day bucket secret epoch tied to window so secret rotation cannot reset a live window.

### Task GE-07.1 — Enforce shared durable trial quotas

**Objective:** Bound creation/growth/request/concurrency across restart and replay. **Priority:** P0. **Dependencies:** GE-06.2.

**Architecture:** Extend GE-04.1 admission buckets with user lifetime counters and existing global advisory admission.

**Files:** Extend `backend/app/modules/guests/limits.py` created by GE-04.1; Create/Test `backend/tests/test_guest_quotas.py`, `test_guest_abuse.py`; modify `backend/app/modules/guests/intents.py`, `backend/app/ai/{persistence,chat_routes,memory}.py`, `backend/app/modules/profiles/routes.py`, `backend/app/modules/voice/routes.py`.

**Interfaces:** `QuotaClaim(operation_key_hash:str,lease_token:UUID)`; `reserve_guest_quota(db: AsyncSession,user: User,*,kind: Literal['ai','voice','embed'],operation_key: str,payload_digest: str,voice_milliseconds: int=0)->QuotaClaim`; `finish_guest_quota(db:AsyncSession,user_id:UUID,kind:str,operation_key_hash:str,lease_token:UUID)->None`; `guest_quota_view(db:AsyncSession,user:User)->GuestQuota`; consumes canonical_client_key from GE-04.1. Claims use guest_operation_links in state claimed, worker/fence and 45s lease (heartbeat every 5s while logically active), with no financial reservation yet in these isolated quota tests. Active concurrency counts nonterminal unexpired claims for kind/user under the shared admission lock. Matching key/digest returns existing claim without a second counter increment; mismatched digest 409. End/restart marks stale claims interrupted, never replays work; late completion of missing/fenced link is no-op. GE-07.2 attaches reservation atomically before state dispatched; all production paid flags remain off until GE-07.3.

- [ ] Step 1: Write `test_trial_quota_survives_rotation_restart_midnight`:25 accepted unique turns,26th 429 GUEST_QUOTA_EXHAUSTED; same clientMessageId no increment. `test_voice_exact_milliseconds_and_concurrency`:6 clips/180000ms allowed, next clip or 180001ms rejected; 2/min and 1 active; global ceilings 10AI/3 voice. `test_spoofed_forwarded_ip_ignored`: arbitrary header cannot change key.

Representative assertions (arranged entities/responses/observations from the named tests):

```python
assert accepted_ai_turns == 25
assert twenty_sixth_response.status_code == 429
assert maximum_guest_ai_active <= 10
assert maximum_guest_voice_active <= 3
```

- [ ] Step 2: `uv run --locked pytest -q tests/test_guest_quotas.py tests/test_guest_abuse.py` -> no durable quota assertions pass yet.
- [ ] Step 3: Implement locked/shared counters, claims/fences, stable operation keys, rate/growth caps and Retry-After. AI operation key derives existing scope_id/client_message_id; never charge conversation creation or idempotent replay twice. Voice operation key hashes Idempotency-Key, with audio digest in the separate payload_digest; same key/different audio 409, replay of dispatched clip 409 VOICE_ALREADY_PROCESSED, never redispatches/charges twice; UI offers explicit new recording if response lost.
- [ ] Step 4: Same tests ->PASS under multiple independent DB sessions. Verify registered calls retain current limits and reserved headroom.
- [ ] Step 5: `uv run --locked pytest -q tests/test_ai_quota.py tests/test_voice.py tests/test_memory.py tests/test_guest_provisioning.py`.
- [ ] Step 6: Check no HMAC key/raw IP in repr/logs; network buckets expire≤24h, identity buckets purged. DB unavailable means no reservation/dispatch.
- [ ] Step 7: Commit `feat(guests): enforce shared trial quotas`.

**Acceptance:** No logical admission/concurrency overshoot or identity/session-reset loophole; no unbounded queue. Remote requests already accepted may continue after local cancellation/crash; do not claim exact physical remote concurrency or cancellation. Financial liability and trial limits still bound retries. **Edge cases:** two processes in tests despite supported production one worker; rate window boundaries; shared NAT; malformed WAV consumes failed-attempt bucket but no paid clip. **Rollback:** paid/entry off, retain counters. **Completion evidence:** concurrency barriers, accepted/denied counts and no external calls.

### Task GE-07.2 — Reserve detached daily financial liability

**Objective:** Budget survives owner cleanup and uncertain provider failures. **Priority:** P0. **Dependencies:** GE-07.1.

**Architecture:** Integer nano-USD, no owner link in durable accounting, atomic budget+reservation locks.

**Files:** Create `backend/app/modules/guests/accounting.py`; Test `backend/tests/test_guest_budget.py`; modify `backend/app/core/config.py`, `backend/app/modules/guests/lifecycle.py`, `backend/app/jobs/retention.py`, config examples/docs.

**Interfaces:** `reserve_guest_operation(db,user,kind,upper_cost: int,*,operation_key: str,payload_digest: str)->Reservation` with `Reservation(id: UUID,upper_nano_usd: int)`; `settle_guest_operation(db,reservation: Reservation,actual_or_uncertain: int | None)->None`; `mark_guest_dispatched(db,reservation_id: UUID)->None`. Lookup replay through ephemeral operation link; no identity in Reservation row/daily totals.

Reservation algorithm: require no unresolved halted_at on any budget day; lock current budget day; require `spent+reserved+upper<=limit`; add the reserved amount and reservation row atomically, attaching reservation_id to the matching quota claim from GE-07.1 (or creating one only through that quota producer). Never insert a second link or increment the same quota twice. At provider dispatch mark dispatched before invocation. Definite no-dispatch can release reservation once. Known actual≤upper: subtract upper reserved, add actual spent once. Ambiguous/error/crash/missing usage: subtract upper reserved and **charge full upper to spent**, terminal uncertain, no automatic refund. Duplicate settlement no-op if equal, conflicting settlement 409/alert. actual>upper is accounting incident: charge actual, set halted_at=DB time and block new paid work across days until reviewed operator resolution; never expire an unresolved halted row or erase overrun. Budget configuration changes never reset spent/reserved; raising a cap still requires D02 approval.

Bounds: AI reserve for at most 3 requests, each input≤configured published model input/context maximum and output≤1200: `3*(max_input_tokens*max(input_rate,cached_rate)+1200*output_rate)`. Enforce chosen model/limits before each request; unknown context/prices fail closed. This is deliberately conservative; tighter tokenizer estimation is deferred. STT reserve actual validated duration rounded up to provider billing quantum (max 30s/clip); embed reserve configured endpoint input maximum per bounded request; no unknown-price fallback. No speculative numeric prices/budget are supplied.

- [ ] Step 1: Write `test_budget_reservations_prevent_concurrent_overshoot`, `test_uncertain_spend_charges_upper_once`, `test_purging_all_guests_cannot_reopen_daily_budget`, `test_unset_budget_or_unknown_price_fails_closed`. Use tiny **synthetic fixture** integer limits, not an approved production dollar amount.

Representative assertions (arranged entities/responses/observations from the named tests):

```python
assert day.spent_nano_usd + day.reserved_nano_usd <= day.limit_nano_usd
assert new_guest_after_purge_response.status_code == 429
assert uncertain_reservation.charged_nano_usd == uncertain_reservation.upper_nano_usd
```

- [ ] Step 2: `uv run --locked pytest -q tests/test_guest_budget.py` -> missing detached/reserved budget fails.
- [ ] Step 3: Implement algorithm/interfaces and validation. Purge settles all unsettled linked reservations conservatively before deleting links/owner. On restart stale reservations become charged uncertain, never paid replay.
- [ ] Step 4: Same tests ->PASS, including simultaneous settlement/cleanup and calendar midnight with liability charged to original reservation.day.
- [ ] Step 5: `uv run --locked pytest -q tests/test_usage_accounting.py tests/test_guest_cleanup.py tests/test_guest_quotas.py`.
- [ ] Step 6: Inspect retained schema for user/run/provider/session/IP linkage; random reservation records terminal≤24h, unlinked daily totals 30d proposed; never delete a day with outstanding reservations.
- [ ] Step 7: Commit `feat(guests): reserve detached guest spend`.

**Acceptance:** Budget includes in-flight/uncertain AI/STT/embed and remains exhausted after purge. **Edge cases:** actual exceeds upper, timeout before dispatch, lease lost, duplicate key/different content, midnight. **Rollback:** paid off; keep settlement/ledger and never refund on disable. **Completion evidence:** real-DB lock tests, no real billing claim.

### Task GE-07.3 — Connect quota/budget to every paid dispatch

**Objective:** No paid guest path bypasses admission or survives deletion with writable identity state. **Priority:** P0. **Dependencies:** GE-07.2, GE-05.2–05.4.

**Architecture:** Existing runtime hooks/providers and voice/embed adapters consume reservation token; no replacement accounting stack for registered users.

**Files:** Create `backend/app/ai/guest_model.py`; Modify `backend/app/ai/{runtime,provider,persistence,accounting,embeddings}.py`, `backend/app/modules/voice/routes.py`, `backend/app/modules/guests/{accounting,lifecycle,jobs}.py`, `backend/app/main.py`; Test `backend/tests/test_guest_budget.py`, `test_guest_inflight.py`, `test_guest_cleanup.py`.

**Interfaces:** LiveRun holds optional Reservation; no user linkage in late settlement. Before **each** SDK model dispatch, complete usage observer/reservation awaits, then fresh lifetime guard as last awaited authorization before invoking the provider model. Reorder current _BudgetHooks.on_llm_start (which currently calls on_progress before usage observer) to avoid an intervening accounting await; tool hooks similarly guard after observer. Create `GuestGuardedModel(delegate: Model,before_dispatch: Callable[[],Awaitable[None]])` in `backend/app/ai/guest_model.py`, implementing pinned SDK Model.get_response/stream_response; invoke before_dispatch immediately before delegating, after SDK queue work. Preserve pinned SDK signatures/types by reading installed interface, cover actual SdkProvider transport in tests. Underlying transport execution is physical dispatch after this logical authorization boundary.

- [ ] Step 1: Add `test_each_paid_adapter_requires_reservation_and_final_lifetime`: AI first/second model, voice, embed; counters/ledger precede call, unavailable flags/pricing zero calls. `test_late_usage_settles_without_recreating_deleted_owner`: purge then delayed observer produces no user/ai_usage row, detached amount remains.

Representative assertions (arranged entities/responses/observations from the named tests):

```python
assert paid_dispatches_without_reservation == 0
assert paid_dispatches_after_T == 0
assert recreated_owner_rows == 0
```

- [ ] Step 2: `uv run --locked pytest -q tests/test_guest_budget.py tests/test_guest_inflight.py tests/test_guest_cleanup.py` -> missing dispatch integration fails.
- [ ] Step 3: Implement wrapper/integration; use configured deadlines and reservation ID for all late settlement. Final snapshot update of missing AiUsage returnsfalse, never inserts. Hold uncertain liability despite cancellation; current global registered accounting remains enforced in addition.
- [ ] Step 4: Same tests ->PASS, including flag off midway, expired queue/slot, retry storms, actual HTTPX fake transport boundary and startup stale reservation handling.
- [ ] Step 5: `uv run --locked pytest -q tests/test_sdk_adapter.py tests/test_ai_quota.py tests/test_usage_accounting.py tests/test_voice.py tests/test_embeddings.py tests/test_guest_cleanup_recovery.py`.
- [ ] Step 6: Confirm GUEST_AUTH_ENABLED can permit journal/private trial while paid features truthfully unavailable; GUEST_PAID_ENABLED requires approved nonzero budget/accounting/model pricing, not a synthetic production fallback. Suppress guest user/provider/run/conversation IDs in existing runtime logs while retaining registered observability; caplog negative assertions cover guest paths. Validate full clean inventory again after accounting integration.
- [ ] Step 7: Commit `feat(guests): gate all paid dispatch with durable liability`.

**Acceptance:** All paid adapters tested; no budget erasure/replay after cleanup/restart. **Edge cases:** cancellation-resistant remote work, semantic disabled, worker dying between dispatched marker and network (charge upper), registered quota errors. **Rollback:** disable paid/entry only; preserve denial, cleanup, settlement and logs without private identifiers. **Completion evidence:** dispatch/settlement event order, counts, full inventory and registered regressions.
