# P1 conversational intelligence — implementation plan

Base: verified main `5e73a130fd0f081887c3c2ab2093c43674388012`.
Branch: `feat/ai-conversational-intelligence-p1`. P0 deployment remains unchanged.

Acceptance criteria:

- Explicit conversation/listening/practical requests do not become mood analysis
  merely because Nhịp received an unused sharing scope. Routing can only remove a
  tool; it cannot authorize data. Ambiguous scoped requests retain the P0 path.
- Analysis still requires current evidence and backend-authored numerical claims.
  Query-aware brief plans select relevant verified facts instead of repeating the
  entire summary; the existing renderer remains the default safe path.
- Five runtime persona layers adapt to joy, listening, corrections, rejected
  activities, boundaries and missing context, without changing frozen historical
  prompt variants, age eligibility, consent, receipts or F03 context projection.
- New SDK/runtime regressions pass; matched real-model baseline/candidate runs use
  new synthetic Vietnamese scenarios, with objective assertions and blinded judging.
- No schema, public API or frontend contract change. No extra model call for intent.
- All applicable regression/static/build/browser checks pass before a Draft PR.

Sequence: record RED behavior; implement bounded intent routing and fact selection;
run targeted regressions; evaluate fresh scenarios against unchanged P0; retain
only supported improvements; run broader checks and publish evidence and Draft PR.
The historical reserved/heldout fixtures are not used for prompt tuning.

Live evaluation reservation: at most USD 2 using the repository's versioned rate
snapshot, bounded provider requests/tokens, no retries, 1,200 output tokens, three
SDK steps, no provider storage/tracing. Actual usage, unknown usage, failures and
the limitations of a small development sample will be reported separately.

Status: implementation/evaluation in progress; no P1 release recommendation yet.
