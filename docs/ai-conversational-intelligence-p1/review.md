# Change review

Reviewed against main `5e73a13`; evaluated application commit `6da23ea`.
No unresolved correctness or authorization finding requiring an application patch
was established in the reviewed paths and executed regressions. This is a scoped
engineering review, not independent human review of conversational quality.

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
