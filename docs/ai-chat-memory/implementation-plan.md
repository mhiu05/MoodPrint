# AI chat and memory implementation ledger

Scope: implement the attached production AI Chat & Memory request in the existing modular monolith. No commits, deployment, `.gitignore` changes, or production writes. Work in the requested existing checkout, preserving initial user changes. The user explicitly delegates technical choices and opts out of design approval questions.

## Design decisions

- PostgreSQL is authoritative for opted-in conversations, delivery state and pending proposals. Existing RAM chat remains the privacy-preserving default.
- A new versioned `ai_preferences` resource separately controls `historyEnabled` and `semanticMemoryEnabled`; both default false. Version `ai-data-v1`. History retention defaults 30 days, maximum 90; no copying old ephemeral content into durable storage.
- Existing AI/MEM consent still gates every model/memory use. Stored data remains manageable with AI disabled. Disabling history stops new persistence and cancels active turns; existing history remains viewable/exportable/deletable until expiry.
- Existing Agents SDK runtime remains the only runtime. Short database transactions reserve durable turn slots, enforce account/global admission and fence completion. Provider calls do not hold database transactions.
- Embeddings derive only from active approved memories, source/current version and explicit external-processing opt-in. Voyage `voyage-4-lite`, 1024 default dimensions, cosine; configuration controls compatibility. Exact scoped nearest-neighbor query is adequate at this scale; no approximate index until measured necessary.
- One PostgreSQL embedding job per memory/version/config, bounded retry/backoff and expiring lease. An old worker cannot publish against changed memory/consent/source.
- Multi-worker SSE reads durable turn status and committed assistant content; raw unfinished model output is never published. Stale turns become interrupted, never silently replayed.
- Supabase project roznanxbiyqybjpvtilq matches existing repository deployment evidence. No identifiable development branch exists; treat hosted database as production and inspect read-only. Local disposable PostgreSQL proves migrations and synthetic workloads.

## Tasks and ownership

1. Root: durable chat models, preference API, persistence service, routes/runtime integration, leases/admission, recovery, retention/deletion/export, migration 0007_chat_history, regression/security/load tests and integration.
2. Memory implementer: durable proposals + lifecycle routes in new `app/ai/memory.py`, models in `memory_models.py`, migration 0008_memory_proposals; runtime tool integration via callable helper. Do not edit runtime/routes/main or chat models.
3. Embedding implementer: Voyage adapter, derived models/jobs/retrieval, config in separate settings mixin if needed, migration 0009_memory_embeddings; tests and configuration documentation. Do not edit runtime/main/routes/config or memory models. Root connects hooks.
4. Frontend implementer: real conversation sidebar/history resume/pagination/export/delete/preferences and proposal states using documented API contract; preserve UI identity, browser tests. Frontend only.
5. Root: integration, lint/mypy/TypeScript/build, all backend/frontend tests, real database migration check, fullstack desktop/mobile/browser, synthetic workload up to 50 actors, final review and requested documentation.

## Shared interfaces

- GET/PUT `/ai/preferences`: `{historyEnabled, semanticMemoryEnabled, version, policyVersion, retentionDays, historyAvailable, semanticMemoryAvailable}`. PUT `{historyEnabled, semanticMemoryEnabled, expectedVersion, policyVersion: 'ai-data-v1'}`.
- GET `/ai/conversations?limit=30&before=<UUID>&botId=may` retains array response; headers add `persistent`, `title`, `createdAt`, `updatedAt`. GET `/ai/conversations/{id}?limit=50&before=<UUID>` returns existing view plus `hasMoreMessages`; messages add `createdAt`, `status`, `runId` where useful. Last page is chronological, older loaded via before first message ID.
- POST conversations adds `persistent: bool | null`; null selects preference, true requires current opt-in. POST messages retains existing body/idempotency contract. DELETE conversation removes history; POST end remains compatible. GET `/ai/conversations/{id}/export` downloads owner-only JSON.
- Memory helper `create_proposal(db, actor, bot_id, text, purpose, data_version, source_id=None, source_version=None)` returns DB proposal. API proposal DTO adds `status`, `expiresAt`; no model approval tool. Root removes old memory endpoints and includes new router.
- Embeddings expose `enqueue_memory(db, memory, settings)`, `invalidate_memory(db, memory_id)`, `retrieve_memories(database, settings, actor, bot_id, query, data_version) -> list[str]`, `process_embedding_jobs(database, settings, provider=None)`. Preference model import `app.ai.models.AiPreference`, fields user_id/history_enabled/semantic_memory_enabled/policy_version/version. Root wires actual signatures after agent reports.

## Baseline and progress

- Initial git: modified .gitignore and untracked existing live AI screenshot/evidence paths; preserve all.
- Backend baseline ruff and mypy pass. Unit run lacks TEST_DATABASE_URL initially; database tests explicitly skip. Frontend baseline typecheck and 85 unit tests pass; build running.
- Hosted DB at revision 0005_export_scope, RLS enabled on private tables, pgvector available 0.8.2 but not enabled; no hosted writes performed.
- Tasks in progress; append actual verification and rulings below.

## Continuation session reconciliation (2026-10-24)

The interrupted session left all work in the main working tree (no other worktrees, branches or stashes). Reconciled state and changes made while resuming; the final summary and verified evidence are in [README.md](README.md).

- Found incomplete: embedding worker observability (test existed, logging absent: 1 failing test in the baseline of 213); ruff import order in `alembic/env.py`; CI Postgres image lacked pgvector, so migration 0009 and the test fixture could not run in CI.
- Defects fixed: sibling proposals became `STALE_VERSION` after any approval or unrelated data revision (validity now uses consent versions stored on the proposal; 0008 changed before any non-disposable deployment); legacy `POST /end` deleted saved history; AI/MEM withdrawal left unusable vectors and pending previews behind; "new conversation" could wipe a draft typed right after the click (router transition race).
- Added: conversation rename (`PATCH`), history grouped by assistant, pending-proposal link in chat, memory delete confirmation, load-harness coverage for pagination/rename/delete, pinned cross-worker cancellation, MEM/AI revocation and real worker crash-kill, CI migration and load smoke steps.
- Not re-verified: `voyage-live.json` (a live Voyage call recorded by the earlier session). No live provider call was made in the continuation session.
