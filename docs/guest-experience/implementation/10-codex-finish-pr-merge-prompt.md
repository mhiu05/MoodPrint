# Guest Experience Finish, PR and Main Merge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans`, or `superpowers:subagent-driven-development` when available and authorized, to execute the checkboxes below. This document is the complete execution prompt for the next Codex session.

**Goal:** Finish the remaining guest-experience defects, verify the complete branch, obtain an independent review, create or update its GitHub PR, and merge into `main` while keeping release publication and hosted deployment on hold.

**Architecture:** Continue the existing implementation in its existing worktree. Repair the final authorization, document-dispatch, output, accounting, logging and navigation boundaries without replacing the architecture. Add a repository-controlled release hold because merging to this repository's `main` can otherwise trigger automatic publication and an AWS deployment poller.

**Tech Stack:** Existing Python 3.12/FastAPI/SQLAlchemy/PostgreSQL/pgvector/Alembic/Supabase Auth BFF; React 19/TypeScript/Vite; pytest/Vitest/Playwright; GitHub Actions and the existing release poller. Read manifests and lockfiles before choosing commands or versions.

**Spec:** Read [implementation index](00-implementation-index.md), its nine original source documents, plans [01](01-foundation-and-guest-auth.md), [02](02-guest-expiry-and-permissions.md), [03](03-guest-cleanup-and-cost-controls.md), [04](04-public-landing-and-guest-ui.md), [05](05-feedback-and-admin.md), [06](06-interactive-onboarding.md), [07](07-integration-testing-and-release.md), [08](08-interface-and-dependency-matrix.md), and the [independent review](evidence/independent-review-b8c7efb.md). The review's six findings are mandatory work, not an invitation to repeat the original implementation.

## Global Constraints

You are the implementing Codex. Execute this prompt through PR and merge when its gates pass; do not stop after another plan or after merely preparing instructions.

- Source worktree: `E:/MoodPrint-guest-experience`; branch: `feature/guest-experience`; reviewed starting commit: `b8c7efb990447d329599b3bf038430b12aa14084`.
- Original workspace: `E:/MoodPrint`. Repository: `mhiu05/MoodPrint`; expected origin: `https://github.com/mhiu05/MoodPrint.git`; PR base: `main`. Verify these rather than assuming the filesystem or remote has stayed unchanged.
- The owner's current instruction authorizes fixes, focused commits, pushing the feature branch, creating/updating its PR and merging into `main` after the gates below pass. It supersedes older handoff text saying not to push, open a PR or merge, only for those actions. Do not ask for the same authorization again.
- This instruction does **not** authorize hosted migrations, production/staging deployment, manual release dispatch, release-hold removal, public feature enablement, real-provider calls, paid tests, new infrastructure or choosing D01–D04 for the owner.
- Do not modify `.gitignore`. Preserve tracked changes and untracked files. Never reset, clean, force push, disable checks, bypass branch protection, approve your own PR, or stage the entire worktree indiscriminately.
- Known pre-existing untracked paths: `docs/plans/` and `frontend/evidence/` in the feature worktree; `docs/guest-experience/` in the original workspace. Reinspect status; do not assume these are disposable or yours to commit.
- Read `E:/MoodPrint/AGENTS.md`, `E:/MoodPrint/CLAUDE.md`, any applicable worktree/nested instructions, README, ARCHITECTURE, manifests, tests and evidence before edits. Resolve installed skills from their actual locations; do not copy machine configuration or secrets to the worktree.
- Use relevant debugging, TDD, receiving-review, code-review and verification skills. Use a read-only independent reviewer for the final review if supported; only the main implementer edits shared files. Do not invent a reviewer verdict when quota or tooling prevents review.
- Lifetime remains exactly **7200 seconds from the database application grant**, immutable and non-sliding. Deny at `database_time >= guest_expires_at`, independently of feature flags and cleanup.
- Keep age eligibility, explicit AI/MEM/VOICE consent, approved-memory scope, CSRF, ownership, provider-session checks and registered-account behavior intact. No account conversion or guest-data transfer.
- Keep all six rollout defaults/examples false: `GUEST_AUTH_ENABLED`, `GUEST_PAID_ENABLED`, `GUEST_SEMANTIC_ENABLED`, `FEEDBACK_ENABLED`, `FEEDBACK_ADMIN_ENABLED`, `PRODUCT_TOUR_ENABLED`. Never turn off expiration, cleanup or reconciliation.
- Limits remain AI 25/trial, 6/minute, 1 active/guest, 10 active guests globally; voice 6 clips/180 seconds per trial, 2/minute, 1 active/guest, 3 globally. Keep registered/global safeguards too. The daily paid budget remains unset and unapproved.
- Test against explicit disposable loopback PostgreSQL databases ending in `_test`, using synthetic identities/providers only. Do not fall back to `.env` or a remote database when a test target is missing. Do not print connection secrets or raw environment contents.
- Use deterministic barriers/events for race tests; do not use arbitrary sleeps as the oracle. Preserve canonical owner-to-job/resource lock order. Do not hold a database transaction/owner lock over external provider I/O.
- External-send authorization has a defined linearization point. A revocation committed before that decision must prevent dispatch. Work already accepted externally cannot be recalled; describe that boundary accurately.
- Public UX copy stays natural Vietnamese. Engineering documentation and the PR should be English. Do not claim universal physical deletion at T or actual manual/hosted validation from synthetic tests.

## Review Focus

1. Consent withdrawn while an upload or dispatch-marker operation is waiting must prevent the next external voice request; cover guest and registered callers in Task 2.
2. An edited/deleted document, changed source or stolen/expired job lease between admission and dispatch must prevent stale embedding disclosure; unrelated personal changes must not cancel valid work, in Task 3.
3. One WAV sample above a billing quantum must reserve the next whole quantum and round quota usage upward, in Task 4.
4. Guest creation/recovery queued across T and an application clock ahead of the database must not bypass output expiry or shorten a valid trial, in Tasks 5–6.
5. A successful end-and-register confirmation must reach signup in one action without stale private state; failed confirmation must retain an honest recoverable state, in Task 8. A merged commit must also remain unpublished while the release hold exists, in Tasks 1 and 10.

## Starting evidence and limits

At the reviewed commit, prior execution artifacts report 978 backend passes/1 hosted skip, 91 frontend unit passes, 259 owned-browser passes, 31 synthetic fullstack passes, and normal/crash 50-guest workloads with physical isolated restore. These are historical baselines, **not results for your new HEAD**. The previous whole-branch review stopped on quota; the later independent review requests changes for two P1 and four P2 findings.

The original workspace contains the independent review and this prompt; they may not yet exist in the feature worktree. Existing feature evidence includes `evidence/execution.md`, `code-review.md`, `release-readiness.md`, `capacity-recovery.md`, `rollback.md`, `hosted-auth.md` and `tour-compatibility.md` below this implementation directory. Preserve historical entries and distinguish new results by exact commit/date.

## Task 0: Verify the workspace, import the handoff and establish a baseline

**Files:** Read-only inventory of both workspaces; copy only this prompt and `evidence/independent-review-b8c7efb.md` into the matching feature-worktree paths if absent. Update the feature worktree's `evidence/execution.md` for this run.

**Interfaces:** Existing branch and commits are the input. Produce a recorded starting HEAD, current remote-main SHA, owned local test-target inventory and a cleanly scoped delta; do not recreate the feature.

- [ ] Read the instructions/spec/evidence above. Run `git status --short`, `git branch --show-current`, `git rev-parse HEAD`, `git worktree list` and `git remote -v` in the appropriate repositories. Use command-scoped `git -c safe.directory=E:/MoodPrint-guest-experience` only if needed for this inspected user-owned worktree; do not change global trust settings.
- [ ] If HEAD differs from the reviewed commit, inspect and preserve the new commits/changes; check each finding against current code. Do not rewind. If the expected repository/branch is genuinely absent or belongs to different work, investigate before making unrelated edits.
- [ ] Copy the two handoff documents individually, compare SHA-256 source/destination, and never overwrite a differing destination without inspecting it. Do not copy the entire untracked docs tree, `.env`, credential files or browser profiles.
- [ ] Check available GitHub integration/CLI authentication without printing tokens, and read the repository PR template/rules/checks/allowed merge methods. Prefer a connected GitHub tool where sufficient. Fetch `origin/main` and record its current SHA; do not treat the old baseline `984753389aa8bd4b3112b19a8beceb1e538fd659` as current main.
- [ ] Inspect Docker/ports/process ownership. The earlier local DB was `moodprint-guest-impl-db`, loopback port `26432`; verify it before reuse. Allocate distinct owned `_test` databases for unit/API, migrations, fullstack and load. Never drop another session's database or terminate its process.
- [ ] Run a focused baseline: guest budget, expiration, provisioning, in-flight, paid-dispatch and previous review-regression tests; frontend typecheck and existing guest browser cases. Record command, cwd, synthetic target, exit/counts and any pre-existing failure. Missing PostgreSQL coverage is BLOCKED, not a passing skip.
- [ ] Start a finding-to-test matrix with F1–F6, UX1 and REL1, and track checkboxes in this prompt or an execution record. Commit only deliberately imported handoff/evidence files together with the first relevant change.

## Task 1: Prevent merge from implicitly publishing/deploying this release (REL1)

**Files:** Modify `.github/workflows/deploy-staging.yml`, `deploy/aws/README.md` and guest release/rollback evidence. Create `deploy/guest-experience.release-hold`, `deploy/aws/release_hold.py` and `deploy/aws/tests/test_guest_release_hold.py`. Reuse existing deployment-test conventions; no new dependency is needed.

**Why required:** The current `Publish verified staging release` workflow responds to successful `Verify local application` push CI on `main`. It can publish GHCR images and `staging-<sha>` releases. The existing EC2 poller discovers that exact-main release and deploys it. The new backend requires schema `0018_app_feedback`; hosted application of pending SQL is unapproved. Flags off alone do not make an old hosted schema compatible.

**Interfaces:** Introduce `release_held(root: pathlib.Path) -> bool` in `deploy/aws/release_hold.py`. Its fixed marker is `root / "deploy/guest-experience.release-hold"`; absent means no hold, any existing entry or inspection error means hold. A small CLI `main(argv: list[str] | None = None) -> int` accepts `--root`, writes `held=true|false` to the runner's `GITHUB_OUTPUT`, and fails closed if it cannot emit a valid output. A hold is a successful safety decision, not a failed application CI check.

- [ ] Write executable tests first: `test_marker_blocks_release`, `test_absent_marker_preserves_release_path`, `test_nonregular_or_uninspectable_marker_fails_closed`, and `test_cli_writes_runner_output_and_errors_cannot_enable_release`. Use temporary roots/output files and run the real CLI in a subprocess; exercise a dangling link where supported and an injected filesystem error where permission tests are unreliable.
- [ ] RED: run `python -m unittest discover -s deploy/aws/tests -p test_guest_release_hold.py -v` from the worktree root; capture the expected missing-gate failure.
- [ ] Implement the helper and commit the marker with the unresolved schema/decision rationale and explicit owner-only removal procedure. Do not put secrets or a guessed release date in the marker.
- [ ] Add an unconditional release-hold step after `validate` checks out the selected commit and before provenance can emit eligibility. Gate provenance with `steps.release_hold.outputs.held == 'false'`; make the job's `eligible` output explicitly default to `'false'` when skipped. Both automatic `workflow_run` and manual `workflow_dispatch` must honor it. Keep all existing SHA/repository/workflow/actor/approval/attestation checks for the absent-marker path. Every image-publication/release job must remain downstream of eligibility; inspect the complete workflow for alternate paths.
- [ ] GREEN: run the new CLI tests, all `deploy/aws/tests`, and actionlint using the pinned command in `verify.yml`. Verify workflow wiring for both event paths and document how `held=true` leads to no eligible build/publish/release. Use a local workflow harness if available; do not dispatch a live release to test the hold. Have the independent reviewer inspect this wiring and the poller's no-release behavior.
- [ ] Acceptance: normal verification CI remains enabled; held commits produce no published release for the poller; absent-marker behavior retains its security gates. Do not alter AWS timers, GitHub repository settings or branch protections. Do not relax `READY_REVISIONS`, perform a hosted migration, or remove the hold later in this task. Reversal/removal needs a separate owner-approved release change after release prerequisites are fulfilled.
- [ ] Commit this guard and its tests as a focused change, for example `fix(release): hold guest publication until hosted prerequisites are approved`.

## Task 2: Recheck voice consent at external dispatch (F1, P1)

**Files:** Modify `backend/app/modules/voice/routes.py`; inspect/reuse `core/security.py`, guest deadlines, quota/financial helpers and consent mutation paths. Create `backend/tests/test_guest_voice_revocation.py`; reuse actual PostgreSQL and existing streaming/provider-probe fixtures.

**Interfaces:** Preserve `transcribe(request: Request, actor: Actor = Depends(require_actor))` and `TranscriptionPreview`. Reuse `assert_purpose(db, user, "VOICE")`, which includes required AI policy, and existing version/funding/lease checks. Keep public error contracts consistent.

- [ ] Add `test_upload_revocation_blocks_transcription`, parameterized by guest/registered and VOICE/AI. Start the real route with a streaming-body barrier after initial authorization; commit the consent withdrawal through the real consent mutation; then complete upload. Assert `provider.calls == 0`, no transcript, no dispatched paid charge, and no leaked active quota lease.
- [ ] Add `test_revocation_during_dispatch_wait_blocks_transcription`: hold an awaited admission/dispatch-marker boundary, commit revocation, then resume. This must reach the actual final guard, not a mock that denies the whole route. Include a permitted-control request that calls the provider exactly once.
- [ ] RED: `uv run --locked pytest -q tests/test_guest_voice_revocation.py` from `backend` with its explicit local `TEST_DATABASE_URL`; capture the disclosure reproduction before changing code.
- [ ] Reassert current consent, relevant versions, owner/session/lifetime and guest claim/funding after upload and awaited admission/marker work, at the final dispatch decision. Document that decision's lock/commit ordering against consent withdrawal. No awaited queue may make a previously checked authorization stale without another check. Do not simply suppress the returned transcript after sending the audio.
- [ ] Ensure pre-send denial releases unused financial reservations and finishes leases idempotently. Preserve durable usage/replay semantics; do not refund already dispatched or uncertain work, reopen consumed quota, or invent an external charge. Keep the provider call outside database locks.
- [ ] GREEN: run the new tests plus `tests/test_guest_paid_dispatch.py`, relevant registered voice/consent tests and guest quota/budget regressions. Commit, for example `fix(voice): revalidate consent at transcription dispatch`.

## Task 3: Fence document embedding dispatch against invalidation (F2, P1)

**Files:** Modify `backend/app/ai/embeddings.py`; inspect `backend/app/ai/memory.py`, embedding models/source scope and lease logic. Create `backend/tests/test_guest_embedding_dispatch_fence.py`.

**Interfaces:** Preserve the worker `process_embedding_jobs(database, settings, provider=None) -> int` and retrieval API. Extend the internal `_guest_embedding_call(...)` with keyword-only `document_job: tuple[UUID, UUID] | None = None` carrying `(job_id, claimed_lease_token)`. Document calls supply it; query calls retain `None`. A document call without its required fence must fail closed. If a typed internal structure fits existing conventions better, define it once and update both call sites together.

- [ ] Add `test_invalidated_document_never_reaches_provider`, parameterized for API edit, API delete and source invalidation. Pause after worker admission copied the text but before final dispatch; commit the mutation, resume, and assert `provider.calls == 0`, no old/new vector publication from that cancelled job, and no dispatched charge or active lease leak. Test with real DB job/memory rows.
- [ ] Add `test_stolen_or_expired_document_lease_blocks_dispatch`, `test_unrelated_personal_edit_preserves_document_dispatch`, and `test_query_embedding_keeps_separate_funded_scope`. Include a registered document-worker control and the existing no-replay/crash cases.
- [ ] RED: `uv run --locked pytest -q tests/test_guest_embedding_dispatch_fence.py`; capture stale-text disclosure before the fix.
- [ ] At final dispatch, load fresh owner, then job, then applicable resource state in canonical order; verify running status, exact lease token, unexpired lease, memory ID/version/existence/approved status, source scope/model/dimensions and current semantic/AI/MEM consent snapshot. Use current database state, not a detached ORM instance or the previously copied text. Send only the validated document payload.
- [ ] Put this check after admission/heartbeat/marker waits that can invalidate an earlier decision. Retain final publication fencing as well. Do not use the owner's global `data_version` as a substitute for document-specific validity; unrelated profile/mood writes must not invalidate an otherwise current memory. Protect the registered document dispatch path consistently without imposing guest budget policy on it.
- [ ] Preserve separately funded query embeddings, conservative uncertain settlement, cancelled-job non-replay and owner-to-job lock order. A failed pre-send check must release an undispatched ticket exactly once. No network I/O inside the locking transaction.
- [ ] GREEN: run the new tests, existing embedding/memory/consent regressions, `test_guest_paid_dispatch.py`, guest budget and recovery tests. Commit, for example `fix(memory): fence document state immediately before embedding dispatch`.

## Task 4: Round voice billing and quota bounds upward (F3, P2)

**Files:** Modify `backend/app/modules/guests/pricing.py`, `backend/app/modules/voice/routes.py`, and only if necessary `backend/app/modules/voice/service.py`. Extend `backend/tests/test_guest_budget.py` and appropriate real-route voice quota tests.

**Interfaces:** Preserve `voice_upper(pricing: dict[str, Any], seconds: float) -> tuple[str, int] | None`, `validate_audio(data: bytes) -> float`, and the response duration contract unless a documented internal exact-duration helper is needed. Do not add a provider SDK or change pricing policy.

- [ ] Add `test_voice_bound_keeps_fractional_sample_above_quantum`. With existing synthetic pricing version `synthetic-v1`, rate 7 nano-USD/second and quantum 15 seconds, the required assertions include:

  ```python
  assert voice_upper(PRICING, 15.0) == ("synthetic-v1", 105)
  assert voice_upper(PRICING, 120001 / 8000) == ("synthetic-v1", 210)
  assert voice_upper(PRICING, 30.0) == ("synthetic-v1", 210)
  ```

- [ ] Generate valid mono 16-bit WAV inputs one sample below, exactly at and one sample above 15 seconds for supported rates. Include the 8000 Hz/120001-frame case, exact 30-second limit and invalid >30-second audio. Assert quota milliseconds use an upward bound: that fractional 15-second input accounts for 15001 ms, not 15000 ms. Verify 6 clips/180000 ms limits and replay behavior remain enforced.
- [ ] RED: run `uv run --locked pytest -q tests/test_guest_budget.py -k 'voice or upper_bounds'` and the named route quota regressions.
- [ ] Remove fractional-millisecond truncation before quantum rounding. Use exact frame/rate arithmetic where appropriate, or a conservative ceiling of the original duration; justify numerical boundaries. Round quota duration upward too. Keep invalid/missing prices fail-closed and settlement no lower than the validated reservation policy.
- [ ] GREEN: run the full budget suite and voice validation/quota/paid-dispatch suites. Commit, for example `fix(voice): reserve fractional sample duration conservatively`.

## Task 5: Install final output deadlines on guest grant/recovery responses (F4, P2)

**Files:** Modify `backend/app/modules/guests/service.py`; inspect guest routes, cookie issuance, `core/security.py`, `guests/deadlines.py` and `guests/output.py`. Extend `backend/tests/test_guest_inflight.py` and provisioning tests.

**Interfaces:** Preserve public `POST /api/v1/auth/guest`, `create_guest(request, body, response) -> SessionView`, grant/recovery semantics and `GuestDeadline`. Set `request.state.guest_output` using `guest_deadline(db, user)` for every response returning a live guest session/cookies, including current-cookie, new-grant and recovery branches. Reuse one internal helper only if that removes actual duplication.

- [ ] Add `test_guest_auth_response_queued_past_deadline_is_withheld`, parameterized for existing guest, credential recovery and new grant. Use the actual ASGI middleware ordering with a barrier after serialization and before outer send; cross immutable T deterministically, then release the response.
- [ ] Assert no private SessionView fields or live credential `Set-Cookie` are delivered after the boundary. Expect `GUEST_EXPIRED` before headers start, or the existing content-free closure contract if already started; deletion cookies are allowed. A pre-T control returns one valid session with the original deadline.
- [ ] RED: `uv run --locked pytest -q tests/test_guest_inflight.py -k guest_auth_response_queued`.
- [ ] Install the conservative DB-sampled deadline before session/cookie output can escape each guest branch. Do not add an authenticated/CSRF dependency to public guest creation, extend a recovered deadline, expose provider credentials, or substitute browser/application wall time.
- [ ] GREEN: rerun the new test, full in-flight and provisioning suites. Preserve registered-cookie rejection (409), idempotent lost-response recovery, and successful end's empty 204/cookie clearing. Commit, for example `fix(auth): guard guest provisioning output at the immutable deadline`.

## Task 6: Use the database clock for guest session expiry (F5, P2)

**Files:** Modify `backend/app/core/security.py`; reuse guest policy's database clock helper. Extend `backend/tests/test_guest_expiration.py`.

**Interfaces:** Preserve `verify_session(db: AsyncSession, session: AuthSession, user: User) -> None` and registered sliding renewal. For a guest, both lifecycle and application-session expiry judgments use fresh DB time; provider-session revocation and explicit trial end remain authoritative.

- [ ] Add `test_guest_session_ignores_ahead_application_wall_clock`: DB time T−1 ms, process wall time T+1 hour, unrevoked provider session. Assert the guest remains authorized and no renewal/write moves T.
- [ ] Add `test_guest_session_denied_at_database_deadline`, plus legitimate pre-T session-expiry/revocation/end cases. Assert DB time exactly T denies. Cover timezone-aware comparisons and retain a registered sliding-session regression.
- [ ] RED: `uv run --locked pytest -q tests/test_guest_expiration.py -k 'application_wall_clock or database_deadline'`.
- [ ] Remove the app-wall-clock expiry decision for guests while preserving registered behavior and all other identity checks. Keep test clock injection inside test harnesses; introduce no production expiry bypass or clock-override endpoint.
- [ ] GREEN: run expiration, auth-session, provider and guest output regressions. Commit, for example `fix(auth): keep guest session expiry on database time`.

## Task 7: Remove guest identifiers from operational AI logs (F6, P2)

**Files:** Modify `backend/app/ai/runtime.py`; inspect `backend/app/ai/embeddings.py`, logging setup and associated guest error/cancel paths. Create `backend/tests/test_guest_log_privacy.py`.

**Interfaces:** Keep existing logging configuration and registered observability. Guest logs retain content-free aggregate status/timing/token/request-count information; they contain no guest user/provider/session/run/conversation IDs or raw input/output/audio.

- [ ] Add `test_guest_run_logs_exclude_activity_identifiers`, parameterized for success, failure, cancellation and expiry. Capture actual log emissions with `caplog`, using distinct fixture IDs and sentinel private text. Assert all forbidden fixture values are absent while expected safe event/status metrics remain present.
- [ ] Add `test_registered_run_logging_preserves_observability`. Inspect both rendered messages and structured log arguments/extra fields so moving an ID out of the message does not pass falsely.
- [ ] RED: `uv run --locked pytest -q tests/test_guest_log_privacy.py`; reproduce the unconditional `run.id` logs around runtime terminal/failure handling.
- [ ] Make guest-aware emissions at the sources, or use a rigorously scoped equivalent. Audit start/progress/failure/finalize/cancel and embedding paths. Do not silence all logs, redact registered identifiers indiscriminately, or log exception content that may include private payloads.
- [ ] GREEN: run the new tests and AI runtime/error/cancellation/cleanup regressions. Keep D01 historical log-retention disclosure unresolved; a forward logging fix does not erase old logs. Commit, for example `fix(privacy): omit guest activity identifiers from AI logs`.

## Task 8: Complete end-and-register navigation in one confirmation (UX1)

**Files:** Modify `frontend/src/features/real/RealApp.tsx` and only the related lifecycle/auth UI if necessary. Extend `frontend/tests/e2e/guest.spec.ts` and `frontend/tests/fullstack/guest-journey.spec.ts` using their existing fixtures.

**Interfaces:** Preserve `POST /auth/guest/end` success as 204, the lifecycle broadcast/abort behavior and hash signup route `#/login?mode=signup`. Give successful end-and-register an explicit transition that clears the terminal guest screen and opens signup after private state is discarded; keep ordinary end/expiry terminal screens.

- [ ] Add browser case `end and register opens signup after one confirmation`: choose the CTA, confirm once, assert signup fields are directly visible without clicking the ended screen again. Confirm the end request succeeded before signup transition.
- [ ] Add cancellation and 503/network-ambiguous end cases: cancelling keeps the current guest view; a failed/unconfirmed end does not show a false successful end or silently enter signup. Preserve actionable error/retry UI and avoid duplicate end requests. Assert late private responses cannot repopulate the new screen and registered logout still works.
- [ ] RED: `npm.cmd exec -- playwright test --config playwright.owned.config.ts tests/e2e/guest.spec.ts -g 'end and register'` from `frontend`. Ensure the filter selects your named case and fails on the extra-click behavior.
- [ ] Implement the smallest explicit transition. The current `ended && session === null` branch takes precedence over the signup hash; changing only the hash does not fix it. Clear/choose terminal state deliberately after successful end; retain private-tree unmount, API reset, cross-tab invalidation and no guest-data transfer.
- [ ] GREEN: run typecheck, frontend unit tests, owned guest/expiry browser cases and actual HTTP/PostgreSQL fullstack guest journey. Inspect 390 px and 1280 px, keyboard focus and confirm/error states; use existing browser tooling and synthetic accounts. Do not claim real microphone, assistive-device or hosted CAPTCHA validation from fixtures.
- [ ] Commit, for example `fix(guest): open signup directly after confirmed trial end`.

## Task 9: Verify the integrated branch and obtain a complete independent review

**Files:** Update existing evidence plus create `docs/guest-experience/implementation/evidence/final-review-and-merge.md`. Update relevant technical docs/contracts only where behavior actually changed. Preserve the original nine audit documents, historical SQL approvals and historical review findings as records.

**Interfaces:** Produce a reproducible latest-HEAD verification matrix and a reviewer verdict tied to an exact SHA. Source integration can pass while public release remains HOLD. D01–D04 and truly manual/hosted checks are not fabricated merge prerequisites once publication is safely held; all required local/security/CI/review gates still apply.

- [ ] Fetch and integrate current `origin/main` into the feature branch without rewriting published history. Resolve conflicts narrowly, preserve user work and rerun affected checks. Inspect the complete PR diff against the refreshed base; do not review only the last fixes or drop existing feature commits.
- [ ] Run backend checks from `backend` against explicit disposable PostgreSQL: `uv sync --locked`, the complete Ruff command from current `.github/workflows/verify.yml` (including its scripts), `uv run --locked mypy app`, and `uv run --locked pytest -q -rs`. Run the complete suite, not only new cases. Only the explicit unapproved D04 hosted-target skip may remain; investigate additional skips/failures rather than calling them PASS.
- [ ] In a distinct disposable migration DB run `uv run --locked alembic upgrade head` and `uv run --locked alembic check` with only the local migration target set. Verify schema head/readiness and existing reviewed-artifact integrity. Do not modify historical approval hashes or apply pending hosted SQL. Avoid a new migration unless a demonstrated schema defect requires one; if it does, update readiness, SQL-review and rollback artifacts coherently without pretending hosted approval.
- [ ] Regenerate OpenAPI with `uv run --locked python ../scripts/export_openapi.py`; run frontend `npm.cmd ci`, `npm.cmd audit --audit-level=low`, `npm.cmd run contracts:generate`, `npm.cmd run typecheck`, `npm.cmd test` and `npm.cmd run build`. Review and commit intentional generated contract changes; verify no drift remains afterward. Do not regenerate lockfiles or update unrelated packages casually to silence failures.
- [ ] Run full owned-browser coverage with `npm.cmd exec -- playwright test --config playwright.owned.config.ts`, the default CI browser command where it differs, and `uv run --locked python ../scripts/test_fullstack.py` from `backend`. Use the harness-owned DB/ports and SDK fake model; do not substitute mocked HTTP for fullstack coverage. Baseline counts 91/259/31 are references, not fixed expected counts after adding tests.
- [ ] Execute all 25 negative scenarios in plan 07 with current test selectors and meaningful selected-test counts. Record F1–F6, UX1 and REL1 as separate rows with reproduction, fix commit, regression names and actual results. Include registered, flags-off, final-output, consent, purge and detached-liability regressions.
- [ ] Because dispatch/funding/leases changed, rerun one-worker **50-user** registered baseline, guest normal, and guest crash/restart/physical-quarantine-restore workloads sequentially, without competing heavy suites. Reuse `scripts/load_chat_memory.py` and `scripts/load_guest_experience.py` and the documented owned target/port checks; guest CLI requires `--workers 1 --users 50`. From `backend`, after setting the verified local load target, use `uv run --locked python ../scripts/load_chat_memory.py --workers 1 --users 50 --port 8017 --output <owned-temp>/registered-final.json`, then `uv run --locked python ../scripts/load_guest_experience.py --workers 1 --users 50 --port 8018 --output <owned-temp>/guest-final.json`, then the latter with `--crash-kill` and a distinct output. Confirm these ports are free first; inspect CLI help and the existing capacity record before running. Normal and crash outputs must prove caps, no unexpected 5xx/owner leak, registered canary, zero replay, retained detached liability and no expired identities exposed after restore. Keep raw dumps/JSON/logs in owned temp locations; commit only sanitized summaries/repeatable scripts. Do not change workload/caps/assertions to get a pass.
- [ ] Run `python scripts/check_reviewed_artifacts.py`, `python scripts/check_docs.py`, `python -m unittest discover -s deploy/aws/tests -v`, pinned actionlint, and the packaging/proxy/image commands from current `verify.yml`. Ensure Linux/Node 22 build coverage through local containers or actual PR CI. Local blocked Linux checks may be satisfied by observed green exact-head CI; they cannot remain unverified at merge.
- [ ] Check `.gitignore` has no branch diff; confirm six defaults/examples remain false, daily paid budget remains unset, release marker is tracked, and no secret/generated dump/browser profile/raw personal output is staged. Inspect `git diff --check` and intentional Markdown hard-break whitespace separately; fix actual accidental whitespace without weakening checks.
- [ ] Obtain a new read-only independent review covering the complete branch and specifically the dispatch races, final output/cookies, exact rounding, DB time, identifier-free logs, one-click transition and both workflow event paths. Give the reviewer the spec, full base/head SHAs, current diff and test evidence. Record all findings, fix actionable defects, and rerun affected checks/review on the changed SHA. No unresolved P0/P1, none of the six required findings, and no unapproved material regression may remain. Quota exhaustion is an incomplete review, never APPROVED; continue safe work and keep merge blocked if a complete verdict cannot be obtained.
- [ ] Update `execution.md`, `code-review.md`, `release-readiness.md`, `capacity-recovery.md`, `rollback.md` and the new final report consistently. Record exact code SHA(s), tool versions/commands/exit/counts, raw artifact locations, skips, manual gaps and reviewer scope. Keep historical results labeled historical. If only evidence changes after a reviewed code SHA, record both SHAs and verify that delta explicitly.
- [ ] D01 deletion/provider/log/backup facts and cleanup target, D02 approved numerical paid budget, D03 proposed 180-day unlinked-feedback retention, and D04 approved hosted Auth/CAPTCHA/DB target remain unresolved. Driver spotlight remains explicitly deferred with inline guidance as the accepted fallback. Do not add another tour library or claim these external decisions have been settled.
- [ ] Acceptance: **merge readiness PASS** only with fresh required local/CI evidence and a completed independent review; **release HOLD/PARTIAL** because hosted/owner/manual prerequisites and the tracked publication hold remain. If anything essential is unavailable, finish unaffected work and the concrete PR, then report the precise merge blocker instead of bypassing it.

## Task 10: Push, open the PR, wait for checks, merge and verify remote main

**Files:** The fully reviewed feature branch and an English PR description following any repository template. Keep `evidence/final-review-and-merge.md` reviewable before merge. PR URL/merge SHA can be reported in the final response; do not create a post-merge evidence commit that invalidates the tested merge merely to insert them into Markdown.

**Interfaces:** PR base `main`, head `feature/guest-experience`; merge the exact reviewed feature SHA using a repository-allowed method. The repository's normal review/check protections remain authoritative. No admin bypass, force push, branch deletion or live deployment action.

- [ ] Make focused commits and stage named paths only. Run `git status --short`, inspect the staged diff, then `git push -u origin feature/guest-experience`. Authenticate through already available tooling; do not expose tokens. If permissions are unavailable, report the exact failed action after completing all possible local work.
- [ ] Find an existing PR for this head/base before creating one. With `gh`, inspect `gh pr list --repo mhiu05/MoodPrint --head feature/guest-experience --base main --state open`; use the equivalent connected GitHub tool if available. Update the existing PR or create one, avoiding duplicates.
- [ ] Write the complete English PR body to a UTF-8 file and pass `--body-file` if using `gh pr create/edit`. Suggested title: `Finish guest experience with dispatch privacy fixes and release hold`. Describe the whole guest/landing/feedback/admin/inline-guidance feature, the six findings and UX fix, actual validation, compatible schema/rollback requirements, the publication hold, D01–D04/manual gaps, and the fact that no hosted migration/deployment/paid enablement is included. Do not describe only the final seven fixes.
- [ ] Wait for required GitHub checks on the latest PR head; inspect failures and fix genuine regressions. Validate the actual Linux full verification job, workflow syntax, packaging/proxy tests, release hold tests, and required reviewer decisions. A queued or pending run is not a pass. Do not treat historical b8c7efb artifacts as exact-head CI evidence or disable failing jobs/security checks. The existing verification job has a 25-minute overall limit: if observed logs prove the complete valid workload exceeds it, measure the stages and make a focused, justified adjustment to that job's bounded runtime budget. Do not remove tests, relax assertions, extend product deadlines or alter load/test timing oracles to mask failures; re-run exact-head CI after any workflow change.
- [ ] Recheck PR head SHA, base, mergeability, required reviews, unresolved threads and `origin/main` immediately before merge. If the base changed materially, update without force, resolve conflicts and rerun affected local/CI/review checks. Never accidentally merge a new unreviewed head.
- [ ] Merge when all gates pass without another routine confirmation. With `gh`, use a repository-allowed method plus `--match-head-commit <full-reviewed-head-sha>`; inspect `gh pr merge --help` if necessary. Prefer `--merge` when allowed; otherwise follow the repository's allowed method and record the resulting SHA. Do not use `--admin`, `--delete-branch` or unattended auto-merge to claim an unobserved result. If repository-required human approval is missing, leave the concrete PR ready and explain that specific blocker.
- [ ] Verify actual PR state `MERGED`, PR URL, `mergedAt`, merge commit SHA, and fetch/read remote `main`. Confirm the merge SHA is reachable from `origin/main` with `git merge-base --is-ancestor <merge-sha> origin/main`; record current remote-main SHA even if a later legitimate commit exists. Do not merely assume a successful merge request means it merged.
- [ ] Observe post-merge `Verify local application` on the merged main SHA. Verify `Publish verified staging release` honors the marker and its build/publish/release jobs do not publish a `staging-<merged-sha>` release. Distinguish an expected absent release from an API permission error. Use GitHub read-only run/log/release inspection; do not probe or modify AWS. Do not report no deployment based solely on flags being false.
- [ ] Keep the branch/worktree and all pre-existing untracked files. Do not run `git pull`, force checkout or overwrite files in `E:/MoodPrint`: its untracked docs can overlap files newly tracked by the merge. Remote-main integration is the required outcome; report that original-workspace synchronization was left untouched if unsafe. Never delete those files to make checkout succeed.
- [ ] If post-merge verification fails, report the exact failing SHA/run/check and remediate through a focused follow-up PR under the same no-deployment/hold boundaries. Never reset or force-push main or silently remove the release hold. Continue until required checks pass, or name the concrete external blocker and actual partial state.

## Required final response

Lead with the actual outcome: merged PR and exact main/merge SHAs, or a ready PR and the specific blocker. Provide a compact table with scope, changes, commands actually executed and observed outcomes, coverage and unresolved risk, using **PASS | PARTIAL | FAIL**. Include:

- F1–F6, UX1 and REL1 closure with regression evidence and independent reviewer verdict/SHA.
- Backend/unit/browser/fullstack/load/recovery/migration/docs/contracts/workflow/build counts and skips; distinguish local, CI, historical and unrun checks.
- PR URL, reviewed feature SHA, actual merged SHA, observed remote-main SHA, and post-merge verification run links/status. Do not invent a successful merge or a completed queued check.
- All six flags still off, budget unset, tracked release hold retained, no hosted mutation or live-provider testing executed, D01–D04/manual/spotlight limitations intact.
- Local original-workspace status and preserved untracked files. Mention `.gitignore` unchanged.

Complete the authorized work autonomously. Do not end with “I can make the PR next” when the gates and permissions already allow doing it. If a real gate blocks merge, leave the best concrete, reviewable PR possible and explain exactly what remains.
