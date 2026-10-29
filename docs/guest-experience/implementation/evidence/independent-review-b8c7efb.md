# Independent review of guest experience at b8c7efb

Date: 2026-10-28, Asia/Bangkok. Reviewed worktree: `E:/MoodPrint-guest-experience`, branch `feature/guest-experience`, exact HEAD `b8c7efb990447d329599b3bf038430b12aa14084`, against baseline `984753389aa8bd4b3112b19a8beceb1e538fd659`.

**Verdict: CHANGES REQUESTED. Release remains PARTIAL / HOLD.** The substantial local implementation and recorded test evidence are useful, but two remaining external-disclosure races need regression fixes before a clean local acceptance claim. This review authorizes no merge, deployment, feature enablement, hosted action or policy decision. No application source was edited during review.

Two independent read-only reviewers covered auth/AI/deadlines and cleanup/financial controls. The primary reviewer corroborated their findings against current source, examined feedback/public/guest UI and release evidence, and reran the checks listed below. This is a focused review, not certification of every line or hosted behavior.

## Findings

### P1 — Consent withdrawal during voice upload does not prevent external transcription

Location: `backend/app/modules/voice/routes.py:105-114`; initial consent check at lines 45-46; later result checks at lines 125-138.

The route reads VOICE/AI consent and data_version before awaiting the request body. After upload completes, its admission transaction reserves quota/budget but does not reassert consent or compare that original data_version. `guard_guest_dispatch` checks account status and lifetime only; the dispatch marker and quota heartbeat do not check VOICE/AI. A concurrent consent withdrawal can therefore complete while the upload is paused, yet the full audio is subsequently sent to the transcriber. Rejecting the transcript afterward cannot undo disclosure.

Required regression: pause the upload, withdraw VOICE (parameterize AI withdrawal as well), finish the upload, and assert zero transcriber calls and no paid dispatched charge. Revalidate the current relevant consent and version after body/admission waits, immediately before external dispatch, while preserving owner/lease/deadline gates. Registered and guest behavior both deserve coverage.

### P1 — A cancelled memory embedding job can still send old/deleted text

Location: `backend/app/ai/embeddings.py:276-289`; document snapshot taken at lines 399-423; invalidation at lines 163-172.

The worker validates and copies memory.text before committing admission. Its final guest adapter checks only preference/AI/MEM consent versions, plus lifetime. It does not revalidate the document job status/token/lease or the memory's current existence/status/version/source. Editing/deleting memory after admission cancels the job, but the adapter can still send the cached old text to the provider. Final publication fencing prevents a vector from being stored; it does not prevent the external request.

Required regression: barrier after worker admission and before the document adapter's final check; delete or edit the memory through the API; release the barrier; assert zero embedding provider calls. Recheck the document job and current memory/source under canonical owner/job order immediately before dispatch. Do not invalidate unrelated memories merely because another personal record changed.

### P2 — Voice financial upper bound truncates a valid fractional millisecond

Location: `backend/app/modules/guests/pricing.py:75`; settlement uses that same bound at `backend/app/modules/voice/routes.py:167`.

`int(seconds * 1000)` floors the validated duration before rounding to a billing quantum. Executed reproduction used valid mono 16-bit WAV, 8000 Hz, 120001 frames: duration **15.000125 seconds**. With the existing synthetic 15-second quantum and rate 7, `voice_upper` returns **105 nano-USD**, while the required two-quanta bound is **210 nano-USD**. The route settles known results at the underestimated reservation, so this discrepancy does not trigger its actual-overrun detection.

Required regression: one-sample-above-quantum WAV boundaries, including the 15.000125-second case. Round the original duration upward using exact frame/rate or decimal/rational arithmetic. Verify 15 seconds stays one quantum, any positive sample beyond it becomes two, and no artificial rounding loss affects quota accounting.

### P2 — Guest creation/recovery responses lack the final output deadline context

Location: `backend/app/modules/guests/service.py:128-138` and `:374-379`; `backend/app/modules/guests/routes.py:27-30`; bypass in `backend/app/modules/guests/output.py:33-36`.

The public guest POST returns existing-guest/recovered SessionView through direct session validation rather than require_actor. Neither path installs request.state.guest_output. Consequently, an inner middleware/response queue that holds the completed response across T bypasses GuestOutputMiddleware and can deliver session fields/rotated Set-Cookie without a final dispatch check. The expired cookies cannot authorize later access, but the required at-T output cutoff is absent on this path.

Required regression: hold POST /auth/guest existing-guest and recovery responses after serialization but before final dispatch, cross T, and assert no private SessionView or live credential cookie is sent. Install the appropriate deadline context for all guest grant/recovery responses; preserve registered-cookie rejection and empty end responses.

### P2 — Application clock can prematurely reject a database-valid guest

Location: `backend/app/core/security.py:33-43`.

After the database-backed guest predicate succeeds, verify_session still compares AuthSession.expires_at against application now(). An ahead process wall clock can reject an otherwise live trial before database T. Guest deadline authority should remain database-owned; existing registered sliding behavior should be preserved.

Required regression: database time before T, application time after T, provider session live: guest is still accepted; database time at T is denied. Keep legitimate provider revocation and explicit trial-end denial.

### P2 — Guest run identifiers are still written to operational logs

Location: `backend/app/ai/runtime.py:657` and `:674`; logging setup in `backend/app/core/logs.py` has no guest redaction filter.

Failure and terminal logs unconditionally include run.id for guest runs, contrary to plan03's explicit identifier-free guest logging requirement. Database/RAM purge does not remove retained stdout/container/CloudWatch records. This is not a transcript or token leak, but it leaves a guest activity identifier outside the claimed active-store cleanup boundary.

Required regression: caplog for guest success/failure/cancellation verifies no guest user/provider/session/run/conversation identifiers, while aggregate latency/token/status metrics remain. Preserve registered observability separately. D01 log-retention disclosure remains an external hold.

## Evidence and checks

| Check actually executed in this review                                                                                                                                                                                                                                  | Result / limitation                                                                                                                                                                 |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Git HEAD/branch/status                                                                                                                                                                                                                                                  | Exact b8c7efb confirmed; no tracked modifications; existing untracked `docs/plans/` and `frontend/evidence/` preserved                                                              |
| `python scripts/check_docs.py` in reviewed worktree                                                                                                                                                                                                                     | PASS: 59 Markdown files, 410 links, 109 API operations, 68 settings, 48 tables                                                                                                      |
| `python scripts/check_reviewed_artifacts.py`                                                                                                                                                                                                                            | PASS: 9 historical approvals unchanged                                                                                                                                              |
| `.venv/Scripts/ruff.exe check --no-cache app tests evals alembic` from backend                                                                                                                                                                                          | PASS                                                                                                                                                                                |
| `node node_modules/typescript/bin/tsc --noEmit` from frontend                                                                                                                                                                                                           | PASS, exit0                                                                                                                                                                         |
| `.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider --basetemp <owned-temp> tests/test_guest_provider.py tests/test_guest_expiration.py::test_deadline_boundary tests/test_guest_expiration.py::test_registered_and_guest_gates tests/test_public_headers.py` | PASS: 39 tests in 7.65s; synthetic/pure/header cases, not the complete PostgreSQL suite                                                                                             |
| Executed WAV/voice_upper reproduction                                                                                                                                                                                                                                   | Under-reservation reproduced: 105 versus required210 synthetic nano-USD; no paid/provider call                                                                                      |
| Archived final outputs read directly                                                                                                                                                                                                                                    | Backend978 passed/1 skipped; owned browser259 passed; fullstack31 passed; final normal/crash50 JSON both statusPASS. These are prior-run artifacts, not suites rerun by this review |
| Original audit hashes and .gitignore comparison                                                                                                                                                                                                                         | All9 audits identical to original main-workspace files; .gitignore unchanged                                                                                                        |
| `git diff --check 9847533..HEAD`                                                                                                                                                                                                                                        | Minor formatting findings: test_foundation.py trailing blank line; intentional Markdown hard-break whitespace in the Sonnet prompt. No functional implication                       |

Mypy completed with a fresh owned temporary cache: `.venv/Scripts/mypy.exe --cache-dir <owned-temp> app` returned **Success: no issues found in114 source files**, exit0. The initial frontend tsc invocation from backend used the wrong relative path and was not a pass; the correct frontend invocation above exited0.

## Remaining release holds

D01 deletion/provider/log/backup disclosure and cleanup target; D02 approved numerical paid budget; D03 proposed180-day unlinked feedback retention; D04 approved hosted Auth/CAPTCHA/DB test target remain unresolved. Manual assistive-device/text-zoom/microphone/CAPTCHA review and full GitHub Actions/target validation remain open. Driver spotlight is explicitly deferred; inline guidance is the implemented fallback. The known extra signup click after ending a trial is a separate minor navigation issue.

Recommended next step: fix the two P1 disclosure races first with deterministic negative tests, then the P2 deadline/accounting/logging issues; rerun affected PostgreSQL/AI/voice/embedding and browser regressions plus final static checks. Obtain an independent review of those fixes before changing a local acceptance verdict. Keep all public/paid flags off and preserve the feature branch/worktree.
