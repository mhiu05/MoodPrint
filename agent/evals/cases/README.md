# Synthetic urgency phrase sets

All text is invented. No real student data.

| File | Role |
|---|---|
| `safety_phrases.jsonl` | Written together with the rules. Measures consistency only. |
| `safety_heldout.jsonl` | Written before running the rules; first-run results are recorded in `agent/tests/test_safety.py`. Contaminated after the first fix round. |
| `safety_heldout2.jsonl` | Same procedure, second round. Contaminated after the fix round that followed. |

Keyword recall on unseen phrasings was 0.74 and 0.79 on the first runs, so the final 1.0 is a
training-set number. Treat the deterministic layer as one safety net, not as evidence of safety.
