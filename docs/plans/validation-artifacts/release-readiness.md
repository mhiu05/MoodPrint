# Release readiness — HOLD

24/10/2026, Asia/Bangkok. **Local synthetic live-AI integration PASS; public release PARTIAL/HOLD.** No commit/push/cloud deployment or new remote DDL. The user's finite live-call authorization supersedes the earlier fixed-budget smoke gate; privacy, consent and SQL approval still apply.

Current evidence:

- Actual gpt-6-luna, Agents SDK0.24.0/OpenAI3.37.0, Responses structured output and function calls.180dataset outputs across baseline/A/B; no schema failures. Selection preceded heldout; score4.3525→4.6375/5 on20heldout cases. Same-model judge/order checks and agent inspection are not independent human calibration. [Evaluation](live-ai/final-evaluation.md), [comparison](live-ai/comparison-results.json).
- 283inference attempts including72judge/2TTS/2STT. Known text:255,939input/74,618output,3,861cached; estimated$0.06255541 excluding audio and3unknown cancelled/timeout attempts. No retries; store=false, tracing off, no fake fallback. [Usage](live-ai/performance-usage.json).
- Five bots, three existing tools, selected mood statistics without notes, memory proposal/explicit approval/peer denial, ten-turn recall/correction, reload and bot isolation. Real cancellation/idempotency/revoke suppress final output. Four distinct live browser tests passed across three runs. [Tools](live-ai/tool-calling-results.json), [context](live-ai/multi-turn-results.json), [safety](live-ai/safety-regressions.json).
- Vietnamese STT passed standalone and through authenticated browser upload/preview/edit/explicit send using a synthetic MediaStream. Native Chromium getUserMedia returned NotSupportedError in an isolated probe; physical mic/mobile Safari/device matrix remain unverified. [Voice](live-ai/voice-browser-results.json).
- 175backend tests; Ruff all backend; mypy47source files;85frontend units; typechecked build;18API browser;15legacy browser;6real local full-stack tests PASS. Markdown active-content denial and draft restoration have regressions. [Checks](live-ai/test-evidence.json).
- Optional durable usage/price snapshots, idempotent settlement and45sworker leases implemented/rehearsed locally. Request starts persist before model work; unknown usage is retained; expired recovery never replays provider calls. Cleanup continues when capture is off. Local0006/RLS rehearsal PASS. [Evidence](live-ai/accounting-local-verification.json).
- Prior approved Supabase initialization/runtime/Auth/core/scoped-tool proofs remain valid in their recorded scopes. Remote schema remains0005; runtime has no admin/BYPASSRLS/CREATE/raw Auth. [Initialization](supabase-migration-execution.json), [runtime](supabase-runtime-verification.json), [hosted core](supabase-e2e-checkpoints.json).

Remaining release gates:

1. **Separate approval for new accounting DDL:** [0006 SQL](live-ai/0006-ai-usage-review.sql), SHA256 `7119b1d9cd6e2d1a58df9c830dc950210b8c66499b3ee24d6d8e6bb402b78b22`. Verify new-table ACL/RLS/runtime before enabling capture. Old SQL approvals do not apply; accounting stays off against hosted0005.
2. **Q02/Q05/P07.03/P08.03:** provider account/project region, retention, deletion, backups/restore and full account deletion remain unverified. store=false does not prove ZDR. Synthetic authorization does not approve private-user rollout.
3. **P02.02/P02.03:** local accounting tests do not qualify shared RAM conversations, distributed fault/reconciliation schedules or a production billing service. Use one application worker. No monetary cap/allocation was invented for this unlimited-budget evaluation.
4. **P08.02:** independent human calibration and a larger untouched future dataset remain. Do not tune on the opened heldout. Mây retained baseline; Rủ Rê heldout was effectively flat.
5. **P07.02/P07.04/P08.04:** physical mic/mobile Safari/manual assistive technology/touch, full state/device matrix and load/SLA remain unproven. Foreground-midnight Nhịp picker bounds can require refresh; backend rejects expired dates.
6. Q07 report staffing, hosted CI, restore/tombstone/drain drills and earlier leaked-password-protection warning remain separate. Signup/SMTP/recovery were outside scope.

The agent did not edit .env; final inspection observed AI_ENABLED=true, STT=false and accounting=false. The live test server explicitly forces global AI off and uses its synthetic allowlist. [Local live commands](live-ai/README.md) use a development-only synthetic actor allowlist and ordinary auth/age/consent. No private mood/chat/memory was added to matching; scores, identity and invitations remain deterministic domain responsibilities.
