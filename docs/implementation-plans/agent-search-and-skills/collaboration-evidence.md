# Collaboration defaults backend evidence

Implemented C1/C2 and the offline C4 rollout support from `05-collaboration-defaults.md` on 2026-11-03. C3 UI and generated contracts belong to the parent implementation.

## Changes

- `backend/app/ai/collaboration/grants.py` is the shared resolver for legacy and V3 families. Eligible accounts receive all three legacy or four V3 capability tokens under `collaboration-defaults-v1`, independently of old missing/false/true sharing rows. The resolver never writes sharing, journal, history, group, or account preferences. Journal consent stays a separate data gate.
- Defaults remain behind existing family/cohort and multi-message switches, AI availability, registered/adult/status/deletion eligibility, the existing AI purpose policy, and saved-history availability. Defaults are disabled by default; the new policy epoch defaults to 2. Legacy rollback still reads original enabled rows and versions.
- Both receipt tables and in-memory consultation/step state carry `permission_policy` alongside `permission_version`. Dispatch and publish compare both fields; equal integer versions across different policies do not authorize an old result. Existing specialist projection, source revision, distress/refusal, quota, concurrency, accounting, and budget logic remains in force.
- `GET /ai/sharing` resolves effective state and returns `policyMode` / `policyEpoch`. Defaults-mode `PUT` returns HTTP 410 `SHARING_SETTINGS_RETIRED`, without rewriting hidden preferences. Legacy-mode writes retain their existing semantics.
- Handoff continuation now requires its original completed/used receipt from the same conversation and a live matching policy/version. The narrow admission call in `chat_routes.py` and checks in `runtime.check` plus its publish transaction were updated with parent authorization.
- Migration `0028_collaboration_defaults` follows `0027_maps_jobs`, adding only `permission_policy varchar(32) not null default 'sharing-v1'` to the two receipt tables. It preserves old receipt identity. Downgrade refuses to drop either policy column while non-legacy receipts remain; operational rollback keeps compatibility schema.
- `collaboration/preflight.py` returns only registered-account aggregate old true/false/missing counts by family. It is an inventory, not an eligibility/grant decision, and exports no identities or content.
- `metric=collaboration_token_mismatch family=legacy|v3 edge=...` supports content-free mismatch monitoring. Existing consultation/orchestration/usage metrics remain available.

## Verification

Provisioning used `backend/.venv/Scripts/python.exe scripts/disposable_postgres.py --port 55440`: a newly owned loopback-only PostgreSQL 17.10 / pgvector 0.8.2 container with run ID `51480369ce3341c99a856644e6fc0f6e`. The test runner loaded only that harness's generated environment file into the process without printing credentials. The parent database on port 55439 was not used.

After verification, the provisioner's ownership-checked `--remove 51480369ce3341c99a856644e6fc0f6e` removed that container and its generated local credentials. The temporary runner was also removed. Reruns require a newly provisioned harness.

Test commands used the existing `.venv` Python and pytest directly (no dependency changes), with the harness environment loaded by `.tmp/run_collaboration_tests.py`:

1. Initial new tests: **7 failed**, proving the missing resolver/config/API behavior before implementation.
2. New defaults plus legacy sharing API: **19 passed** in 24.61s.
3. An in-flight continuation test initially published a response after an epoch bump; after the narrow runtime authorization fix, it stopped publishing. A V3 denied-receipt test initially stored `sharing-v1/0`; after fixing receipt stamping it stores `collaboration-defaults-v1/2` without a child request.
4. Prescribed combined regression command:
   `tests/test_collaboration_defaults.py tests/test_sharing_api.py tests/test_collaboration_migration.py tests/test_collaboration_chat.py tests/test_collaboration_proactive.py tests/test_collaboration_privacy.py tests/test_collaboration_review_fixes.py tests/test_orchestration_policy.py tests/test_orchestration_sdk.py tests/test_v3_review_fixes.py tests/test_v3_proactive.py -q --tb=short`
   Result: **157 passed in 265.66s**. This run preceded the additional downgrade guard and aggregate/group tests below.
5. Expanded defaults suite: **56 passed in 106.19s**, including guarded migration upgrade/downgrade, preflight counts, unchanged group journal/history and personal preferences, and off→on→off/epoch token checks.
6. Final regression after the mismatch metric and required continuation conversation ID:
   `tests/test_collaboration_defaults.py tests/test_collaboration_policy.py tests/test_collaboration_dto.py tests/test_orchestration_sse.py -q --tb=short`
   Result: **142 passed in 109.75s**. This includes all 56 defaults tests on final implementation code. The mismatch metric assertion was observed failing before its implementation.
7. Ruff on collaboration, owned orchestration files, the new test module, and migration: **all checks passed**. `git diff --check` on affected backend files: **passed**.
8. `mypy app/ai/collaboration app/ai/orchestration --follow-imports=silent`: **success, no issues in 18 source files**. Its first run caught a `str` versus policy literal mismatch in the new read view; the final change adds the explicit policy literal type without changing runtime values.

Defaults-mode SDK proofs reuse the complete existing assertions with setup changed to omit every sharing PUT: legacy R1/R3/R4, proactive R2, bounded journal projection, journal-context denial, in-message refusal, injection isolation, source-edit rejection, both V3 consults, both specialist handoffs, continuation segmentation, real child usage/receipts, and the Nhật ký→Hoạt động taint guard. Separate matrix tests cover stored missing/false/true values, both families, guest, under-18/unknown/missing age evidence, suspended/inactive/deleting accounts, AI availability, missing AI consent row, history, cohort, and feature switches. Held synthetic child responses test epoch changes, policy rollback with equal version integers, and feature shutdown; none publishes stale bot output or a used receipt.

## Rulings and operational limits

- Preserve the current repository's consent policy: `consent_enabled('AI', false)` is intentionally true for personal purposes. The overlay calls that existing policy and does not redefine a false historical AI row as a new opt-out. Missing consent rows and AI service availability still fail closed. The parent was informed of this source/older-plan difference.
- Authorization failure follows the runtime's existing failure handling (`CONTEXT_CHANGED`, no published output); it does not introduce a new terminal status.
- Preflight counts include all registered accounts, including those currently ineligible or outside a cohort. Runtime eligibility remains a separate live decision.
- Rollout has not been performed. Apply compatibility schema/code first, review aggregate counts/config names, enable existing family flags/cohorts and defaults epoch 2, then inspect call/deny/timeout/usage and token-mismatch metrics before broadening. For emergency rollback, close family switches, drain/cancel in-flight work, disable defaults, and bump epoch on redeploy. Preserve receipt policy columns while defaults receipts remain readable. Do not rewrite old preference rows or broaden journal/group access.
- No application runtime secrets or application `.env` files were read. No live provider, hosted database, AWS, deployment, commit, or push was used. Frontend files, application `.env` files, and `.gitignore` were unchanged by this subtask. Only the generated disposable harness environment was loaded. No live-cost, staging, production, visual/UI, or provider-readiness claim is made. Fresh-context whole-branch review belongs to the parent; this subtask performed its own targeted diff review.
