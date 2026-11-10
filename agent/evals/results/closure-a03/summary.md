# Evaluation run `closure-a03`

- model `gpt-6-luna` · openai-agents 0.24.0 · openai 3.46.0 · commit `14fcee3f68d4` · prompt `companion_v4` · tools `77f3941b03fdb67a`
- effort `low` · repeat 3 · groups all
- outputs: 6 (0 crashed/blocked)

## Deterministic assertions
- P0: **72/72** passed
- P1: 19/21 passed
  - FAIL app-07 r1: A-07: propose_action_plan called: False
  - FAIL app-07 r3: A-07: propose_action_plan called: False

## Rubric grades (coding agent; no judge model)
- R-04: mean 2.67 over 6 graded outputs (min 2)
- R-05: mean 2.33 over 3 graded outputs (min 2)
- graded ≥ 2: 9/9
- **ungraded: 0** of 9 expected (case, repeat, rubric)

## Latency and usage
- TTFT p50/p95 (ms): 3554 / 10443 (n=12)
- turn latency p50/p95 (ms): 5510 / 12063
- tokens per turn: mean 10507, p95 16532
- run spend: $0.006853 · calls 37 · cumulative ledger $0.16325 of $2.9
