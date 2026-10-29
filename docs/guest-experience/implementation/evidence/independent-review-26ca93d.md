# Independent whole-branch review — 26ca93d

Date:2026-10-28, Asia/Bangkok. Read-only fresh reviewer
`/root/finish_independent_review` (gpt-6-astra/high), base
`984753389aa8bd4b3112b19a8beceb1e538fd659`, head
`26ca93d141b38f8c963a8c2ec0279280eb830594`.

**Complete verdict: CHANGES REQUESTED.** No P0/P1 identified; three actionable
P2 findings at this SHA. Earlier quota failure produced no verdict; this report
comes from the successful resumed complete review. Author fixes require later-SHA
review, and execution/CI gates remain separate.

| Priority | Finding at reviewed SHA | Effect / required regression |
| --- | --- | --- |
| P2 R1 | `backend/app/modules/guests/limits.py:195`: rejection refunds the current window | Old pending signup crosses hour/day boundary, new signup succeeds, old rejection decrements the new count. Preserve exact original DB sample and refund only after successful attempt transition. |
| P2 R2 | `backend/app/modules/guests/jobs.py:270`: retention deletes reservations referenced by operation links | FK RESTRICT fails after cleanup outage/incident retention >24h, rolling back unrelated expired abuse counters. Exclude linked reservations and preserve replay fence. |
| P2 R3 | `backend/app/main.py:147`: startup missing-job repair is abandoned after one failure | Transient repair failure sets first=false, so expired guests without jobs never purge until restart. Retry until repair succeeds; test two worker ticks without restart. |

Nonblocking hardening concern: `runtime.py:441` marks the reservation once and
rechecks general policy on later model requests; operation-token/state/lease
checks occur in the five-second heartbeat. Forced claim replacement or premature
reservation finalization could precede heartbeat detection. Reviewer found no
normal token-stealing path; normal lease expiry is bounded by cancellation, so
synthetic token tampering alone was not graded as a confirmed production defect.
A later-model-request fencing test remains a possible hardening improvement.

Minor: EOF blank lines in test_foundation.py, AWS README and three evidence docs;
the two prompt09 trailing-space lines are intentional Markdown hard breaks.

## Scope and observed reviewer checks

All237 branch files reviewed in functional passes: production changes, surrounding
authorization/lifecycle, migrations/contracts, frontend flows, tests/fixtures/
harnesses, workflows and operations. Detailed inspection covered critical races,
requester/peer denial, foreign social evidence, owner purge, orphan recovery,
detached settlement/no replay, feedback unlink/admin filters, public/callback
routing, lifecycle invalidation, export, guide and registered paths.

F1–F6 and UX1: no additional actionable defect identified in the repairs. Both
release events honor the tracked hold, all publication jobs require eligibility,
and the poller returns when the exact-main release is absent. Six defaults/examples
false, budget unset, readiness0018 and guest-aware rollback preserved.

Reviewer actually executed (bytecode disabled): release-hold unittest4 PASS;
docs61 files/420 links/109 operations/68 settings/48 tables PASS; historical SQL
pins9/consumed9 PASS; branch diff whitespace FAIL on items above. No DB/browser/
load/hosted/paid commands or source edits. Author test results are separate evidence.

## Behaviors deliberately not certified

- Hosted Auth/CAPTCHA, actual provider child cascade and hosted permissions: no D04 target.
- Production capacity, paid provider, approved prices/budget/disclosure/retention: no live approval; D01–D04 unresolved.
- Screen-reader, real mic and device soft-keyboard behavior: no device/manual examination.
- Driver spotlight: deferred; inline fallback ships.
- Actual post-merge publication suppression/deployment state: source reviewed, merged-SHA observation pending.
- Final integrated execution/CI: author-owned gates pending completion.

No other production behavior deliberately excluded from source review. Source
integration blocked until R1–R3 fixes are reviewed; public release remains HOLD.
