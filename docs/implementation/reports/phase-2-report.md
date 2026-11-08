# Phase 2 report

Status: **NOT VERIFIED**. Retrieval quality is **UNMEASURED**. Voyage calls are **BLOCKED**.

The branch is `feat/knowledge-base`. Work started from `origin/feat/knowledge-base` at `fc84d1fa` (pre-branch readiness merged). Tags `baseline/phase-2-3-start` and `baseline/phase-2-3-start-rc2` are not on the remote. `baseline/phase-2-3-start-rc1` is an ancestor. The owner asked to continue from this provisional branch while the two-stack pre-branch gate is still outstanding.

## D2 acceptance

| ID | Status | Evidence |
|---|---|---|
| D2-01 | BLOCKED | No Voyage key and no `.local/eval-budget.json`. No live ingest. |
| D2-02 | NOT RUN | `kb` stack was not started. `foundation` and `ag` were already running; a third stack was not added. |
| D2-03 | BLOCKED | Same as D2-01. Hashing vectors are 1024-d and L2-normalized in unit tests only. |
| D2-04 | PARTIAL | Retriever and contract-shaped code exist. Contract tests against Postgres were not run. |
| D2-05 | NOT RUN | `verify-citations` was not executed on a published corpus. |
| D2-06 | PARTIAL | Hub calls the live adapter outside Vitest. Real E2E was not run. |
| D2-07 | UNMEASURED | No Voyage holdout run. |
| D2-08 | PARTIAL | Offline unit tests were run. pgTAP, integration, and E2E were not. |
| D2-09 | NOT RUN | Security tests that need the database were not run. |
| D2-10 | PENDING | Ownership and CI to be recorded on the pushed SHA. |
| D2-11 | PARTIAL | This report. It does not claim `PHASE_2 = VERIFIED`. |

## Environment

- Stack `kb` (offset 100, DB 54422) was **not** started.
- Running stacks left untouched: `moodprint-foundation` and `moodprint-ag`.
- No `.env.live` and no budget file. No Voyage or OpenAI call was made.

## Sources

Thirteen sources are registered. One is `authored` (`mp-authored`). Four are `reference_only` (UNICEF, WHO, Tổng đài 111, Bộ GD&ĐT). Eight stay `unverified` because the official text or licence was not opened (HTTP 403 or secondary-only CC BY-SA). None of those eight have an acquire block. There is no verified `open_reuse` source, so the “at least six reusable sources” target is **not met**. Authored cards cite the reference sources and do not copy their pages.

Known gap: Vietnamese legal instruments (Nghị định 80/2017/NĐ-CP, Thông tư 06/2019/TT-BGDĐT, Thông tư 38/2019, Luật Trẻ em 2016) and StopBullying.gov were not ingested.

## Corpus

`build` of `agent/ingestion/corpus/manifest.toml` produced 51 documents and 726 chunks. Scenario and quiz articles from the static library are excluded. Guide, FAQ, checklist, and template articles are kept as authored cards with their legacy ids. Chunk lengths in that build: min 102, max 692, 44 chunks under 200 characters. Those short chunks are marked `short`.

`manifest_sha256` from the plan command in this session: `324a2c4d7f0f57de367ccc4a6e3f198793597a580268d72b2a6fa46215f1a0bb`.

Synthetic contract corpus: `agent/ingestion/synthetic/contract_corpus.json`, version `kb-20261108-01`. It includes a `support` document for the frozen retriever contract, a cyberbullying message document for the Hub query, and a prompt-injection trap stored as data.

## Schema

Migration: `supabase/migrations/20261108190000_kb_schema.sql`.

`knowledge.f_unaccent` and `knowledge.search_chunks` are not SQL functions. The frozen migration checker rejects `CREATE TABLE ... AS` (the word `as` inside generated columns) and rejects non-allowlisted calls inside function bodies, including `translate` and `to_tsvector`. `heading_norm` and `fts` are ordinary columns filled at insert time with the same Python fold (`lower` → NFD → drop Vietnamese combining marks → `đ` to `d`). `licence_note` is in `knowledge.source_confidential` (`moodprint:private_ingestion`) because table-level `SELECT` is required by the frozen grant test and cannot hide one column.

pgTAP files: `supabase/tests/kb_00_schema.sql`, `supabase/tests/kb_01_rls_grants.sql`. They were not executed here.

## Retrieval

Default `KnowledgeConfig.retriever` remains `fixture`. `pgvector` is wired in `build_knowledge_retriever` and requires `VOYAGE_API_KEY`. Missing key raises `ValueError`. E2E uses `build_e2e_retriever` with `HashingEmbedder`. Provisional gates: `min_vector_score=0.55`, `min_lexical_score=0.01`, `rrf_k=50`. These are not tuned on a Voyage dev split.

Hybrid search is vector distance plus accent-folded `simple` FTS, fused with RRF in Python. Empty or off-topic queries are meant to return `no_results` rather than fixture text.

## Benchmark

Targets Recall@5 ≥ 0.80, no-result accuracy ≥ 0.90, and citation integrity 100% are **UNMEASURED**. No holdout run was performed. Hashing metrics are not reported as quality.

## API and Hub

Authenticated routes: `GET /v1/knowledge/search`, `/documents/{documentId}`, `/sources`, `/corpus`. Timeouts and unavailable retrieval map to `502 upstream_error`. The Hub shows “Tra cứu từ nguồn” only when the live adapter is present. Vitest still sees `knowledgeSearch === null` because the pre-branch composition test requires that, and that test file is outside Phase 2 ownership. The Vite app, including Playwright `--mode test`, does not set `VITEST`, so the adapter is enabled there. Demo workspaces still use the mock catalog.

## Tests run in this session

- `uv run pytest agent/tests shared/tests backend/tests -q` after the factory and OpenAPI fixes: the earlier run had 2 failures that were corrected; the registry test passed separately (`1 passed`).
- `uv run pyright` on the knowledge packages: `0 errors` after the type fixes.
- Migration scope: `Migration scope: VERIFIED (1 phase migrations)`.
- Frontend `npm ci`, `tsc --noEmit`, and Vitest: 24 files, 122 tests passed.
- `ci_ownership.py --branch feat/knowledge-base --local`: PASS against base `fc84d1fa`.

Not run: `supabase test db`, integration pytest, demo/real E2E, Voyage live tests, GitHub CI on the final SHA (to be filled after push).

## Known limits for the integrator

- Do not treat this SHA as `PHASE_2 = VERIFIED`.
- Start stack `kb` only when fewer than two Supabase stacks are running, then apply the migration with `supabase_worktree.py test` and seed with `seed-synthetic`.
- A Voyage key plus `.local/eval-budget.json` is required before any live embed or the 180-query holdout.
- `frontend/src/services/composition.test.ts` still expects a null knowledge adapter under Vitest. Removing the `VITEST` guard needs that test updated by the integrator.
- Generated columns and `search_chunks` need a migration-checker allowlist before they can move into SQL.
