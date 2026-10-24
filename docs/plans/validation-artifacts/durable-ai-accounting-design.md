# Durable AI accounting: schema gap and next implementation boundary

Status: design only; no accounting DDL, budget allocation or live provider call performed.

Current Alembic head remains `0005_export_scope`. `ai_runs` has identity, owner,
conversation, bot, status, version and creation timestamp. It has no usage, price,
reservation or worker-lease fields. The model/tool/30s limits in `ai/provider.py`
are per-run limits; they do not prove a durable monetary budget.

Do not encode billing records in `outbox.resource_id`, reuse consent versions as
money, or modify the already approved initialization/runtime-role SQL. A separate
expand migration and complete SQL review are required before remote execution.

The next slice should implement and rehearse these together:

1. A budget ledger for UTC-day global and per-user limits, spent and reserved
   integer nano-USD. Zero or missing allocation denies a live request. Runtime
   can consume counters; setting positive limits requires an operator decision.
2. One reservation per `AiRun.id`, model and immutable pricing version/rates,
   cumulative SDK request/input/cached/output counts, accounting state and
   timestamps. No prompts, responses, memory, notes, email or provider tokens.
   Use exact integer/Decimal arithmetic; cached input cannot exceed total input.
3. In the same transaction as run acceptance, lock global then user budget and
   reserve a conservative bound for at most three model calls and bounded input
   plus output. A duplicate client intent must reuse the reservation.
4. Persist call-start before the provider request; persist cumulative usage from
   SDK hooks. Terminal settlement must be idempotent under competing writers.
   A cancelled request with unknown provider usage keeps its reservation and is
   marked uncertain; it must not become a zero-cost refund or automatic replay.
5. Recovery reconciles metadata only. A provider receipt can settle uncertain
   usage; output/transcript is never reconstructed from PostgreSQL. Actual cost
   above the reservation must still be recorded and block further allocations.
6. Test simultaneous allocation, retry/duplicate settlement, cancellation at
   every await, process death before/after call-start, unavailable DB, owner
   isolation, role grants/RLS and deletion/retention of identifiers. Then export
   exact incremental Alembic SQL and obtain approval for that content/hash.

New implementation and SQL are not yet ready for approval. No schema change or
monetary reservation is claimed by the current evidence. Live AI/STT remains
disabled pending provider/account privacy verification and an explicit budget.

Independent recovery hardening completed now: durable run status is checked
before model/tool work, completion requires a successful database compare-and-set,
terminal writers preserve the first committed outcome, and purged metadata is
not recreated. Ten regression cases reproduce stale output/tool/finalization
schedules and reserve input/output RAM across their commits; this does not constitute
monetary accounting or multi-worker lease fencing. Startup still
assumes one worker and its orphan update must be replaced or fenced before
multiple workers can serve AI.
