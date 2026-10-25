# Matching v2 gate decision (C-06, T-EVAL-01)

Date: 2026-10-25 · Report: [`backend/evals/matching/report.json`](../../../backend/evals/matching/report.json) · Method: [evals/matching/README.md](../../../backend/evals/matching/README.md)

Command (executed): `cd backend && uv run --locked python -m evals.matching.benchmark --out evals/matching/report.json`

| Metric | rules-v1 | rules-v2 | Gate |
|---|---|---|---|
| NDCG@5 | 0.0613 | 0.8728 | v2 ≥ v1 + 0.05 — met |
| Precision@5 (mean label ≥ 1.5) | 0.000 | 0.178 | — |
| Coverage (viewers with ≥ 1 candidate) | 0.217 | 1.000 | v2 ≥ v1 — met |
| Mean candidates per viewer | 1.03 | 51.73 | — |
| Exposure Gini (top-5) | 0.814 | 0.225 | v2 ≤ v1 — met |
| Reason faithfulness | 1.0 | 1.0 | 100 % — met |
| Symmetry violations | 0 | 0 | 0 — met |
| p95 ms per viewer at 600 personas | ~4 | 33–44 (three runs on this workstation) | < 50 ms — met |

Krippendorff's α of the proxy labels: 0.286 (target ≥ 0.4 for human raters — not met).

## Decision

- The metric gate passes, **but on provisional, rule-based proxy labels** (no human raters were available in this session) whose agreement is below the target.
- v1's low coverage is largely structural: most personas use v2-only tags or goals that the frozen v1 vocabulary ignores, so this comparison overstates v2's advantage for v1-shaped data.
- Therefore **`MATCHING_SCORER` stays `v1` by default** (`backend/app/core/config.py`, env examples). Recommended rollout: `shadow` on staging for ≥ 3 days (G6), human-rated labels, then switch to `v2`.
- `v2` is fully implemented and tested (T-MATCH-01…06) and can be enabled per environment with `MATCHING_SCORER=v2`; rollback is `MATCHING_SCORER=v1` and a restart.
