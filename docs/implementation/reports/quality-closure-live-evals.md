# Live evaluation continuation readiness

Prepared code SHA:`040816f8ec38c68dc2eb7d45ac5ac4d5653e80c7`. Current source/prompt/SDK/config/case/corpus hashes are pinned in`agent/evals/plans/quality-closure/`. All planned slots remain NOT_RUN; this directory is not a spending authorization.

## Budget and historical evidence

Owner budget: model `gpt-6-luna`, `max_usd = 2.90`, `max_calls_total = 900`, `max_tokens_total = 8000000`, `max_tokens_per_run = 60000`, `max_output_tokens_per_request = 4096`, scopes phase3-live-compat/phase3-eval, expiry 2026-11-12T00:00:00Z. Read the existing original worktree ledger in place; never copied/reset/replaced. Calls 900/900, remaining 0. Ledger committed USD 0.16324955 consists of 0.15527855 reconciled provider-reported cost (894 calls) plus 0.007971 conservative holds (6 unknown calls); known tokens 1796840 plus 33326 held. This is ledger accounting, not an invoice assertion. This task made 0 paid OpenAI calls.

Both `run.py --suite live` and `run_s06.py --live` were exercised against that existing ledger and refused with exit 3 before key/provider construction. Additional USD headroom never bypasses the call ceiling. No cap, expiry, model, scope or authorization was edited.

Legacy output directories are preserved. They lack current source/prompt/case fingerprints, so historical-reconciliation.json credits zero current slots; this does not erase their historical measurements. Current prompt names remain companion_v4, roleplay_partner_v2, roleplay_coach_v1, evidence_reader_v1, risk_assessor_v1; every prompt text hash, all agent/shared/eval source hashes, case/repeat selection, SDK versions, tools digest, requested model `gpt-6-luna` and corpus are pinned. gpt-6-luna is a provider alias, not an invented immutable dated snapshot; any provider change requires a new comparable run record.

## Implemented protocol

| Plan | Cases/repeats | Missing outputs | Request bound |
|---|---|---:|---:|
|Current fixture-backed Companion/screenshot/roleplay suites|67 x 3|201|336 minimum through 1638 maximum|
|Same knowledge cases with integrated PgVector adapter|20 x 3|60|60 minimum through 480 maximum|
|Original S-06 plain reference + AJSONstream + Bclosingtool + Cpostprocess classifier|20 x 4 x 3|240|300 (B uses the same response, C uses two calls)|
|Total|All planned repetitions|501|696 minimum through 2418 maximum|

The exact missing observations are 501 slots. Future model tool loops determine the actual call count; claiming one exact forecast would be false. 2418 is the reproducible conservative maximum under the current max-turn and approval limits, not a promise to consume it.

Coverage includes chat, injection, approval, knowledge/no-result/citations, memory, screenshot, roleplay, urgency, cancellation, provider failure, multi-turn and structured output. Inj-06 now checks clarification before preparation; know-10 source absence/legal grounding, role-03 danger exit, app-03 permission-before-write, truthful rejection, save-intent handoff and plan-step filtering have offline regressions. A04 checks actual citation identity, not title alone. Crashes/empty executions become failed assertions. Missing/duplicate/orphan results or grades cannot pass. Every assertion and grade must bind provenance_id and output_sha256 to the exact output, with worst-of-3 rubric >= 2, every P0 passing and P1 at least 2/3.

Original S-06 is separate from detector A/B/C. The provider-neutral runner and injected OpenAI adapter implement decoded incremental JSON reply streaming (including split escapes), a final read-only assessment tool excluded from runtime write/tool budgets, and a separately metered post-classifier. Deterministic urgency floor is recorded separately from model assessment. Each slot has a fresh metered run ID; cancellation/refusal/malformed/absent assessment and missing/nonfinite/negative TTFT are failures. Offline scripted tests validate mechanisms; no fabricated live latency/quality/grading or mechanism selection is reported.

`evals.real_knowledge:factory` requires a loopback int database, an exact published voyage-4 corpus and the existing cumulative Voyage ledger. It yields real PgVectorKnowledgeRetriever; no fixture fallback or poison/empty fixture override. Voyage query reservations are serialized and include 5 attempts, unknown billing keeps the conservative hold. Main live runner refuses absent real factory and records corpus-version drift as failure. Real integration/browser tests use HashingEmbedder/scripted model explicitly and do not substitute for paid live repeats.

## Exact owner action before paid continuation

Approve an amendment to the EXISTING authorization only; keep the same append-only ledger. Proposed conservative envelope: additional maximum calls 2418 => cumulative max_calls_total=3318; additional tokens 30060000 => max_tokens_total=32000000 (existing known + held 1830166 gives cumulative 31890166); historical verified pricing snapshot worst-case additional USD 15.03 => cumulative max_usd=15.20 (0.16324955 already committed+15.03=15.19324955). Keep `max_tokens_per_run = 60000`, `max_output_tokens_per_request = 4096`, model `gpt-6-luna` and existing scopes. Owner must populate approved_by / approved_on, explicitly approve these amended caps, verify current pricing snapshot and set expires_on covering the chosen execution window; existing expiry need not be changed if execution finishes before 12 November. No budget draft grants permission.

Use synthetic data only, no paid judge, same corpus07 / digest f5e14a3b...ffe8 and pinned current prompts. Owner must separately authorize any real-user model-assisted safety data handling; this continuation does not enable it. Provide credentials privately in process/.env.live, not in committed artifacts. Voyage uses its existing 1 USD cap and original ledger; its authorization is separate.

After approval, regenerate/compare the manifests at the chosen code SHA; execute full 3x protocol with these entrypoints (run IDs must be new, but the budget and ledger must remain the originals):

```powershell
uv run python agent/evals/run.py --suite live --repeat 3 --effort low --budget <existing-budget> --ledger <same-ledger> --run-id <new-final-run>
uv run python agent/evals/run.py --suite live --groups knowledge --retriever real --retriever-factory evals.real_knowledge:factory --corpus-version kb-20261109-07 --corpus-sha256 f5e14a3b96c14c8aed2ba3d144d29e680c52132861b18c470185a07e8343ffe8 --repeat 3 --budget <existing-budget> --ledger <same-ledger> --run-id <new-real-run>
uv run python agent/evals/run_s06.py --live --out <new-results-directory> --budget <existing-budget> --ledger <same-ledger>
```

Set MOODPRINT_EVAL_DATABASE_ENV, MOODPRINT_VOYAGE_LEDGER, MOODPRINT_VOYAGE_KEY_FILE and MOODPRINT_EVAL_CORPUS_SHA256 privately for the real adapter. Reconcile actual provider usage/unknown holds; independently read every rubric-relevant output; write grades with grader/reason/provenance/output digest. NOT_RUN remains until each slot is observed. Paid quality gates are BLOCKED now.
