# Companion evaluations

Phase 0 uses the official SDK `ScriptedModel` in `agent/tests`; no API key or model calls are needed.
Scenario evaluations belong to Phase 3. Every future live invocation must use
`moodprint_shared.config.OPENAI_MODEL`. This applies to compaction and smoke runs as well.

Keep synthetic cases in `cases/*.jsonl`. A run writes `outputs.jsonl` and deterministic
`assertions.jsonl` under `results/<run-id>/`. Record the model, SDK version, commit,
prompt version, and tools version with every output.

The coding agent reads every output and writes `grades.jsonl` using [the rubric](rubric.md).
Do not call a judge model. Unrated cases remain unrated. High-risk cases SC-04, SC-07,
SC-09, and SC-24 must each be read; sampling does not satisfy acceptance.

No live evaluation was executed in Phase 0. Paid calls require the configured API key
and the owner's cost ceiling before running.
