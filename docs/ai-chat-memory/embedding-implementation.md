# Approved memory embeddings

> Continuation note (2026-10-24): AI/MEM consent changes now also delete derived vectors and cancel jobs (`discard_user_index`), and the worker logs content-free `embedding_job_attempt` and `embedding_queue_state` lines. See [README.md](README.md).

Implemented in `backend/app/ai/{embedding_config,embedding_models,embeddings,voyage}.py`, migration `0009_memory_embeddings`, and `backend/tests/test_embeddings.py`.

## Provider and storage decisions

Official [Voyage embeddings documentation](https://docs.voyageai.com/docs/embeddings) and [HTTP reference](https://docs.voyageai.com/reference/embeddings-api), checked 2026-10-24, list `voyage-4-lite` with default 1024 dimensions and supported 256/512/1024/2048 outputs. The adapter uses existing `httpx`, the fixed HTTPS endpoint, float output, explicit `document`/`query` input type, bounded timeout, and no automatic HTTP retries. It validates vector length, numeric finite components and nonzero magnitude; stored errors are controlled codes without user text, response bodies or credentials.

Official [pgvector documentation](https://github.com/pgvector/pgvector) specifies exact nearest-neighbor search and cosine distance (`<=>`). The implementation stores `extensions.vector` with a matching dimensions check and uses exact search. No approximate vector index or extra Python dependency is introduced. The extension must already be available to the local/hosted PostgreSQL installation; migration refuses an existing vector extension installed in a different schema rather than moving it implicitly.

Both new tables are private `moodprint` tables with RLS enabled, public/Supabase client grants revoked, and the existing trusted backend role policy. Vectors reference memories with cascading deletion. Jobs contain identifiers and version/configuration metadata, never memory text or chat transcripts.

## Authorization and lifecycle

- External indexing requires the deployment capability, a provider key, explicit current `ai-data-v1` semantic preference, current `v1` AI+MEM consents, an eligible active account, and an active approved memory with an unchanged confirmed source owned by that account. Only `may`, `guong`, `nhip`, `rure` are eligible. `caunoi`, mood records and transcripts are never indexed.
- Unique jobs identify memory/version/model/dimensions and preference/AI/MEM consent versions. A bounded reconciliation query discovers eligible missing snapshots, so old memories and model/dimension changes are indexed without an unbounded request or a first-page starvation loop.
- Global `User.data_version` is recorded for provenance and checked on each retrieval run. It is deliberately excluded from job uniqueness and vector eligibility: an unrelated mood/profile update must not resend every unchanged memory to an external provider. Memory versions, source versions, current consent versions and semantic preference versions determine vector validity.
- A worker claims jobs with `FOR UPDATE SKIP LOCKED`, increments attempts, commits an expiring UUID lease, validates the owner/current snapshot in a second short transaction, calls the provider outside transactions, and then rechecks snapshot, source, lease token and expiry before publication. Owner-to-job locking order is consistent with lifecycle mutation hooks. An old worker cannot publish after a new claim or invalidation.
- Controlled failures retry after 5, 10, 20... seconds, capped at an hour, within the configured attempt ceiling. Exhausted jobs remain terminal and do not block discovery of other memories. Cancelled jobs can be revived only when their exact current snapshot becomes eligible again. There is no automatic reset of failed attempts.
- `invalidate_memory` deletes derived vectors and cancels pending/running/retry jobs in the caller's mutation transaction. Independently, every retrieval joins the current memory/source and verifies consent/preferences; immediate exclusion does not depend on maintenance cleanup.

## Retrieval and fallback

`retrieve_memories(database, settings, actor, bot_id, query, data_version)` first validates the real session/owner and AI+MEM gates. It makes no external query call unless the actor opted in and at least one eligible vector exists for this bot, model and dimensions. After the provider returns it repeats session/consent/version authorization. The SQL scopes tenant, bot, memory version, confirmed source, configuration and permission versions before applying cosine threshold, ordering and top-k. Context is limited by both memory count and characters.

Missing capability/opt-in, absent compatible vectors, or provider failure uses a bounded selection of actual current approved memory text. Unicode-normalized Vietnamese token overlap ranks the fallback; ties preserve revision and stable-ID order. The existing memory model has no creation timestamp, so this is not presented as chronological recency. Semantic results below the threshold are omitted; an empty semantic result does not fabricate facts or replace the result with unrelated text.

The synthetic Vietnamese fixture `backend/tests/fixtures/memory_retrieval_vi.json` supplies five approved topics and five paraphrased queries with independently assigned topic vectors. It verifies database retrieval, threshold behavior and context content. It is **not** a live Voyage relevance benchmark, and no empirical multilingual accuracy or provider latency/cost claim follows from it.

## Configuration

All are backend environment variables. The root settings class inherits `EmbeddingSettings`; API preferences remain a separate per-user opt-in.

| Variable | Default | Purpose |
| --- | --- | --- |
| `SEMANTIC_MEMORY_ENABLED` | `false` | Deployment capability gate |
| `VOYAGE_API_KEY` | empty | Server-side provider secret |
| `VOYAGE_MODEL` | `voyage-4-lite` | Versioned compatibility scope |
| `VOYAGE_DIMENSIONS` | `1024` | Supported 256/512/1024/2048; numeric dotenv strings parsed before validation |
| `VOYAGE_TIMEOUT_SECONDS` | `10` | Provider timeout, 1–30 seconds |
| `EMBEDDING_JOB_BATCH_SIZE` | `10` | Reconciliation and processing limit per worker tick, 1–50 |
| `EMBEDDING_MAX_ATTEMPTS` | `4` | Maximum total provider attempts, 1–8 |
| `EMBEDDING_LEASE_SECONDS` | `60` | Lease lifetime, 35–600 seconds |
| `MEMORY_RETRIEVAL_LIMIT` | `6` | Context top-k, at most 10 |
| `MEMORY_FALLBACK_LIMIT` | `100` | Maximum lexical candidates, 10–500 |
| `MEMORY_SIMILARITY_THRESHOLD` | `0.3` | Minimum cosine similarity |
| `MEMORY_CONTEXT_CHAR_LIMIT` | `1200` | Maximum returned memory characters, 120–4000 |

Call `process_embedding_jobs` from the application's maintenance loop. It also runs bounded reconciliation, so each web request does not perform bulk indexing. Configuration changes select a separate compatibility scope and trigger bounded new indexing; they can incur new provider calls. Do not enable against production until provider/privacy settings and deployment migration are reviewed under the project workflow.

## Observed validation

Only disposable local PostgreSQL databases on `127.0.0.1:16432` were written. No paid provider call or hosted database mutation was performed. Existing `.gitignore` changes were preserved.

| Scope | Command actually executed | Observed result |
| --- | --- | --- |
| Adapter/settings/queue/retrieval | `uv run --locked pytest -q tests/test_embeddings.py` | Initial tests failed for absent feature; subsequent 21-test run passed before vector-reflection, Vietnamese fixture and dotenv regressions were added. Final expanded run recorded below. |
| Static checks | `uv run --locked ruff check app/ai/embedding_config.py app/ai/embedding_models.py app/ai/embeddings.py app/ai/voyage.py tests/test_embeddings.py` | Pass |
| Type checks | `uv run --locked mypy app/ai/embedding_config.py app/ai/embedding_models.py app/ai/embeddings.py app/ai/voyage.py` | Pass, four source files |
| Fresh migration | `uv run --locked alembic upgrade head` using local `moodprint_embedding_migration_test` | Pass through `0009_memory_embeddings` |
| Schema parity | `uv run --locked alembic check` on that database | No new upgrade operations; vector reflection warning reproduced, regression added, then fixed and check rerun clean |
| Database security metadata | Local `psql` reads of `pg_class`, `pg_extension`, `moodprint.alembic_version` | Both embedding tables RLS enabled; vector in extensions schema; revision 0009 |
| Dotenv integration failure | `uv run --locked pytest -q -x` | Initially 2 passed / 1 error from integer Literal dotenv parsing; reproduced with dedicated red test and fixed |
| Dotenv regression | `uv run --locked pytest -q tests/test_embeddings.py -k 'dimensions_from_environment or environment_dimensions'` | 2 passed |
| Actual settings construction | `uv run --locked python -c "from app.core.config import Settings; Settings(); print('Settings valid')"` | Settings valid, no values printed |

Coverage includes malformed/zero/nonfinite vectors, sanitized provider errors, duplicate jobs, source ownership/currentness, cross-tenant and bot separation with real foreign vectors, incompatible dimensions, semantic opt-in, MEM revocation during query, edits during indexing, lease fencing, concurrent workers, bounded retry/backoff/exhaustion, cancelled configuration recovery, unrelated data revisions, bounded reconciliation progress and Vietnamese lexical ranking.

Remaining limits: actual Voyage availability, multilingual ranking quality, network latency, usage/billing, hosted migration privileges and production scheduling are untested. Those checks require an explicitly authorized live-provider/production validation. Root integration verifies runtime hooks, maintenance scheduling and browser journeys.
