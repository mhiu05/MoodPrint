# Paid staging campaign: cumulative USD 3 guard

Status: **OFFLINE CONTROLLER VERIFIED; LIVE CAMPAIGN NOT RUN.** Account-specific
pricing, project RPM/TPM, effective staging configuration and exact input-count
contract remain unverified. No live ledger, API generation, judge call, cloud
change or runtime activation was performed for this work.

## What is implemented

`scripts/paid_campaign.py` is a separate, single-host campaign ledger. Cooperating
processes must use the same canonical SQLite file on a durable local filesystem.
`BEGIN IMMEDIATE` serializes reservation and dispatch claims; `synchronous=FULL`
and commit-before-transport persist the hold before caller-owned code can send.
No application accounting or runtime flags are changed.

Each **physical attempt** needs a unique sanitized ID and a committed reservation.
The ledger has a fixed cumulative USD 3 cap, with no daily reset and no configurable
increase. USD uses decimal strings and exact `Decimal` arithmetic. Floats, negative
or nonfinite prices, excessive precision, missing proof and expired attestations
are rejected. The input bound is at most 64,000 tokens; output at most 1,200.
Reservation is `(input_bound * max(input_rate, cache_write_rate) + output_bound *
output_rate) / 1,000,000`. Rates must be conservative **account-specific upper
bounds** for the exact processing tier, region and cache policy.

Every reservation stays charged against the campaign cap permanently, including
completed calls with smaller known actuals, zero-cost calls, cancellation,
timeouts, unknown outcomes and process death. There is intentionally no refund or
release API. A retry must reserve again under a new ID. Duplicate reservation or
dispatch fails closed. A process killed after dispatch claim leaves `dispatching`
held indefinitely; do not replay it. A known actual larger than its reservation
is persisted and freezes all future reservation/dispatch. This is an accounting
alarm, not a way to reverse provider spend already incurred.

The only CLI command is status; it never contacts a provider:

```powershell
backend/.venv/Scripts/python.exe scripts/paid_campaign.py status <canonical-ledger-path>
```

`Campaign.create(path, attestation)` refuses existing paths; `Campaign.open(path)`
refuses missing, uninitialized or corrupt ledgers. `reserve`, `dispatch`, `cancel`
and `record_actual` are the Python integration points. `dispatch` supplies fixed
`model=gpt-6-luna`, `service_tier=default`, `store=false` and the reserved output
limit to an injected transport exactly once. There is no OpenAI client, API key
lookup, runnable live adapter, automatic retry or API-based judge here.

## Preconditions for any later live adapter

The attestation requires staging, USD, `gpt-6-luna`, a nonempty immutable pricing
version, positive input/cache-write/output maximum rates as decimal strings,
`model_access_verified=true`, `account_pricing_verified=true`,
`quota_verified=true`, positive integer `rpm`/`tpm`, a SHA-256 of sanitized account
evidence, and an unexpired timezone-aware `expires_at`. The controller validates
these fields; **it does not authenticate the evidence or turn operator assertions
into verified account facts**. Keep a reviewed evidence artifact and identity of
the exact account/project with the operational record. No real attestation has
been created or accepted in this task; test attestations are synthetic.

Before implementing or enabling a live adapter, establish all of the following:

1. Read-only account/project evidence proves Luna access, actual tier/region/cache
   pricing, quota and available spend. A successful model metadata GET proves
   neither generation access nor RPM/TPM/pricing. Public price tables alone do
   not establish the account contract.
2. Bind each reservation to the final immutable serialized request and prove its
   input bound with the supported exact-count contract. Count endpoint semantics
   and any charge must be known. Any paid count/preflight call also needs a
   reservation; if its cost cannot be bounded, stop before calling it.
3. The reviewed adapter must send exactly one physical request per dispatch,
   disable SDK/HTTP retries and redirects/fallbacks, preserve the forced Luna
   model/output/service tier, and reject tools, hosted state, files, images,
   multimodal input, uncounted history and all additional paid operations. The
   current injected callback is trusted and cannot enforce these restrictions.
4. Use the same durable ledger for the **whole campaign**, across canaries,
   retries, workers and restarts. No second ledger, deletion, restored older
   snapshot, day reset, or new campaign ID can supply extra allowance. A missing
   or damaged ledger requires reconciliation from durable backup, never an empty
   replacement. SQLite does not establish a cap across hosts or independent files;
   a distributed campaign needs a shared transaction authority first.
5. Enforce measured RPM/TPM outside this ledger; its positive quota fields are
   admission prerequisites, not a rate limiter. Verify effective staging flags,
   account identity, output/reasoning billing and no alternate egress. Preserve
   rollback compatibility and existing open application liabilities.
6. Start with one bounded physical canary after these prerequisites are proven;
   stop on ambiguous billing, counts or transport behavior. Evaluate saved,
   sanitized outputs with deterministic checks and human/offline scoring. No
   paid evaluator or judge model may run.

This controller therefore proves durable **reservation authority for the bounded
attempts routed through it**, not an end-to-end provider-spend hard cap for an
unverified callback. The absence of a live adapter is deliberate while those
prerequisites are unresolved. This addition does not close G09 or authorize
turning on paid traffic.

## Official OpenAI documentation checked 2026-11-05

The [official Luna model page](https://developers.openai.com/api/docs/models/gpt-6-luna)
identifies the model and documents context/tier/region pricing modifiers. The
[official API pricing table](https://developers.openai.com/api/docs/pricing) lists
short-context Standard Luna rates per million tokens: input USD 0.10, output USD
0.50, cached input USD 0.01, 30-minute write USD 0.125 and 12-hour write USD 0.25.
These are documentation observations, not the selected account's verified rate
card. Using only the 30-minute write price would not cover a 12-hour write policy.
The controller embeds no public price default and requires a reviewed maximum.

## Verification and remaining application blockers

Offline tests use synthetic prices and account attestations; they never import an
API client or contact a provider. Tests cover exact cumulative exhaustion after
successful cheaper calls/reopen, refusal of invalid/unverified/expired
preconditions, request bounds, duplicate holds/dispatch, unknown outcomes,
cancel/retry without refund, freeze on actual overrun, subprocess hard death,
12 competing processes admitting only three USD 1 reservations, corruption and
read-only status output. See
[campaign evidence](evidence/round2-campaign-summary.json) and
[test log](evidence/round2-campaign-tests.txt).

Application-wide workflow pooled allocation is still not implemented. Existing
per-row conservative holds must not be described as pooled accounting. Voyage
embedding/STT and other registered provider costs are not integrated into one
all-provider budget authority; client reuse and measured external quotas remain
separate work. App retry/multi-call/fanout/guest/background/rollback behavior must
be proved across their actual transports and ledger paths. This SQLite campaign
module does not replace Postgres accounting, change the global app budget, prove
50-user production capacity, or close deployment/configuration/quality gates.
Keep the bounded/dispatch activation flags off until those gates are met.
