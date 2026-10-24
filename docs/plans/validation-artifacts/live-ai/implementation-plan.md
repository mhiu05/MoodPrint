# MoodPrint live AI implementation plan

**Goal:** Evaluate real models, improve the existing five companions and verify product behavior with synthetic data.

**Spec:** User's attached “CODEX MASTER PROMPT — MOODPRINT LIVE AI, AGENT INTELLIGENCE & PRODUCT QUALITY”, 24 October 2026.

**Architecture:** Keep one buffered Agents SDK runtime and domain authorization. Freeze legacy prompts for the baseline, compare two versioned candidates on calibration/development, select before opening heldout. Local live access is restricted to configured synthetic actor IDs. Provider telemetry contains counts and tool names, never private content.

**Constraints:** No commit, push, cloud deployment, .gitignore changes, auth bypass, unapproved remote DDL, private matching data, automatic memory approval, or fake-model live evidence. Work directly in the user-specified E:/MoodPrint workspace. The user explicitly requests autonomous implementation and opts out of repeated design/budget confirmation. No specialist subagents.

## Review focus

- Provider cancellation after request start must retain unknown usage.
- Guardrail failures must still account for completed model responses.
- Missing consent, a different actor, or changed data version must deny tools/output.
- A correction at turn 8 must supersede a fact at turn 1 inside bounded context.
- UI retries must keep the draft and scope and must not duplicate final output.

## Tasks and evidence

- [x] Real provider smoke with unchanged prompt; save safe usage/status.
- [x] Baseline five bots on existing calibration/development cases; preserve hashes.
- [x] Provider usage observer and development-only actor allowlist. Files: core/config.py, ai/provider.py, ai/runtime.py, ai/routes.py; test denied actors, callback timing, guardrail/cancel usage.
- [x] Versioned legacy/A/B instructions and repeatable finite evaluation runner. Files: ai/prompts.py, evals/live.py; validate split selection, metadata, no overwrite/retry/fake fallback. Compare same cases and model settings; review outputs and hard gates.
- [x] Bounded context selection and multi-turn correction/isolation. Files: ai/context.py, ai/runtime.py; test oldest facts retained within a byte budget and newest input retained under pressure.
- [x] Run real authorized tools, failure/cancel/revoke scenarios through FastAPI and React. Reuse synthetic accounts and consent. Add focused regressions for observed failures.
- [x] Inspect voice privacy/processor gates, run synthetic STT if permitted, keep text fallback.
- [x] Implement/rehearse durable accounting locally if feasible; do not execute new remote SQL without separate approval. Document exact remaining boundary.
- [x] Run Ruff/mypy/backend/frontend/build/relevant browser suites; review diff and update release evidence.

## Ledger

- Smoke PASS: gpt-6-luna, Agents 0.24.0/OpenAI 3.37.0; one request, 541 input/99 output tokens; default flags unchanged.
- Ruling: old smoke document's fixed monetary cap and additional live permission gates are superseded by the user's explicit synthetic live-call authorization. Account-level ZDR remains unverified and is not claimed.
- Ruling: use direct execution in requested workspace; no worktree that would hide changes or omit local configuration, no commits, no delegation.

- Final checkpoint: scoped synthetic live work completed; release HOLD for separate remote SQL approval, provider policy/human/native-device qualification. See final-evaluation.md.
