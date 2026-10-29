# Feedback and Administration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (when authorized/available) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collect a required 1–5 rating with optional categories/comment and support safe admin review.

**Architecture:** Independent app_feedback without identity relation; ephemeral receipts implement per-owner limits/idempotency. Registered live admin+12h reauth guards review APIs; shared filters govern list and metrics.

**Tech Stack:** Existing FastAPI/Pydantic/PostgreSQL/Alembic, React/CSS primitives, generated types, pytest/Playwright.

**Spec:** [Feedback design](../04-feedback-system-design.md), [D03](../07-risks-and-open-decisions.md), [guest deadline](02-guest-expiry-and-permissions.md), [index constraints](00-implementation-index.md#global-constraints).

## Global Constraints

FEEDBACK_ENABLED/FEEDBACK_ADMIN_ENABLED default false, proposed 180d policy requires D03 before public collection. Only active eligible guest/registered submitters; no post-expiry token/extension. No automatic private attachment, identifying metadata, user-history join, paid moderation, Markdown/HTML rendering or persistent browser draft. Existing activity feedback and safety reports remain independent.

## Review Focus

1. Rating-only and Unicode emoji/control boundary → consistent strict validation (GE-10.1/10.2).
2. Lost response/concurrent requests/expiry → one receipt/row or rolled-back insert (GE-10.2).
3. Guest purge → retained feedback without receipt/provider/session/user relationship (GE-10.3).
4. Admin role revoked while update queued → live locked role check denies (GE-11.1).
5. Empty/spam/multicategory filters → identical list/summary cohort, null mean if 0 (GE-11.2).

## Canonical schema (GE-10.1)

Create migration `backend/alembic/versions/0018_app_feedback.py` after 0017, or next rebased free revision per plan 01. Runtime-only private grants/RLS; all CRUD denied anon/authenticated/service_role; no public insert policy. Add models to Alembic/test metadata imports.

| Table                        | Exact fields/constraints/indexes                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| ---------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| app_feedback                 | id UUID PK; rating SMALLINT NOT NULL CHECK between 1 and 5; categories TEXT[] NOT NULL default{}; comment TEXT NULL CHECK char_length≤1000 and no NUL/disallowed controls; app_version VARCHAR(64) NOT NULL server release or unknown; context VARCHAR(16) checked allowlist; account_kind VARCHAR(10) guest/registered snapshot; disclosure_version VARCHAR(32) feedback-v 1; created_at TIMESTAMPTZ NOT NULL database time; status VARCHAR(12) new/reviewed/planned/resolved/spam default new; version INTEGER>0 default 1; reviewed_at TIMESTAMPTZ NULL. Index(created_at,id), index(status,created_at,id). No user_id/auth_subject/session_id/IP/run/conversation/device/URL or hashed surrogate identity. |
| feedback_submission_receipts | id UUID PK; user_id REFERENCES users ON DELETE CASCADE; idempotency_key VARCHAR(128); payload_digest CHAR(64); feedback_id REFERENCES app_feedback ON DELETE CASCADE; created_at TIMESTAMPTZ; UNIQUE(user_id,idempotency_key); index(user_id,created_at). CASCADE direction is feedback→receipt, never receipt→feedback.                                                                                                                                                                                                                                                                                                                                                                                       |
| feedback_review_events       | id UUID PK; feedback_id REFERENCES app_feedback ON DELETE CASCADE; staff_id REFERENCES users ON DELETE RESTRICT (registered staff only); action status/redact; from_status/to_status nullable checked enum; resulting_version positive; created_at TIMESTAMPTZ. No comment/body copy. Retention follows feedback. Admin writes also use existing Idempotency receipts; those reference only resource/version, not comment.                                                                                                                                                                                                                                                                                     |

Categories exactly `ease_of_use,ai_quality,interface,performance,bug,missing_feature,privacy_trust,other`. Enforce subset, no null elements, cardinality≤8 and uniqueness in DB via `moodprint.feedback_categories_valid(items text[]) RETURNS boolean`, private immutable array-validation function (SQL cannot use an arbitrary subquery in CHECK); function has explicit search_path/private grants. API rejects repeated codes rather than silently deduplicating, then stores canonical enum order. Unknown fields rejected. Mirror comment control/length policy with private immutable `moodprint.feedback_comment_valid(value text) RETURNS boolean`; NULL is accepted, and checks do not authorize access.

Context exactly `general,assistants,mood,memory,privacy,activities,trial_end`; no raw route/query/title/ID. Comment trim Unicode whitespace, empty→null; max 1000 Unicode code points **before trimming as well as after**, reject NUL/C0 controls except tab/LF/CR, reject C1/DEL and invalid surrogate input; store other HTML/SQL-looking text unchanged safely. Pydantic strict int rating rejects bool/string/fraction. Database check mirrors forbidden control policy; test both direct SQL/API. App_version comes from trusted server deployment revision, never client body.

## Canonical API and service contracts

Prefix /api/v 1, existing error envelope and CSRF/Idempotency-Key. New schemas in `backend/app/modules/feedback/schemas.py` derive existing DTO.

| Endpoint                       | Exact request/result/policy                                                                                                                                                                                                                                                                                                                                                                   |
| ------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| POST /feedback                 | `{rating:int,categories:Category[]=[],comment:string\|null=null,context:Context='general',disclosureVersion:'feedback-v1'}`. Eligible live actor+CSRF.201 `{feedbackId:UUID,createdAt:ISO,status:'received'}`; same key/payload returns 200 same receipt. New key after guest success 409 FEEDBACK_ALREADY_SUBMITTED; different payload same key 409 IDEMPOTENCY_CONFLICT.                    |
| GET /feedback/submission-state | Own active actor; `{submitted:boolean,lastSubmittedAt:ISO\|null}`; guest lifecycle receipt or registered last 30d receipt existence. No content/admin status.                                                                                                                                                                                                                                 |
| GET /admin/feedback            | Registered admin, live role,12h reauth, adminflag. `{items:FeedbackAdminView[],nextCursor:string\|null}`; max 50 (default 25). View contains all feedback fields above, no submitter lookup.                                                                                                                                                                                                  |
| GET /admin/feedback/summary    | Same gate/filter cohort, cursor ignored; `{count:int,meanRating:number\|null,ratingCounts:{'1':int,...,'5':int},categoryCounts:Record<Category,int>,accountKindCounts:{guest:int,registered:int},byDate:{date:string,count:int,meanRating:number\|null}[],byVersion:{appVersion:string,count:int,meanRating:number\|null}[]}`. Count included in every mean cohort; categories may sum>count. |
| PATCH /admin/feedback/{id}     | Admin+CSRF+Idempotency-Key; `{status:Status,expectedVersion:int>=1}`; returns FeedbackAdminView. Same status/current version is successful no-op; stale version 409 STALE_VERSION; nonexistent 404. Real transition increments version and reviewed_at=DBtime, inserts content-free review event atomically.                                                                                  |

Filters shared by list/summary: `fromDate,toDate` ISO dates inclusive in **Asia/Bangkok**, default last 30 days ending today, max 180 days, start≤end; convert to UTC half-open [start 00:00,next-day 00:00). Optional exact `appVersion`≤64, `accountKind`, `rating`1..5, `status`, `category`, `includeSpam` false. If explicit status supplied it selects that status (including spam); otherwise exclude spam unless includeSpam. List stable order(created_at DESC,id DESC); base 64url cursor contains createdAt/id/filterHash, bounded≤1024, strict parse, reject filter mismatch 422 INVALID_CURSOR. No client-selected SQL identifiers/order. Summary groups dates within range, version rows max 50 with explicit other bucket if needed; use same SQL predicate helper. Do not infer causal product improvement from small cohorts.

Service `submit_feedback(db:AsyncSession,user:User,body:FeedbackInput,key:str,*,network_key:str,app_version:str)->FeedbackReceipt`. Under owner lock: revalidate eligibility/lifetime, check receipt, normalize/digest payload, enforce limits, insert feedback+receipt, final_guest_authorization before commit. Existing output guard handles expiry before response. A valid pre-T insert may commit/deliver later; at/post-T authorization must not create one. A dropped post-T response does not undo a valid pre-T feedback grant; no extension to recover it.

Limits:1 successful feedback/guest lifecycle,1/registered user per Asia/Bangkok calendar day;3 attempts/identity per fixed UTC minute;20 accepted/reserved submissions/network HMAC per fixed hour. Reuse guest abuse buckets, with dedicated scopes for registered identities too; require HMAC config when public collection enabled. Replay key bypasses new accepted counters but still active lifetime, no content-based global deduplication.429 with Retry-After;503 temporary storage;422 validation;403 eligibility/CSRF;401 expiry; disabled endpoint 404.

### Task GE-10.1 — Store minimal unlinked feedback

**Objective:** Private constrained schema and strict DTOs without identity. **Priority:** P1. **Dependencies:** GE-07.3.

**Architecture:** Three tables above, no relation from retained feedback back to submitter.

**Files:** Create `backend/app/modules/feedback/{__init__,models,schemas}.py`, migration 0018; Test `backend/tests/test_feedback_privacy.py`; modify `backend/alembic/env.py`, `backend/tests/conftest.py`, `backend/app/core/revisions.py`, `docs/supabase/schema.md`.

**Interfaces:** Produces `AppFeedback,FeedbackSubmissionReceipt,FeedbackReviewEvent,FeedbackInput,FeedbackReceipt,FeedbackAdminView,FeedbackStatusInput,FeedbackFilters,FeedbackSummary`; canonical fields above. No new fields consumed before backend OpenAPI export in 10.2/11.2.

- [ ] Step 1: Write `test_feedback_schema_has_no_submitter_identity`: inspect columns/FKs, exact allowed fields, receipt deletion preserves feedback, feedback deletion cascades receipts/events. `test_feedback_db_constraints`: direct SQL rating 0/6, duplicate/unknown/null category/control/1001char fails; rating-only succeeds.

Representative assertions (arranged entities/responses/observations from the named tests):

```python
assert not ({"user_id", "auth_subject", "session_id", "ip", "conversation_id"} & set(feedback_columns))
assert retained_feedback_count_after_receipt_delete == 1
assert public_role_crud_privileges == set()
```

- [ ] Step 2: `uv run --locked pytest -q tests/test_feedback_privacy.py` -> missing models/constraints fails.
- [ ] Step 3: Implement tables/validator/private function/migration and metadata registration, timestamp defaults, indexes/grants.
- [ ] Step 4: Same tests ->PASS; separate disposable migration DB upgrade/check as plan 01, head 0018 and no drift.
- [ ] Step 5: `uv run --locked pytest -q tests/test_guest_schema.py tests/test_activity_schema.py tests/test_readiness.py`; root `python scripts/check_docs.py`.
- [ ] Step 6: Review all CRUD permissions and check expressions with NULL/Unicode/control values, staff FK cannot point to guest via service checks.
- [ ] Step 7: Commit `feat(feedback): add unlinked constrained storage`.

**Acceptance:** No permanent identity relationship; consistent direct DB/API validation. **Edge cases:** SQL CHECK null semantics, emoji vs UTF16 units, invalid UTF8, deletion cascade direction. **Rollback:** collectionoff, keep table/retention. **Completion evidence:** migration/runtime-privilege tests and schema/FK assertions.

### Task GE-10.2 — Submit feedback atomically with limits

**Objective:** Low-friction rating-only submission safely replayed while authorized. **Priority:** P1. **Dependencies:** GE-10.1.

**Architecture:** Receipt/feedback insert one transaction, shared quota locks, no LLM.

**Files:** Create `backend/app/modules/feedback/{service,routes}.py`; Test `backend/tests/test_feedback.py`; modify `backend/app/main.py`, `backend/app/modules/guests/limits.py`, `backend/openapi.json`, `frontend/src/api/{contracts.ts,generated/schema.d.ts}`, `docs/backend/api-reference.md`.

**Interfaces:** Produces submit_feedback and two user endpoints above; consumes lifetime/transaction, network bucket and flags from earlier tasks.

- [ ] Step 1: Write `test_rating_only_guest_and_registered`:201, categories[],commentnull. Parameterize bool/'5'/1.5/0/6, category duplicate,1000/1001 codepoints incl emoji, controls, metadata fields->422. `test_concurrent_feedback_replay_and_expiry`: same key yields 1row/receipt, changedpayload 409, new guest key 409; final check at T rolls back both/counters.

Representative assertions (arranged entities/responses/observations from the named tests):

```python
assert response.status_code == 201
assert saved_feedback.rating == 5
assert saved_feedback.categories == []
assert saved_feedback.comment is None
```

- [ ] Step 2: `uv run --locked pytest -q tests/test_feedback.py` -> missing endpoint/validation fails.
- [ ] Step 3: Implement contracts and normalization; registered daily limit on receipt.created_at in BKK day; no user snapshot in feedback beyond kind. No provider/memory/journal/screenshot/URL attachment accepted.
- [ ] Step 4: Same command ->PASS; HTML/SQL-looking comment survives as harmless text; no SQL exception body/log.
- [ ] Step 5: `uv run --locked pytest -q tests/test_feedback_privacy.py tests/test_guest_inflight.py tests/test_guest_budget.py`; export OpenAPI/generate TS/typecheck; update API inventory.
- [ ] Step 6: Check CSRF/origin/eligibility/flagoff 404, Retry-After, registered/guest receipt windows, no correlation in logs.
- [ ] Step 7: Commit `feat(feedback): add idempotent rating submission`.

**Acceptance:** Rating alone works, guest form cannot extend lifetime, no accepted-counter double charge. **Edge cases:** lost response, post-T response drop, storage 503, expiry during owner-lock wait, independent identical comments. **Rollback:** FEEDBACK_ENABLED=false stops new writes but retention/receipt purge continue. **Completion evidence:** concurrency/body/negative endpoint tests.

### Task GE-10.3 — Remove links and enforce feedback retention

**Objective:** Retain only voluntarily disclosed independent feedback while deleting guest identity. **Priority:** P1. **Dependencies:** GE-10.2, GE-06.2.

**Architecture:** Delete guest receipt on purge, registered receipt 30d/account deletion; feedback/review events 180d proposed.

**Files:** Create `backend/app/modules/feedback/retention.py`; Test `backend/tests/test_feedback_retention.py`; extend `test_feedback_privacy.py`, `test_guest_cleanup.py`; modify `backend/app/modules/guests/lifecycle.py`, `backend/app/modules/users/lifecycle.py`, `backend/app/jobs/retention.py`; create `docs/guest-experience/implementation/evidence/feedback-operations.md`.

**Interfaces:** `purge_feedback(db:AsyncSession,*,batch_size:int=500)->int`; DB time cutoff created_at≤clock−180 days; receipts≤30 days for registered, guest only during active identity; bounded batches per retention tick. No retained long-term aggregates inMVP. Operator runbook uses receipt ID to locate independent feedback, reviewed protected SQL can null/redact comment and append content-free action=redact; do not execute it on hosted DB without separate approval.

- [ ] Step 1: Write `test_guest_purge_leaves_feedback_without_any_identity_link`: submit→expire→purge, feedback remains, zero user/session/receipt/attempt/provider references, schema has no identity join. `test_feedback_retention_exact_cutoff`:180d boundary deleted including events/receipts, just newer stays; registered receipt 30d gone, feedback remains. Registered account deletion drops receipt but follows existing user tombstone behavior.

Representative assertions (arranged entities/responses/observations from the named tests):

```python
assert retained_feedback_count == 1
assert guest_receipt_count == 0
assert all(count == 0 for count in guest_reference_counts.values())
```

- [ ] Step 2: `uv run --locked pytest -q tests/test_feedback_retention.py tests/test_feedback_privacy.py` -> missing purge/separation integration fails.
- [ ] Step 3: Implement final inventory integration and bounded retention independent of feature flags; document redaction/restore workflow and no account-based retrieval promise.
- [ ] Step 4: Same command ->PASS plus `uv run --locked pytest -q tests/test_guest_cleanup.py`.
- [ ] Step 5: `uv run --locked pytest -q tests/test_data_lifecycle.py tests/test_retention.py tests/test_guest_cleanup_recovery.py`.
- [ ] Step 6: Review backup restore filtering/retention and voluntary identifying comments/timing correlation: no irreversible anonymization claim.
- [ ] Step 7: Commit `feat(feedback): unlink receipts and enforce retention`.

**Acceptance:** Guest deletion survives independently retained feedback without identity FK/hash; policy still unapproved for public launch. **Edge cases:** feedback deleted before receipt replay, redaction after backup, featureoff. **Rollback:** keep retention even collectionoff. **Completion evidence:** before/after counts, FK schema and registered deletion tests.

### Task GE-11.1 — Separate feedback staff gate from moderation

**Objective:** Live permanent admin authorization with current reauth at mutation. **Priority:** P1. **Dependencies:** GE-10.3.

**Architecture:** Parameterize existing staff gate without changing moderation defaults; recheck locked role before protected update.

**Files:** Create `backend/app/modules/feedback/admin_routes.py`; Test `backend/tests/test_feedback_admin.py`; modify `backend/app/modules/moderation/staff.py`, `backend/app/main.py`.

**Interfaces:** Extend `require_staff(role:str='moderator',*,feature:Literal['moderation','feedback']='moderation')`; feedback uses require_staff('admin',feature='feedback'). Produces `assert_feedback_admin(db:AsyncSession,actor:Actor,*,lock:bool=False)->Staff`: revalidate actor, require_registered_user, live StaffRole(admin), session.reauthenticated_at within 12h (fresh DB time for guest-aware policy). Mutation lock owner→StaffRole before feedback resource; role revocation serializes on role row. Flag off 404 remains.

- [ ] Step 1: Add `test_feedback_admin_role_and_reauth_matrix`: guest with forged admin row denied, normal/moderator 403, admin stale reauth 403 REAUTH_REQUIRED, fresh admin allowed, feedbackflagoff 404 independently of moderation flag. `test_revoked_role_cannot_update_after_wait`: revoke before final locked check, no event/update.

Representative assertions (arranged entities/responses/observations from the named tests):

```python
assert guest_admin_response.status_code == 403
assert moderator_response.status_code == 403
assert revoked_role_update_count == 0
```

- [ ] Step 2: `uv run --locked pytest -q tests/test_feedback_admin.py -k 'role or reauth or flag'` -> missing independent gate fails.
- [ ] Step 3: Implement reusable feature gate and transaction recheck, do not authorize from SessionView.staff/client metadata. Password step-up remains registered flow.
- [ ] Step 4: Same command ->PASS.
- [ ] Step 5: `uv run --locked pytest -q tests/test_moderation_admin.py tests/test_auth_flows.py tests/test_guest_permissions.py`; extend operation classification map for new routes.
- [ ] Step 6: Review role update/revocation lock order and no client role assignment path.
- [ ] Step 7: Commit `fix(feedback): protect review with live admin authorization`.

**Acceptance:** Backend denies direct routes; moderation behavior unchanged. **Edge cases:** session missing, age unknown, suspended admin, role deletion midtransaction. **Rollback:** independent adminflagoff, backend gate remains. **Completion evidence:** full matrix and revocation barrier.

### Task GE-11.2 — Query metrics and update review status

**Objective:** Bounded consistent analytics and optimistic review transitions. **Priority:** P1. **Dependencies:** GE-11.1.

**Architecture:** Single shared parameterized filter predicate; status/audit/receipt atomic.

**Files:** Create `backend/app/modules/feedback/queries.py`; modify `admin_routes.py`, `schemas.py`; Test `backend/tests/test_feedback_admin.py`; update `backend/openapi.json`, `frontend/src/api/{contracts.ts,generated/schema.d.ts}`, `docs/backend/api-reference.md`.

**Interfaces:** `list_feedback(db,filters:FeedbackFilters,cursor:str|None,limit:int)->FeedbackPage`; `summarize_feedback(db,filters:FeedbackFilters)->FeedbackSummary`; `review_feedback(db,staff:Staff,id:UUID,body:FeedbackStatusInput,key:str)->FeedbackAdminView`. Exact filters/DTOs above.

- [ ] Step 1: Add `test_feedback_filters_share_summary_cohort`: seeded scores 1/5/multicategory/spam/version/day; sum ratingCounts=count, mean with correct sample, zero→null; category sum may exceed count; explicit spam filter consistency. `test_review_conflict_and_idempotency`: stale 409, replay no second event, differentpayload 409; no comment in audit.

Representative assertions (arranged entities/responses/observations from the named tests):

```python
assert summary.count == 2
assert summary.mean_rating == 3
assert sum(summary.rating_counts.values()) == summary.count
assert empty_summary.mean_rating is None
```

- [ ] Step 2: `uv run --locked pytest -q tests/test_feedback_admin.py -k 'filter or summary or review or cursor'` -> missing queries fails.
- [ ] Step 3: Implement cursor/filter bounds/date conversion/status transaction; emit all/only specified metadata. No free SQL sorting or query identifiers; no user-history joins.
- [ ] Step 4: Same command ->PASS, including malformed cursor/date/window/multicategory and role-CSRF failures.
- [ ] Step 5: `uv run --locked pytest -q tests/test_feedback_admin.py tests/test_moderation_admin.py`; regenerate contracts/typecheck and docs inventory.
- [ ] Step 6: Inspect query plans on synthetic bounded sample; use existing created/status indexes; add app_version index only if measured plan justifies it, in unshipped 0018 or next revision with recorded reason.
- [ ] Step 7: Commit `feat(feedback): add bounded review and rating metrics`.

**Acceptance:** Lists/metrics align, empty mean never 0/5, no overwrite race or private drilldown. **Edge cases:** feedback retention deletes current row, cursor filter changes, status-noop, simultaneous admins. **Rollback:** adminflagoff; no destructive rollback. **Completion evidence:** seeded exact metric oracles/query and status tests.

### Task GE-12.1 — Add mobile-friendly voluntary form

**Objective:** Accessible rating-only UI with optional detail. **Priority:** P1. **Dependencies:** GE-09.2, GE-11.2.

**Architecture:** Explicit settings/footer entry, no automatic conversation prompt; local React draft only.

**Files:** Create `frontend/src/features/feedback/FeedbackPage.tsx`, `feedback.css`; Test `frontend/tests/e2e/feedback.spec.ts`, `frontend/tests/fullstack/guest-feedback.spec.ts`; modify `frontend/src/features/real/RealApp.tsx`, `Privacy.tsx`, `frontend/src/features/public/LandingPage.tsx`.

**Interfaces:** `FeedbackPage()` uses existing session context/generated DTOs; no-session #/feedback shows explanation/trial/login before private Shell; expired guest uses lifecycle handler. GET submission-state suppresses repeat success UX; no admin status leaked.

- [ ] Step 1: Browser “rating-only submits”, “keyboard ratings have no preselection”, “optional categories/comment”, “busy duplicate and transient same key retry”, “expiry clears draft”, “malicious text stays text”. Payload assertion exact fields only, no URL/private IDs; fullstack guest submit→purge→feedback retained.

Representative assertions (arranged entities/responses/observations from the named tests):

```typescript
await expect(
  page.getByRole("button", { name: "G?i g?p ?", exact: true }),
).toBeVisible();
expect(submittedBody.categories).toEqual([]);
expect(submittedBody.comment).toBeNull();
```

- [ ] Step 2: `npm.cmd exec -- playwright test --config playwright.owned.config.ts feedback.spec.ts` -> missing route/form fails.
- [ ] Step 3: Implement native fieldset/radios 1 “Rất chưa hài lòng” through 5 “Rất hài lòng”, optional native category checkboxes and 1000-codepoint count using Array.from length, helper “Bạn không cần viết thêm để gửi đánh giá. Đừng gửi thông tin liên hệ, nội dung trò chuyện hay nhật ký riêng tư.” Disclosure immediately above submit, proposed 180d copy only when approved flag enabled. Success “Cảm ơn bạn. MoodPrint đã nhận góp ý.” plus receipt ID user may keep.
- [ ] Step 4: Same command ->PASS at 320/390/1440, keyboard/200%text/axe. Retain draft on 503 only while active; no localStorage/sessionStorage draft.
- [ ] Step 5: Backend harness `uv run --locked python ../scripts/test_fullstack.py guest-feedback.spec.ts --reporter=list`; frontend typecheck/unit/build.
- [ ] Step 6: Verify no forced rating, five-star bias, chat interruption, autoattachment or invisible consent; guest expiry cancels pending setState.
- [ ] Step 7: Commit `feat(feedback): add accessible voluntary rating form`.

**Acceptance:** Minimal friction, successful receipt required before success, retention visible. **Edge cases:** disabled 404, already submitted 409, no rating, offline, underage, post-T response drop. **Rollback:** hide form via capability while retaining privacy text/retention jobs. **Completion evidence:** payload inspection, form/accessibility/fullstack results.

### Task GE-12.2 — Add protected review dashboard

**Objective:** Admin triage and metrics usable without a BI dependency. **Priority:** P1. **Dependencies:** GE-12.1.

**Architecture:** Lazy admin route, existing primitives, escaped text and semantic data display.

**Files:** Create `frontend/src/features/real/admin/Feedback.tsx`; Test `frontend/tests/e2e/feedback-admin.spec.ts`; modify `frontend/src/features/real/RealApp.tsx`.

**Interfaces:** `FeedbackAdmin()` consumes canonical list/summary/PATCH; route /#/admin/feedback shown only registered admin (server enforces actual capability). REAUTH_REQUIRED opens step-up/retry UI, notlogout.

- [ ] Step 1: Browser “guest/user direct dashboard denied”, “admin empty/error/reauth/filter”, “rating bars show counts and sample”, “status 409 reload preserves focus”, “HTML-looking comment rendered literal”; no links to private histories.

Representative assertions (arranged entities/responses/observations from the named tests):

```typescript
await expect(
  page.getByText("<script>private-canary</script>", { exact: true }),
).toBeVisible();
expect(privateHistoryRequests).toHaveLength(0);
```

- [ ] Step 2: `npm.cmd exec -- playwright test --config playwright.owned.config.ts feedback-admin.spec.ts` -> missing dashboard fails.
- [ ] Step 3: Build date/version/kind/rating/status/category filters with stated BKK timezone, total/mean/sample, text rating bars, category counts labelled multi-select, semantic review table with mobile cards/overflow region labelled accessibly; load more cursor, versioned status select/button.
- [ ] Step 4: Same command ->PASS with keyboard/reduced motion/200%text/mobile, no dangerouslySetInnerHTML/Markdown parser.
- [ ] Step 5: Owned `admin.spec.ts feedback.spec.ts`; frontend typecheck/build; backend `uv run --locked pytest -q tests/test_feedback_admin.py`.
- [ ] Step 6: Verify loading/error/empty/zero-sample states, role revocation clears loaded data on 403; no submitter identity joins/telemetry.
- [ ] Step 7: Commit `feat(feedback): add protected review dashboard`.

**Acceptance:** Safe review/status and consistent filter metrics; guest cannot inspect dashboard even forged client staff. **Edge cases:** role revoked while page open, two admins conflict, retention removes row. **Rollback:** independent adminflagoff. **Completion evidence:** UI/API denial, escaped text and filter/status test outputs.
