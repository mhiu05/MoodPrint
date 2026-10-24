# Prompt variants and selection

Source: `backend/app/ai/prompts.py`. Model `gpt-6-luna`, Responses/Agents0.24.0, max_output_tokens1200, max_turns3, timeout30s, retries0, store=false, tracing disabled throughout comparison. Raw token deltas remain buffered.

- **Baseline / legacy-v1:** exact original instructions, preserved and hash-checked against captured baseline artifacts.
- **A / 2026-10-24-a1:** natural Vietnamese, distinct personas, context-sensitive length, fewer automatic questions/compliments, calibrated observations, concrete activities and verified product facts. Includes examples and explicit proposal/receipt boundaries.
- **B / 2026-10-24-b1:** A plus explicit correction precedence, grounded tool use, selected-date boundaries, short confirmed-memory proposals and error/no-data handling.

Forty calibration/development cases ran before selection. Twenty heldout cases were not used to modify or select prompts. `selection.json` predates `heldout-results.json`. All three variants were then evaluated on heldout without further tuning. Quality batches expose no tools to any variant, so tool availability does not confound the prompt comparison; real domain tools were exercised separately through authenticated FastAPI/React.

Selected default map: Mây baseline, Gương A, Nhịp B, Rủ Rê B, Cầu Nối A. Mây stays on baseline because candidates did not improve development scores. Rủ Rê's tiny heldout decrease is retained in the report; no selection was changed after opening heldout. Baseline and both candidates remain callable by the evaluation CLI; the HTTP API cannot choose variants or fake models.

Judge used anonymous labels, seeded randomized order, the six user-specified weighted criteria and reversed-order repeats for20% of case groups. Mean absolute weighted score change from order repeats on tuning splits:0.1688/5. Same-model style bias and small sample uncertainty remain; this is not independent human calibration. Agent manual review inspected ordinary outputs for all bots, refusal cases, the largest score changes and real tool/multi-turn replies. No two human reviewers are claimed.
