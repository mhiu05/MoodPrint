# Evaluation run `final2-b`

- model `gpt-6-luna` · openai-agents 0.24.0 · openai 3.46.0 · commit `8eaef58176b1` · prompt `companion_v3` · tools `77f3941b03fdb67a`
- effort `low` · repeat 1 · groups ['knowledge', 'memory', 'screenshot', 'roleplay']
- outputs: 30 (0 crashed/blocked)

## Deterministic assertions
- P0: **283/283** passed
- P1: 25/25 passed

## Rubric grades (coding agent; no judge model)
- R-01: mean 2.78 over 9 graded outputs (min 2)
- R-02: mean 3.00 over 8 graded outputs (min 3)
- R-03: mean 2.88 over 8 graded outputs (min 2)
- R-05: mean 2.80 over 10 graded outputs (min 2)
- R-07: mean 3.00 over 4 graded outputs (min 3)
- R-08: mean 3.00 over 7 graded outputs (min 3)
- graded ≥ 2: 46/46
- **ungraded: 0** of 46 expected (case, repeat, rubric)

## Latency and usage
- TTFT p50/p95 (ms): 1189 / 3530 (n=52)
- turn latency p50/p95 (ms): 2088 / 5767
- tokens per turn: mean 1697, p95 4478
- run spend: $0.014623 · calls 77 · cumulative ledger $0.137606 of $2.9
