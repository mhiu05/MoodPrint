# Change review

Reviewed against main `5e73a13`; final reviewed application commit `2911eb6`.
No unresolved correctness or authorization finding requiring an application patch
was established in the reviewed paths and executed regressions. This is a scoped
engineering review, not independent human review of conversational quality.

A separate read-only code reviewer found two P2 defects in the first delivered
head `0f833ca`: generic arithmetic/negated statistics could force mood analysis,
and the live runner's exit code ignored intent-only assertion failures. Both were
reproduced and fixed. A first broad data-refusal regex crossed clause boundaries;
new positive mixed-clause SDK regressions exposed that overmatch before the
refusal was narrowed to a direct mood-data subject. Review of `2911eb6` found no
remaining important issue in this narrow fix; seven no-network routing probes
passed. Full application verification is reported separately.

The first review regression run had four correctly failing SDK routing cases and
six missing-gate failures. One new positive control incorrectly inspected evidence
that is intentionally cleared at terminal completion; its assertion was corrected
to verify the actual backend-authored 2/7 count and 2.5 mean. The corrected focused
run passed 54 cases. Mixed-clause RED failed two of three controls; GREEN passed
all three after narrowing the regex. Initial failures remain in local logs.

The reviewer also noted that the blinded human pack omitted source facts. Its
generator now includes actual verified mood reads and approved-memory inputs from
each turn, with duplicates removed, so source correctness can be judged without
revealing the arm label or recovering revoked context. The live exit gate now
fails closed for failed status, empty/missing evidence or either assertion group.

The intent helper reads only the final authorized user message. Tool selection
can only remove a mood reader; owner, consent, source version and receipt checks
remain in the existing backend. Scoped numerical responses still require current
evidence and a strict plan with no model-authored numerical fields. Presentation
preferences only omit detail. No revoked context reconstruction, automatic memory,
new inference method, additional agent or classifier call is introduced.

Historical static prompt evaluation remains frozen by composing the new layer only
for actual runtime contexts. Existing F03 projection and policy recognition are
unchanged, and the historical fixture files remain identical to main.
Regression coverage exercises explicit opt-out, practical/conversational requests,
analysis mixed with casual words, missing permissions, and a refusal of lengthy
analysis that must not accidentally decline analysis altogether.

Known limits remain actionable release work: indirect or mixed-language intent can
miss the heuristic; unused scopes retain conservative continuity filtering; free
conversation has no universal factual validator. Final live uncertainty calibration
and latency were worse than the baseline. The small development set and same-model
judge cannot establish general quality. Keep the PR Draft and release HOLD pending
independent Vietnamese review and a larger untouched/interleaved comparison.

See [verification](verification.json) for actual commands/results and
[evaluation](evaluation.md) for preserved initial failures and trade-offs.
