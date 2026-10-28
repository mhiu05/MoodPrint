# Scoped independent review — 862e036

Date:2026-10-28, Asia/Bangkok. Same read-only reviewer as the
[complete whole-branch review](independent-review-26ca93d.md). Exact head
`862e036e711e7976d83b4ecf6ec6b6a4eea5d218`;12-file delta from26ca93d inspected,
including new tests, callers and private orphan helpers.

**Verdict: CHANGES REQUESTED.** Original R1–R3 resolved in source, but one new
P2 interaction: `service.py:189` reuses the pre-admission bucket clock as
signup_started_at/lease origin. The0017 orphan helpers match provider identity
creation within60s of signup_started_at. Bucket admission waiting>60s can now
send signup outside that window, leaving an unmatchable orphan after grant failure.

Required correction: keep the original bucket sample only in the request frame
for the same in-process definitive-rejection refund, restore a separate fresh
post-admission provider-start sample, and retain counts when original refund
information is unavailable. Preserve CAS winning-transition gating and never
fall back silently to provider-start time for refund. No migration is necessary.
Reviewer confirmed this proposed approach resolves the timestamp coupling;
the resulting exact SHA still requires review.

Reviewer checks: docs63 files/423 links/109 operations PASS; SQL9 pins/9consumed
PASS; delta whitespace PASS, whole branch only intentional prompt09 hard breaks.
No DB/browser/load tests. No other material issue found. Nonblocking forced-token
tampering concern, declined-certification list and release HOLD remain unchanged.
