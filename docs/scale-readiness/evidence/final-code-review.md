# Candidate code review — 2026-11-05

Fresh-context reviewer: candidate_review. The initial reviewer could not start due to
its usage limit; the replacement completed the review. No Critical findings; three
Important findings were accepted and fixed. This review does not certify cloud capacity.

1. Direct WebSearch Responses calls bypassed the candidate physical dispatch gate.
   The candidate now rejects that unsupported path before admission/provider dispatch.
   The default path is unchanged. Public search is unavailable while the candidate gate
   is enabled until its paid-operation authority is integrated.
2. Authorization before a queue wait could become stale. SDK hooks now bind the exact
   filtered input object to a one-use authority fence, executed after acquiring a slot.
   Journal/consent/worker checks and the request-start accounting marker remain together.
   Revocation while queued results in no model call, with the permit released.
3. Account deletion with the budget disabled could delete legacy relevant liability.
   Relevant financial rows now survive deletion regardless of the current budget setting.
   Unknown liability fails closed after re-enabling accounting.

Evidence: [five failing tests before fixes](review-red.log),
[39 passing tests after fixes](review-green.log),
[candidate gate regressions: 96 PASS, 2 SKIP](candidate-gate-regression.log).
Tests overlap; their counts must not be added as distinct coverage.

Ruling: unsupported public-search dispatch fails closed under the candidate flag.
This preserves financial/authorization guarantees at the cost of that feature's
availability in the candidate. It requires explicit UX review before activation.

Declined to judge: hosted quotas, actual pricing, full mixed capacity, and production
readiness. Ruling: these remain release blockers; unit tests and this review do not
replace account-specific evidence, target-size load, or owner approval.

Subsequent local changes: transaction-local actor/session/age prefetch (poll 6 to 4
queries) and narrower resend/recovery error classification. Their own RED/GREEN and
regression evidence are recorded in the implementation ledger and test report.

Further regression found eight failures in nested Agent.as_tool specialists with the
candidate physical gate enabled. Those nested SDK runners need their own post-queue
hook wrapper; adding it fixed the regression. An explicit false/true parameter case
failed first, then the SDK/orchestration/fence subset passed39 tests. The final current
candidate matrix passed242 tests in449.37s, including Auth/reset/provisioning, SDK,
orchestration, groups, privacy, accounting and safety. No second independent review is
claimed. The failed admission-before-checkout experiment was removed after load results
37/50 and33/50; its evidence is retained, and it is not part of this candidate.
