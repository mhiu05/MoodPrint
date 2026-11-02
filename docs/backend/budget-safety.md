# Bounded AI liability for the demo

With `AI_ACCOUNTING_ENABLED=true` and `AI_DAILY_BUDGET_USD=20`, every registered
model run reserves $2 in the existing `ai_usage` ledger before dispatch. Parent
chat/group runs and each planner, selector, specialist, handoff and group speaker
have separate reservations. The shared admission advisory lock serializes the
liability check and insertion across API/worker processes. Values above $20 are
clamped to $20 for financial reservations. Missing accounting, model prices or
relevant historical cost records deny admission.

This is a conservative **application liability cap**, not an exact provider
invoice guarantee. It covers these accounted model calls with the documented
prices and request limits, not taxes, other applications, STT, embeddings or
separately funded guest calls. Keep `GUEST_PAID_ENABLED=false`,
`GUEST_SEMANTIC_ENABLED=false`, STT and semantic embedding dispatch off for this
demo. Publishing the change does not authorize broad rollout or worker enablement.

The supported model is exactly `gpt-6-luna`. Its published maximum input is
922,000 tokens. Every ledger row is bounded to at most three provider requests,
each with at most 1,200 output tokens, and SDK/HTTP retries are zero. Conservative
rates stack long-context, cache-write, regional and Fast premiums: 550 nano-USD
per input or cached token and 1,650 per output token. The maximum is
`3 * (922000 * 550 + 1200 * 1650) = 1,527,240,000` nano-USD, rounded up to $2.
Settled usage uses those conservative rates too. Production model overrides
that differ from the accounted model, including custom model objects, are denied.
Synthetic model objects remain available only in `APP_ENV=test`.

Sources verified 2026-11-02: [model limits and pricing modifiers](https://developers.openai.com/api/docs/models/gpt-6-luna)
and [September 2026 pricing announcement](https://developers.openai.com/api/docs/changelog).
Reverify these assumptions before changing model, token limits, retries or pricing.

While a row is open, partial snapshots never release its envelope. Terminal
complete usage settles at conservative cost. A missing/zero-usage response does
not count as financially known; cancellation, timeout or unknown outcome retains
the envelope as uncertain. Restart recovery releases only a definite zero-dispatch
reservation; it never replays a provider call. No automatic refund is inferred for
uncertain work.

The UTC financial day includes the complete previous UTC day's ledger, so turns
crossing midnight do not reopen their budget. Open/uncertain rows also carry
across later days while retained by the existing 90-day metadata policy. This
deliberately reduces usable capacity and repeated uncertain outcomes can close
AI until operators reconcile them. Historical standard-price settled rows are
revalued conservatively when checking the cap; unknown historical rows require
review rather than silently counting as free.

Proactive runs and descendants use `PROACTIVE_BUDGET_SHARE` of the same ceiling.
For example, share `0.5` limits their next reservation to the first $10 of total
liability; interactive work may use the remaining ceiling. A small share can stop
proactive work early because the full $2 must fit before dispatch. This financial
headroom does not implement queue preemption or guarantee interactive latency.

Account deletion still purges private journal/chat data and revokes identity.
Relevant financial usage and its content-free run/ancestor anchors remain linked
to the existing deleted-user tombstone until normal metadata retention, so
deletion cannot reopen the budget. These anchors contain identifiers, timing and
token/cost metadata; they are not anonymous records or journal content.

Validation includes independent PostgreSQL sessions competing for a $20 cap,
child/proactive admissions, unknown history/models, partial and terminal snapshots,
crash recovery, midnight carryover and account deletion. Schema head remains 0024;
no migration or production data rewrite is required.
