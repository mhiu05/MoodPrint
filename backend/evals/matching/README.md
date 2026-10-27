# Matching evaluation (offline, synthetic)

Compares the rollback scorer `rules-v1` with `rules-v2` without any network call, provider or real data.

```bash
cd backend
uv run --locked python -m evals.matching.generate      # rewrites personas_v2.json and pair_labels.json (seeded)
uv run --locked python -m evals.matching.benchmark --out evals/matching/report.json
```

## Dataset

- `personas_v2.json` — 60 synthetic personas from seven interest archetypes: 12 v1-shaped (v1 vocabulary, no v2 facets), 6 sparse (minimum selections, no activities/availability), 42 full v2; 24 of the 48 non-v1 personas have no availability.
- `pair_labels.json` — 300 random persona pairs, each labelled 0/1/2 ("would plausibly enjoy a first conversation") by **three rule-based proxy raters** `r1` (intent/archetype), `r2` (shared interests) and `r3` (language + activities + shared items), with 10 % seeded disagreement. Krippendorff's α is reported in the report.

**The labels are provisional.** They are not human judgments and partly reuse the same signals the scorers see, so a passing gate on them is necessary but not sufficient to switch production to `rules-v2`. Obtain independent human judgments before relying on the quality gate. Current algorithm and evidence limits: [matching algorithm](../../../docs/matching/algorithm.md), [evaluation](../../../docs/matching/evaluation.md).

## Metrics

NDCG@5 and Precision@5 (mean label ≥ 1.5) over each viewer's labelled peers; coverage (viewers with ≥ 1 candidate); mean candidates per viewer; exposure Gini over top-5 appearances; reason faithfulness (every v2 reason names an item both profiles share; must be 100 %); symmetry violations (must be 0); p95 ranking time per viewer at 60 and 600 personas (600 = the 60 replicated ten times with small mutations).

Gate (05 §12): NDCG@5(v2) ≥ NDCG@5(v1) + 0.05, coverage(v2) ≥ coverage(v1), Gini(v2) ≤ Gini(v1), faithfulness 100 %, 0 symmetry violations, p95 at 600 personas < 50 ms.

`tests/test_matching_eval.py` runs the harness on a 10-persona slice in CI.
