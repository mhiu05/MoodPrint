# MoodPrint live AI — final evaluation

24/10/2026, Asia/Bangkok. **Local synthetic integration PASS; overall release PARTIAL/HOLD.** No commit, push, cloud deployment, new remote DDL, .env secret disclosure, .gitignore edit, Auth bypass or RLS relaxation was performed.

## A. Live provider and usage

Actual configured model: **gpt-6-luna**, OpenAI Agents SDK **0.24.0**, OpenAI Python **3.37.0**, Responses adapter. A dated model snapshot was not captured; do not treat the alias as an immutable snapshot. Structured output, function calls, buffered streaming and token receipts were observed. Reasoning/verbosity parameters were left at provider defaults for all variants; no model upgrade or silent fallback.

**283 inference attempts:**279 text attempts (including72 judge requests),2 synthetic TTS calls and2 actual STT calls. Text receipts:276; known usage **255,939 input tokens**, including3,861 cached, and **74,618 output tokens**. Estimated known-text cost **$0.06255541**, using [Standard short-context prices](https://developers.openai.com/api/docs/pricing) fetched24Oct2026. This excludes audio charges and3 incomplete text attempts with unknown billing; it is not an invoice or a zero-cost assertion for cancelled requests. TTS binary responses did not expose usage. STT price is$0.0045/minute; standalone audio6.05s and browser capture approximately8s. [Full accounting](performance-usage.json).

No retry was configured or observed. Real timeout at0.3s, HTTP cancellation after provider start, duplicate intent and consent revoke passed without a final output. Incomplete calls remain explicitly unknown. Provider503/no-retry behavior has deterministic transport tests; an actual remote503 was not induced.

Latency, no-tool batches: baseline p50=2.422s/p95=3.747s; candidate batch p50=2.539s/p95=4.306s; heldout p50=3.051s/p95=6.664s. These finite measurements are not a load test or SLA.

## B. Five companions

All180 dataset outputs (60 cases × baseline/A/B) validated the real structured-output contract. There were no observed textual hard-gate failures in the blinded judge. Permission/privacy claims also rely on separate domain tests; textual scoring alone cannot certify authorization.

| Bot | Prompt before → after | Calibration/dev baseline → chosen | Heldout baseline → chosen | Tools and qualitative assessment |
|---|---|---:|---:|---|
| Mây | legacy-v1 → legacy-v1 | 4.775 → 4.775 | 4.413 → 4.413 | Real propose_memory PASS; retain baseline because development candidates did not improve it. Warm, responsive; still sometimes automatic praise/questions. |
| Gương | legacy-v1 → a1 | 4.650 → 4.844 | 4.663 → 4.738 | Real propose_memory/propose_private_item PASS; accepts corrections and separates hypotheses from facts. Some examples remain generic. |
| Nhịp | legacy-v1 → b1 | 4.525 → 4.825 | 4.250 → 4.750 | Real read_mood_summary PASS against selected hosted data, no notes. Honest missing-day/no-data behavior; limited to permitted date scope. |
| Rủ Rê | legacy-v1 → b1 | 4.725 → 4.794 | 4.463 → 4.450 | No model tools by design. More actionable activities; tiny heldout decrease retained, not hidden or tuned away. No production activity session is claimed. |
| Cầu Nối | legacy-v1 → a1 | 4.025 → 4.869 | 3.975 → 4.838 | No model tools by design. Correct private/public-profile separation; cannot inspect actual candidate results or identities from model context. |

Selected overall heldout score **4.3525 → 4.6375/5**,20 cases, four per bot. Selection was frozen before heldout; no post-heldout prompt tuning. Small samples, same-model judge bias and stochasticity limit this result. Labels were blinded, positions randomized and20% of groups rejudged in reversed order; average order-related difference0.1688/5 on tuning splits. Primary-agent manual inspection was performed; independent two-human calibration was not. [Variants](prompt-variants.md), [scores](comparison-results.json).

## C. Functional changes

- Versioned shared/persona/strategy instructions and exact frozen baseline in `backend/app/ai/prompts.py`; evaluated per-bot defaults, not a blanket replacement.
- `ai/context.py` retains a contiguous, ordered suffix of at most24 messages/24,000 UTF-8 bytes, with at most10 authorized bot-scoped approved memories if space remains. Latest user input takes priority. Real turn6 recall and turn10 correction passed; histories are not compacted or shared across bots.
- Development-only actor allowlist, checked in feature availability, acceptance and provider invocation. The local live server resolves configured Supabase Auth subjects to existing internal actors. Normal sessions, age and consent still apply. Memory-proposal tools are omitted when MEM is off and still recheck permission during execution.
- Content-free provider events record request starts before model work, completed receipts before output validation, and tool names without arguments. Unknown cancellation/timeout usage is retained.
- Optional PostgreSQL `ai_usage` ledger: integer nano-USD price snapshots, monotonic usage snapshots, idempotent settlement, worker-owned45s leases and expired-run recovery without provider replay. Completion and accounting settle in the same DB transaction. Retention/account deletion continue even when new capture is disabled. No monetary cap/allocation was invented for this unlimited-budget evaluation.
- Frontend restores draft text after confirmed terminal AI failure; a transport interruption still requires reconciliation. Consumed mood access is not automatically regranted. Lazy-loaded Markdown renders prose, emphasis, lists and code while excluding active links, remote images and HTML. Initial bundle remains about136KB gzip; Markdown is a separate37KB gzip chunk.

New source: `ai/{prompts,context,usage,accounting}.py`, `evals/{live,judge,report,server,timeout_live,voice_live}.py`, migration0006, `MessageMarkdown.tsx`, live Playwright suite/runner and focused regression tests. Existing changes: provider/runtime/routes/config, actor-scoped session features, voice gates, retention/deletion, conversation renderer and environment example. Legacy Alembic import formatting was corrected for Ruff; existing approved remote SQL was preserved.

## D. Verification

**PASS:**175 backend tests with disposable PostgreSQL, Ruff over all backend files, mypy47 source files,85 frontend unit tests, typechecked production build,18 API-fixture browser tests,15 preserved legacy browser tests,6 real local full-stack tests. Four distinct live browser tests passed across three runs with hosted Auth/DB and actual OpenAI; fixture HTTP is not counted as provider evidence. [Commands/results](test-evidence.json).

Real browser: all five bots, correct selected-date tool, note exclusion, memory proposal without auto-save, peer approval denial, explicit owner approval, mobile390/desktop1440, axe zero violations in the tested conversation, ten turns, updated fact, reload dedupe and cross-bot isolation. All three existing tool names were observed in real model calls. Cancellation, duplicate intent and revoke passed. [Tools](tool-calling-results.json), [multi-turn](multi-turn-results.json), [safety](safety-regressions.json).

Voice: standalone real Vietnamese STT PASS. Browser AudioWorklet→WAV→authenticated STT→editable preview→explicit send PASS using synthetic Web Audio input. Native `getUserMedia` returned NotSupportedError in an isolated Chromium probe; native microphone permission/physical devices/iOS remain unverified. This limitation is not labeled PASS.

The0006 expand migration ran successfully on disposable local PostgreSQL. New table has RLS enabled and expected constraints. It was not applied remotely. [Local rehearsal](accounting-local-verification.json), [reviewable SQL](0006-ai-usage-review.sql), SHA256 **7119b1d9cd6e2d1a58df9c830dc950210b8c66499b3ee24d6d8e6bb402b78b22**.

## E. Remaining work / checkpoint

1. **Separate approval required:** apply the exact reviewed0006 SQL to the existing Supabase project, verify new-table ACL/RLS with the runtime role, then enable accounting deliberately. Hosted schema remains0005 and default accounting remains off. Historical initialization/runtime SQL approvals do not approve this new content.
2. **Q02/Q05, P07.03/P08.03/P09.02 HOLD:** provider account/project region, retention, deletion, backups/restore and full account deletion remain unverified. Application `store=false` does not establish ZDR. Real private-user rollout remains gated; synthetic live tests were explicitly authorized.
3. **P02.02/P02.03 PARTIAL:** accounting/fencing is implemented/rehearsed locally, but remote reconciliation, process-kill schedules, DB fault exhaustion and multiple workers sharing RAM conversations are not fully qualified. Keep one application worker. There is no production monetary allocation/reconciliation service.
4. **P08.02 PARTIAL:** live comparison completed; independent human calibration and a larger untouched future test set remain. Do not keep tuning on the now-opened heldout set. Mây unchanged; Rủ Rê heldout essentially flat.
5. **P07.02/P07.04 PARTIAL:** native mic, mobile Safari, physical touch/audio and manual assistive-technology checks remain. Existing foreground-midnight Nhịp picker bounds still require refresh; backend rejects expired scopes.
6. Domain-owned matching scores, identity, invitations, connections and activity persistence remain deterministic. No additional profile/candidate tools were exposed without an explicit source-selection contract. No cloud deployment, signup, SMTP or password recovery expansion was attempted.

## F. Run locally

Use the exact executed commands in [README](README.md). FastAPI live entrypoint is `python -m evals.server` from backend; Vite targets port8004 and serves5177; `scripts/run_live_browser.py` uses only configured synthetic accounts and the generated synthetic WAV. Paid evals require `--live` and a fresh output filename; `evals.report` rebuilds metrics offline. The agent did not edit `.env`; final inspection observed local AI_ENABLED=true, STT=false and accounting=false. The live test entrypoint explicitly forces global AI off and scopes access to synthetic actors. Stop owned local processes after tests; restart the disposable local DB container before reusing its test URLs.
