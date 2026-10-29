# Independent approval — 11538b2

Date:2026-10-28, Asia/Bangkok. Same fresh read-only reviewer as
[whole-branch review26ca93d](independent-review-26ca93d.md) and
[scoped review862e036](independent-review-862e036.md). Exact approved code SHA:
`11538b233c9ae9e127df7d133a73e01e0e242ec2`, base
`984753389aa8bd4b3112b19a8beceb1e538fd659`.

**APPROVED for source integration, subject to pending execution and CI gates.**
Complete latest six-file delta, new tests/callers, combined R1–R3 and evidence
reviewed, preserving the complete237-file whole-branch coverage. No unresolved
material finding or new P0/P1/P2 remains.

- R1 refund uses exact request-local admission time and winning rejection CAS;
  missing timestamp retains count conservatively.
- Provider-start is sampled separately after admission waits. Both delayed
  admission regressions cover rejection and private-helper deletion after grant failure.
- R2 linked reservations/replay mappings/charges remain while other records expire.
- R3 failed startup repair retries until successful without restart.

Reviewer actually ran docs64 files/426 links/109 operations/68 settings/48 tables,
historical SQL9pins/9consumed and latest-delta whitespace: PASS. Whole-branch
whitespace has only two intentional prompt09 hard breaks. Release/config inspection:
hold, flags, unset budget and .gitignore unchanged. No reviewer DB/browser/load/
hosted/paid tests; author54 target tests and Ruff/mypy are separate evidence.

Nonblocking forced-token-tampering hardening remains recorded in the whole-branch
report, with no normal takeover path found. No other production behavior was
deliberately excluded from source review. Deliberately not certified: D04 hosted
Auth/CAPTCHA/cascades/permissions; D01–D04 live capacity/prices/budget/disclosure/
retention; manual assistive/mic/device keyboard; deferred Driver spotlight;
actual post-merge publication/deployed state; unfinished execution/CI gates.
These require their own evidence/owner action. **Public release remains HOLD**,
all six flags false and paid budget unset.
