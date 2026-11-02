# MVP demo safety implementation plan

Owner's 2026-11-02 follow-up authorizes V3 for authenticated adults, an AI budget
of at most $20/day, explicit revocable journal consent, and proactive opt-in
messages only after worker/schedule/idempotency hosted verification. Guest access
must preserve private-journal boundaries. Keep a quick worker kill switch.

## Constraints

- Keep branch test/11-2, current migrations/head0024 and `.gitignore` unchanged.
- Preserve exact-main verified releases, workflow identity, immutable digests,
  attestations and complete CI. No CI refactor, skipped tests or retry inflation.
- QA first, then expand registered-adult cohorts. Worker stays disabled until all
  required checks pass. Missing guest prerequisites must fail closed.
- Use existing usage ledger if financial reservation is needed; no new database
  schema or migration infrastructure.

## Tasks and ownership

1. Root: expose sharing settings for smartOrchestration accounts independently of
   the legacy collaboration flag. Observe the browser test RED, then GREEN; keep
   guests excluded. Existing 22 collaboration/mention browser tests pass.
2. Budget audit/implementation: establish a conservative bounded per-run liability,
   known model pricing, atomic global admission, fail-closed unknown usage and
   terminal settlement before enabling broad paid usage. Verify concurrent runs,
   uncertainty, midnight and account deletion. Do not claim an invoice guarantee
   from an observed-spend threshold.
3. Worker safety: make the root-owned runtime file control worker enablement;
   include its health when deployed, and check quiet hours at actual authorization
   and publication. One worker/concurrency1 only. Validate packaging and delayed
   job behavior with regression tests before enabling.
4. Root hosted QA: test explicit consent, both specialist consultations, handoff,
   revocation, group mention/reload, normal chat, proactive schedule save and one
   idempotent QA delivery. Inspect actual accounting, non-QA data, worker health
   and logs. Do not use unrestricted synthetic test endpoints on production.
5. Root release: review, commit by function, push current branch, require green PR
   checks, merge, require exact-main push CI, consume verified release through the
   existing poller, verify digests/SHA/readiness, rerun hosted smoke, then expand
   adult rollout and document kill-switch commands and remaining limitations.
