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
prices and request limits, not taxes, other applications, STT or embeddings.
Owner-approved guest AI now shares this $20 ceiling with a guest subset of at
most $5; it is not an additional $5 budget. Keep `GUEST_SEMANTIC_ENABLED=false`,
STT and semantic embedding dispatch off. Publishing the change does not
authorize broad rollout or worker enablement.

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

## Guest AI subset

After hosted CAPTCHA/anonymous-auth and cleanup prerequisites pass, configure
`GUEST_AUTH_ENABLED=true`, `GUEST_PAID_ENABLED=true`, `GUEST_DAILY_BUDGET_USD=5`,
`GUEST_AI_TURNS=50`, `GUEST_AI_CONCURRENCY=1` and
`GUEST_AI_GLOBAL_CONCURRENCY=2`, alongside the global $20/accounting settings.
Use this server-only price mapping; there is deliberately no voice/embed price:

```json
{"ai":{"pricing_version":"openai-conservative-2026-11-02-v1","input_nano_per_token":550,"cached_nano_per_token":550,"output_nano_per_token":1650,"max_input_tokens":922000}}
```

Each guest turn reserves `1,527,240,000` nano-USD in the existing detached guest
ledger. Global liability is registered usage plus detached guest spent/reserved
totals. Guest `ai_usage` rows are diagnostic metadata and are excluded from the
global sum, so they do not count twice. A guest usage row requires its live,
owner-linked detached reservation before it can be inserted. The guest subset
also uses conservative carryover across the UTC day boundary. Existing Bangkok
civil-day rows remain unchanged; any Bangkok day overlapping the global window
is included. Three simultaneous full guest envelopes fit the $5 subset; a
fourth is refused before provider dispatch. Known final usage releases the
difference, while missing/partial usage retains the full envelope.

Guest financial admission takes the same global advisory lock before any guest
day/reservation lock. Purging a guest removes user-linked metadata but retains
detached totals. Uncertain detached reservations are retained rather than aged
out after 24 hours; they keep their day and liability until operator review.
Any halted guest day blocks global paid admissions too. Legacy unpriced guest
usage denies admission; purge records a detached halted marker before removing
its identity, so cleanup cannot make unknown charges disappear. The verified
hosted first-enable preflight had zero guest financial rows; no price/ledger
reconciliation write was performed or inferred.

Guest paid readiness rejects unknown models, insufficient model input/rate bounds,
unapproved pricing versions and a guest budget above $5. In capped mode guest
voice/embed are unavailable even if somebody adds prices; production guest paid
work also requires a positive global cap. These checks do not replace provider
authentication/CAPTCHA readiness or the immutable two-hour guest lifetime.
