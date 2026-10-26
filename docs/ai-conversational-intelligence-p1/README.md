# P1 conversational intelligence — Draft delivery

Base: verified main `5e73a130fd0f081887c3c2ab2093c43674388012`.
Branch: `feat/ai-conversational-intelligence-p1`.
Evaluated application: `2911eb63f6c72301c2b72837bfca8090e457a8c6`.
P0 remains deployed; this branch must not be merged or deployed automatically.

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

Implementation and live evaluation are complete. **P1 release: PARTIAL / HOLD.**
An unused scope no longer forces Nhịp into analysis for explicit conversation or
practical requests. Tool selection can only remove permission, never grant it.
Analysis retains backend-controlled facts and gains bounded brief/no-repeat choices.
Five runtime persona layers preserve frozen historical variants and F03 projection.

| Scope | Observed result |
| --- | --- |
| P0 prerequisite | [PASS: migration, integration and staging](../ai-p0-integration/FINAL.md) |
| Backend regression | `pytest -q --tb=short`: **623 passed**, 448.54 s (reviewed source) |
| Static verification | Ruff, configured mypy over 89 application files, frontend typecheck: PASS |
| Frontend and contract | 54 unit tests, production build, OpenAPI/schema drift checks: PASS |
| Real browser/full stack | 4 selected tests: saved history, five bots, ownership, logout/relogin, mood evidence, desktop/mobile, keyboard and axe checks: PASS |
| New deterministic coverage | 17 cases through the real SDK with a synthetic model, plus 6 fail-closed evaluator-gate cases; existing privacy/evidence regressions retained |
| Live development comparison | 12 new synthetic scenarios, 26 turns per arm; P0 **24/26** completed, final P1 **26/26**, zero final objective assertion failures |
| All live rounds | 165 requests / 165 responses with known usage; estimated **USD 0.044654**, reservation cap USD 2 |
| P1 release decision | **PARTIAL / HOLD**: factual accuracy, uncertainty calibration and latency stability need review; independent human review pending |

Read [architecture and security boundaries](architecture.md),
[comparison, methodology and limitations](evaluation.md),
[machine-readable final summary](evaluation-summary.json),
[verification](verification.json) and [source fingerprints](source-manifest.json).
[Blinded before/after conversations](human-review-blind.md) are prepared for an
independent reviewer; [labels are separate](human-review-key.json).
Reports contain synthetic text only, never production conversations or keys.

The first complete backend run found five prompt-composition expectation failures
(605 passed); expectations were updated to assert the exact complete layered
prompt while retaining ownership, memory and tool assertions. The final full run
passed all 610 before source review. After review fixes, the full suite passed 623. Initial live outputs, scores and evaluator corrections remain
visible; no human review or statistical significance is claimed.

No dependency, migration, public API or frontend behavior changed. Intent routing
is a bounded Vietnamese heuristic; free conversation has no universal semantic
claim validator. Analytical numerical output remains deterministic. An unused
scope keeps the conservative F03 stamp and may lose harmless next-turn continuity.
The reviewed run had p95 3.820 s versus 4.060 s for P0, while the previous candidate
had p95 9.305 s. Final judged uncertainty calibration was 4.750 versus 4.917 and
factual accuracy 4.875 versus 4.917. Runs were not interleaved; investigate before release.

GitHub CI and Draft PR links are recorded in the PR description after publication.
Initial raw XML, local test logs and generated screenshots are retained locally;
they are not part of the commit.
