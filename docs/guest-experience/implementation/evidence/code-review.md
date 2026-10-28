# Independent review and author fix pass

Current finish status: [complete whole-branch review](independent-review-26ca93d.md)
found3 additional P2; [scoped review](independent-review-862e036.md) found one
timestamp interaction, all resolved. [Independent11538b2 approval](independent-review-11538b2.md)
supersedes the historical incomplete verdict below. [6316f82 source approval](independent-review-6316f82.md) extends the test/evidence
review. The final activity-race delta requires scoped approval/latest-head CI. See
[finish verification](final-review-and-merge.md). Release remains HOLD.

## Historical review before b8c7efb

Further finish review: [b49e109 approval](independent-review-b49e109.md) covers
the deadline-test/evidence delta. A controlled browser-history gap discovered
during PR CI is fixed using native popstate cleanup; new exact-SHA review and
CI must pass before merge. Complete traceability is in the finish ledger.

Review range: `984753389aa8bd4b3112b19a8beceb1e538fd659` → `6b367ece7e4c9967cddbb1b034e3ecf66acf72df`. A fresh-context `gpt-6-astra` reviewer inspected the whole branch read-only under the requesting-code-review template. Its messages identified the eight findings below. The reviewer then hit its service usage limit before delivering its final report/verdict or a complete “declined to judge” list. **No clean independent verdict is claimed.** This record preserves received findings and the author's verified disposition; it is not a replacement reviewer report.

| Finding, graded Important by effect | Author disposition and regression |
| --- | --- |
| Query embedding bypassed its guest semantic flag, price/budget and reservation | Both query/document adapters now require their own funded fenced claim. Closed query admission uses approved lexical fallback. `test_guest_query_embedding_needs_its_own_funded_admission` RED→GREEN for flag/price/budget; funded replay charges once and does not consume a document slot. |
| Document embedding could dispatch after a DB wait crossed T and wait on provider past T | Fresh conservative DB/monotonic bound before send, timeout clamped to T, no late vector publication, conservative settlement. Two document dispatch/cancellation tests RED→GREEN. |
| ORM identity map kept stale reservation state across concurrent settlement locks | Scalar day probe and `populate_existing` on locked budget/reservation; deterministic PostgreSQL competing transaction RED→GREEN, charge/reserved balance exactly once. |
| A zero-row dispatch marker still let adapters call a provider | Terminal/expired reservation now raises a fenced operation error before any send. Cancelled/uncertain marker regressions RED→GREEN. |
| Active claims expired after45s without renewal despite valid120s AI configuration | Fenced heartbeat every5s for AI, STT and both embedding adapters, lifetime cap and no upsert. AI/STT short-lease regressions RED→GREEN; stolen lease cannot revive. A blocked renewal is bounded by the existing monotonic lease and cancels work before its slot can reopen. |
| Guest end swallowed every API error and claimed accepted deletion | Failed/ambiguous request stays in the confirmation dialog with retryable error, no accepted-deletion claim; confirmed204 alone ends the tree. Browser regression RED→GREEN. |
| Generic Settings logout destructively ended a guest without confirmation | Guest session control explicitly names ending the trial and uses the shared confirmation dialog; registered logout unchanged. Browser regression RED→GREEN. |
| Purge omitted registered child authorship inside a malformed guest graph | Message/read/participant/response and related session/request/reveal authorship are checked before graph deletion; foreign evidence stays as an incident with guest access denied. Four PostgreSQL cases RED→GREEN; full exhaustive purge suite11 pass. |

Initial backend review regressions:9 failures; purge4 failures; browser2 failures. Broad first fix suite81 pass, targeted browser33 pass. Further blocked-heartbeat RED→GREEN and complete review file13 pass. Final whole-suite/load/image results are recorded in the [ledger](execution.md); intermediate passes do not replace those final checks.

Minor deferred from the reviewer: after confirming “end and create account”, the ended screen takes precedence over the signup hash, so the user must select Create account once more. Data is not transferred or exposed. This is a navigation inconvenience; it stays deferred under the one-fix-pass process.

Author rulings on review scope: D01–D04, hosted provider/CAPTCHA/backup facts, physical assistive-device checks and optional spotlight acceptance remain release holds. Synthetic tests do not establish them. The independent reviewer did not supply a complete final scope list before its limit, so final review coverage remains PARTIAL. No second reviewer or fabricated verdict was substituted.

## Completed scoped review at1b27851 and fixture follow-up

Read-only reviewer APPROVED source integration at exact
`1b2785191d9e431f4867ad8111e25ff8891e61d5`: no new material finding; terminal
room-local dismissal lifecycle/new invitation behavior and nine-file delta
inspected; docs67/445 and9pins PASS. No DB/browser/load executed by reviewer.
Declined hosted/owner/manual/spotlight/post-merge certifications remain as before.

Subsequent CI motion investigation found an inconsistent empty stored-transcript
fixture after final SSE, rather than a supported product regression. Author's
new idle/reconciliation condition reproduces RED before correcting fixture
publication order. Test/evidence-only delta requires scoped exact-SHA approval
and latest-head CI; see [current finish record](final-review-and-merge.md).

## Approved091d4f8 and cleanup test follow-up

Reviewer APPROVED exact091d4f86f0e754c79fb743a8ff27eb0f31ae9071, no new material
finding; docs67/446 and9pinsPASS, deterministic motion RED/GREEN inspected,
production tree unchanged. Later read-only cleanup investigation identified a
supported one-tick/global-completion harness race; no runtime defect established.
Actual PostgreSQL barrier and bounded exact-zero browser correction are in the
new test/evidence delta and require scoped exact-SHA approval/latest-head CI.
All declined hosted/owner/manual/post-merge certifications and HOLD remain.
