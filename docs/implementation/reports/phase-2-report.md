# Phase 2 report: Knowledge Base

Second round (2026-11-09), taken over from the first-pass agent. The first-pass report and its benchmark remain in Git history (commit `00a2db0b`) and in `agent/evals/knowledge/results/`; this file replaces its conclusions.

## A. Overall status

`PHASE_2 = NOT_VERIFIED`

One mandatory acceptance item fails on the final test run: **no-result accuracy 0.556 (10/18) against a target of 0.90**. Every other measured quality gate, including Recall@5 and citation integrity, passes. Details, causes and what would be needed to close it are in sections H and M.

What this branch is: a functional, tested, locally publishable Knowledge Base that returns relevant, correctly cited Vietnamese guidance and never fabricates a citation. What it is not: a quality sign-off for real students. In-domain questions the corpus cannot answer (penalty amounts, a named school's rules, other countries' law) still retrieve the nearest cards instead of returning no result.

## B. What was wrong with the first pass, with measurements

`agent/evals/knowledge/results/diagnosis-v1.json`, script `agent/evals/knowledge/diagnosis/diagnose_v1.py`, corpus `kb-20261109-03`, benchmark v1.

| Finding | Measurement |
|---|---|
| The corpus was padding, not content | 672 of 726 chunks came from 45 cards that repeat one paragraph eight times with a counter ("lần 3 trong bối cảnh lớp 10, tình huống số 04-02") and the raw topic key ("liên quan tới physical"). Median nearest-neighbour Jaccard 0.87, p90 1.00. 36% of all characters sat in boilerplate sentences that occur in at least 20% of chunks. |
| Provenance was invented | Every card said it was "cross-checked with UNICEF Việt Nam" or "who-youth-violence". Both sources are `reference_only` and nothing had been compared. |
| The keyword gate passed anything | All 30 off-topic queries had a lexical hit and 24 of 30 cleared `min_lexical_score` because the tsquery was an OR of tokens and a single shared common word cleared an absolute `ts_rank`. |
| Vector similarity separated well | Max-cosine AUC 0.98 for answerable versus no-result queries, but the locked gate rejected 27 of 150 answerable queries. |
| The benchmark was unsound | Dev and test shared one topic (dev held cyber, definition, physical, verbal, exclusion; test held the other nine). Labels were whole 3 to 4 card topic clusters, so strict Recall@5 needed all near-identical cards. No query style, no grades, and zero in-domain no-result queries. |
| The CRLF hash | `benchmark.jsonl` hashes to `0bedae78…` only after line-ending normalisation. The manifest digest had the same machine dependence (fixed). |

## C. Task completion

| Task | State | Evidence |
|---|---|---|
| P2-00 | Done | Branch `feat/knowledge-base`, stack `kb` offset 100 (DB 54422, API 54421), baseline `baseline/phase-2-3-start-rc3` merged. The first-pass agent's four unpushed commits were verified (ahead 4, behind 0, ownership PASS, no secrets in the diff) and pushed unchanged. |
| P2-01 | Partial | 13 sources scored. Nghị định 80/2017/NĐ-CP is now `open_reuse` (section F). Luật Trẻ em, Thông tư 06/2019 and 38/2019 remain `unverified`: the official texts could not be read. |
| P2-02 | Done | Migration `20261108190000_kb_schema.sql` unchanged. pgTAP 16 files, 300 tests, exit 0. |
| P2-03, P2-04 | Done | Pipeline and chunker. The chunker now merges short neighbouring sections up to the 600 to 1100 target and never merges across Điều/Khoản headings. |
| P2-05 | Done, target unmet | 54 documents, 74 chunks. The 350-chunk target is **not met** and was not padded to. |
| P2-06 | Done | `voyage-4`, 1024 dims. Embedding input is now title, heading and text. |
| P2-07 | Done | `plan`, `acquire`, `build`, `embed`, `store`, `validate`, `publish`, `rollback`, `status`, `verify-citations`, `seed-synthetic` all perform work; `--embedding-input` option added. |
| P2-08 | Done | Real retriever: IDF-coverage keyword branch, query-level gate, diacritic restoration (section H). Contract signature unchanged. |
| P2-09 | Done, with deviations | Benchmark v2, frozen before tuning (section I). |
| P2-10 | Done, FAIL recorded | Dev-only tuning, one test run, no-result target missed. |
| P2-11 | Done | Backend service tests (13). OpenAPI is unchanged because no route or schema changed. |
| P2-12, P2-13 | Done | Frontend unchanged apart from one formatting fix; Vitest 122, real E2E 1, demo E2E 13 (section K). |
| P2-14 | Done | 500-string fuzz at unit and database level, canary log scan, tracked-secret scan, licence gate (section J). |
| P2-15 | This report | |

## D. Acceptance matrix (doc 12 section 7)

| ID | Status | Evidence |
|---|---|---|
| D2-01 | PASS for the pipeline, FAIL for source coverage | `build → embed (Voyage) → store → validate → publish → verify-citations` on `kb-20261109-06`. One `open_reuse` source and one `authored`; the six-source target is unmet. |
| D2-02 | PASS | `supabase_worktree.py test --name kb --offset 100`: 300 tests, PASS. |
| D2-03 | PASS | `validate` accepted the version; 74 vectors, 1024 dimensions. |
| D2-04 | PASS | Retriever contract and integration tests pass against Postgres through the `authenticated` role. |
| D2-05 | PASS | `verify-citations` on `kb-20261109-06`: `problems: []`; benchmark citation integrity 1.0 over 900 returned chunks on the test run. |
| D2-06 | PASS | Vitest 122 tests including the Hub states, and real Playwright `E-KB-01` (results, citation, no-result, forced 502 with retry, no mock fallback). |
| D2-07 | **FAIL** | No-result accuracy 0.556 (10/18) against 0.90. Everything else passes (section I). |
| D2-08 | PASS for the suites run | 881 Python tests, 58 + 8 knowledge tests, 15 backend knowledge tests, pgTAP 300, Vitest 122, real E2E 1, demo E2E 13. Test counts rose from the first pass (24 knowledge tests). |
| D2-09 | PASS | Section J. |
| D2-10 | Ownership PASS locally; CI result in `integration-report.md` | Run for `5a1ac224` linked in section L. |
| D2-11 | PASS as a report | This file. |

## E. Environment and budget

- Worktree `C:\Users\minhh\orca\workspaces\MoodPrint\knowledge-base`, branch `feat/knowledge-base`. Docker Desktop was off at the start of the round; starting it restarted the `foundation`, `ag` and `kb` stacks together on an 8 GB VM.
- Voyage ledger `.local/voyage-ledger.json` (not committed): hard cap USD 1.00 unchanged, **spent USD 0.00729198**. All embeddings used `voyage-4`. `voyage-4-large`, `voyage-4-lite` and `rerank-3` were **not** used because the recorded authorization names `voyage-4` only. No OpenAI call was made.
- Key handling: the key lives in the worktree `.env` (gitignored) and was never printed. `APP_ENV=test` still does not read it.

## F. Sources and licensing

| Class | Count | Sources |
|---|---:|---|
| `open_reuse` | 1 | `vn-nd-80-2017` |
| `authored` | 1 | `mp-authored` |
| `reference_only` | 4 | UNICEF, WHO, Tổng đài 111, Bộ GD&ĐT |
| `unverified` | 7 | Luật Trẻ em 2016, Thông tư 06/2019, Thông tư 38/2019, two StopBullying pages, UNESCO, platform help |

**Nghị định 80/2017/NĐ-CP.** The official PDF (SHA256 `cdede8a6…a8e4`, 8 pages) is an image scan with no text layer; the first pass could not use it. No OCR engine was available, so the 8 page images were extracted and every operative provision (Điều 1, 2, 5, 6, 13, 16) was transcribed page by page, with page numbers, into `agent/ingestion/legal/nd-80-2017.md`. The original file is kept under `agent/ingestion/legal/original/`. The transcription was made by a model reading the images in a single pass with no human proofreading, which the document states.

Limits that stay open:

- The legal basis for reuse (Luật Sở hữu trí tuệ Điều 15 khoản 2, văn bản quy phạm pháp luật not protected) was confirmed through secondary sources only. Class `open_reuse` is therefore **partially verified**.
- Current status of NĐ 80/2017 is **not confirmed** from an official database (`vbpl.vn`, `congbao.chinhphu.vn` render with JavaScript; mirrors returned HTTP 403). The official government page lists no amendment or replacement; secondary sources say it is in force.
- Secondary sources report that Luật Trẻ em 2016 has an official consolidation (108/VBHN-VPQH, 2025-08-27) and that Điều 6 of Thông tư 06/2019 was replaced by Thông tư 03/2026/TT-BGDĐT. Neither was read from an official text, so neither source was upgraded.
- Numbers 113 and 115 in the urgent-safety cards come from secondary sources.

## G. Corpus

- Version **`kb-20261109-06`**: 54 documents, 74 chunks, `manifest_sha256` `95435827eccd150b77734f2a58a8c3fe03c7b684ece93d6cbc226fee49ed3eed` (line-ending independent), `voyage-4`, 1024 dimensions, 74 of 74 vectors from the embedding cache. Earlier versions are immutable and untouched.
- 44 new situation-specific cards over the 14 core topics (every topic has at least three documents), 9 legacy cards with their appended filler removed, and the NĐ 80 excerpt.
- Chunk size: median 722 characters, 55 of 74 chunks at 600 or more, 7 short chunks that are deliberately short legal provisions (Điều 1 khoản 1, Điều 16 and similar).
- Duplication after the rewrite: only 2 of 190 pre-merge chunks had a neighbour with Jaccard at least 0.5 (maximum 0.765, median 0.0), and no sentence of more than 60 characters occurs in more than two cards (enforced by a test).
- Provenance is now accurate. Cards cite `mp-authored` ("authored by MoodPrint; not reviewed by an outside expert") and add NĐ 80 or the 111 fact only where the card actually uses them. The old `_review` notes, which claimed cross-checks that never happened, were removed.
- **Targets not met:** 350 chunks (74), six usable sources (two), blind second relabel of benchmark labels (not done).
- Known content gaps, intentionally left as `no_results` territory: penalties, age of criminal responsibility, individual school rules, transfers, local directories, medical advice, foreign law.

## H. Retrieval

What changed, each measured on the dev split only (`results/dev-sweep-v2.json`):

1. **Keyword branch by coverage.** Candidates still come from the tsquery. Each is scored by the IDF-weighted share of the query's terms it contains. Diacritics are respected when typed; unaccented tokens match by folded form. A common shared word weighs almost nothing.
2. **Query-level answerable gate.** A query is answerable only if its best hit clears `min_vector_score` or `min_lexical_score`; chunks above lower floors are then kept. Dev Recall@5 0.72 to 0.76 at the same no-result accuracy.
3. **Diacritic restoration.** An unaccented query that looks Vietnamese is restored from the published corpus text (Viterbi over unigram and bigram counts) before embedding. Dev Recall@5 for unaccented queries 0.46 to 0.89, overall 0.76 to 0.86. English and already-accented text pass through unchanged.
4. Rejected on dev: appending the unaccented form to each chunk's embedding input (lower no-result accuracy and lower unconstrained nDCG).
5. Not run: `rerank-3` and other Voyage models (authorization), HNSW (exact scan is 56 ms p50 end to end excluding the Voyage call).

Locked configuration (`results/locked-config-v2.json`, enforced equal to the `KnowledgeConfig` defaults by a test): `gate_scope=query`, `min_vector_score=0.425` (cosine 0.455), `min_lexical_score=0.5`, floors 0.2 and 0.2, `lexical_weight=0` (ranking is by vector score; the keyword branch opens the gate and powers the degraded mode), `max_chunks_per_document=1`, `restore_diacritics=true`.

Selection rule, registered before the first sweep: keep settings with false-no-result at most 0.08 and no-result accuracy at least 0.90; maximise dev nDCG@10; take the median feasible vector gate. **No setting met both constraints on dev**, so the registered fallback applied: best no-result accuracy under the false-no-result cap (0.833), without relaxing anything.

## I. Benchmark

- Dataset `agent/evals/knowledge/cases/benchmark_v2.jsonl`, LF SHA-256 `6d9fae8b0aedb5f1cca52c965dc1696250266755b79333289bf1e235ace4f1d6`, committed (`57e2123b`) before any tuning. 180 queries: 150 answerable, 30 no-result (10 in-domain gaps, 20 out of scope, several of them lexical traps). Split dev 60 + 12, test 90 + 18, stratified by topic and style, all 14 topics in both.
- Labels are graded per document. A pooled review of lexical, vector and hybrid candidates added 30 grade-1 labels before the freeze.
- **Limits.** The same agent wrote the corpus, the queries and the labels; no human reviewed anything and there was **no blind second labelling pass**. Treat the numbers as optimistic. Details in `cases/LABEL-REVIEW.md`.
- The locked configuration was committed (`4bf2fbce`) before the test split was read. Two earlier output files that contained per-query test results were deleted unread. The test split was then run **once** over the five registered configurations.

### Test split, one pass, corpus `kb-20261109-06`

| Config | Hit@5 | Recall@5 | Recall@10 | MRR@10 | nDCG@10 | P@1 | False no-result | No-result accuracy |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A lexical only | 0.300 | 0.233 | 0.423 | 0.154 | 0.206 | 0.033 | 0.267 | 0.722 (13/18) |
| B vector only | 0.833 | 0.769 | 0.817 | 0.800 | 0.774 | 0.767 | 0.156 | 0.722 (13/18) |
| C hybrid RRF | 0.900 | 0.776 | 0.874 | 0.763 | 0.723 | 0.656 | 0.056 | 0.556 (10/18) |
| C′ blend | 0.889 | 0.780 | 0.872 | 0.773 | 0.740 | 0.678 | 0.056 | 0.556 (10/18) |
| **Locked** | **0.933** | **0.869** | **0.917** | **0.886** | **0.863** | **0.844** | **0.056** | **0.556 (10/18)** |

Locked configuration against the plan section 7.5 targets:

| Metric | Target | Result | |
|---|---|---|---|
| Hit@5 | at least 0.90 | 0.933 | PASS |
| Recall@5 | at least 0.80 | 0.869, 95% CI [0.807, 0.920] | PASS |
| Recall@5, unaccented / slang | at least 0.72 / 0.65 | 0.986 / 0.760 | PASS |
| Recall@10 | at least 0.90 | 0.917 | PASS |
| MRR@10, nDCG@10 | at least 0.60, 0.65 | 0.886, 0.863 | PASS |
| Precision@1 | at least 0.75 | 0.844 | PASS |
| False no-result | at most 0.08 | 0.056 | PASS |
| Citation integrity | 100% | 1.00 over 900 chunks | PASS |
| **No-result accuracy** | at least 0.90 (17 of 18) | **0.556 (10/18)**; out of scope 9/12, in-domain gaps 1/6; 95% CI [0.333, 0.778] | **FAIL** |
| Hybrid over best single branch | at least +0.03 Recall@5 | C 0.776 versus B 0.769: +0.007 | not justified, so ranking stays vector-led |
| Latency, warm | p50 600 ms, p95 1 200 ms | 56 / 132 ms for the database and scoring with the embedding cached; **330 / 1 044 ms end to end with a live Voyage call** (20 fresh queries, published corpus, `authenticated` role, one warm-up) | PASS, small sample |

By style (Recall@5): standard 0.894, narrative 0.833, unaccented 0.986, slang 0.760, English-mixed 0.773. Lowest topics: emotional-impact 0.72, verbal-social 0.75, school-procedure 0.77, legal 0.78.

### Failed cases (test)

- Out-of-scope answered: N006 "cách xóa tin nhắn rác cho đỡ đầy bộ nhớ điện thoại" (shares "tin nhắn"), N007 "xem phim hành động mới nhất", N020 "dịch câu này sang tiếng anh giúp mình".
- In-domain gaps answered with the nearest cards: N021 penalty amounts, N024 school transfer, N025 bullying at work, N027 US law, N028 principal's phone number.
- Answerable but returned nothing: A057 (English), A064, A085, A113, A128 (slang or narrative with little word overlap).
- Cost: query embeddings for 180 queries, a few hundred tokens each run; total Voyage spend USD 0.0073.

## J. Security and privacy

| Check | Evidence |
|---|---|
| RLS and grants | pgTAP 300 tests pass, including `kb_00_schema.sql` and `kb_01_rls_grants.sql`. |
| 500 hostile queries, unit level | `test_security_query.py`: SQL, tsquery operator, template, control character and RTL strings plus 490 seeded random strings; the tsquery is always `^[a-z0-9]+( \| [a-z0-9]+)*$`, at most 16 terms. **This found a real defect**: the new tokenizer let an underscore token such as `pg_sleep` into the tsquery. Fixed (underscore is a separator, only ASCII-foldable terms reach the tsquery). |
| 500 hostile queries, database level | `test_security_pg.py` through the `authenticated` role: no exception, status always `ok` or `no_results`. |
| No raw query in logs | Backend service test and database test with a `ZZ-CANARY-<uuid>` query at DEBUG level: not present. |
| Identifier redaction | Email, phone, URL and handle are removed before the embedder (test). |
| Secrets | `test_no_tracked_file_contains_a_credential` scans every tracked text file for Voyage, OpenAI-style, Supabase secret keys, JWTs and private keys; `.env` is not tracked. |
| Licence gate | Manifest test: every document is `authored` or `open_reuse`; no document sits on an `unverified` source; `open_reuse` needs a quote. |
| Boilerplate guard | A test fails if a sentence of more than 60 characters repeats across more than two cards. |
| Prompt injection | The synthetic corpus keeps the trap card; retrieval returns it as data. |

Remaining risks: single-reader transcription of the legal text; secondary-only licence basis; no independent safety review of the card wording; queries are sent to Voyage after redaction of obvious identifiers only, and the owner's Voyage training opt-out (O-06) is not confirmed.

## K. Tests

Run on this worktree; the tested code is the final source of the branch (the only later changes are documentation and this report).

| Command | Exit | Result |
|---|---|---|
| `uv run python scripts/check.py` | 0 | ruff check, ruff format, pyright, import-linter (3 contracts kept, 0 broken), pytest: **881 passed, 87 deselected** |
| `uv run pytest agent/tests/knowledge -q` | 0 | 58 passed (up from 24 in the first pass) |
| `uv run pytest -m integration agent/tests/knowledge -q` with the kb stack env | 0 | 8 passed (retriever contract, publish, rollback, 500 hostile queries, canary log) |
| `uv run pytest backend/tests/knowledge -q` | 0 | 15 passed (13 new service tests) |
| `uv run pytest shared/tests -q` | 0 | 58 passed |
| `uv run python scripts/dev/supabase_worktree.py test --name kb --offset 100` | 0 | pgTAP 16 files, 300 tests, PASS |
| Frontend `npm run typecheck`, `lint`, `build`, `check:boundaries` | 0 each | clean |
| Frontend `npm test -- --maxWorkers=2` | 0 | 24 files, 122 tests passed |
| Frontend `npm run format:check` | 1 as checked out | 122 files differ **only by CRLF line endings** of this Windows checkout (the repository stores LF). With `--end-of-line auto` one real file differed, `e2e/knowledge-real.spec.ts`; it was formatted and the check passes. |
| Frontend bundle secret scan (script, 15 files of `frontend/dist`, matched against key patterns and the two configured secret values) | 0 | 0 hits |
| `uv run python scripts/e2e_stack.py --run --project real --name kb --offset 100 --grep E-KB` | 0 | 1 passed (15.3 s): search, citation drawer, unaccented query, no-result, forced 502 with retry, second user, 8 widths, axe |
| `uv run python scripts/e2e_stack.py --run --project demo --name kb --offset 100` | 0 | 13 passed (4.7 min) |
| Locked configuration regression on the final code, dev and test splits | 0 | identical metrics to the recorded runs |

Isolation: the E2E harness seeds the synthetic corpus and replaces the published one. After the runs the final corpus was published again (`publish --version kb-20261109-06`); the integration tests now restore the live corpus through a fixture (`agent/tests/knowledge/conftest.py`).

Not run in this round: Playwright responsive matrix and axe for the demo beyond what the 13 demo specs and `E-KB-01` already cover; a separate API HTTP test file (`test_knowledge_http.py`) because the service tests plus the real E2E cover the same behaviour; no GitHub-hosted Voyage test.

## L. Git and CI

- Baseline `baseline/phase-2-3-start-rc3` = `3ff7cb35`, already merged into the branch before this round.
- The first-pass agent's four unpushed commits (`3ff7cb35`..`00a2db0b`) were verified before anything else (ahead 4, behind 0, clean tree, no merge in progress, ownership PASS, no credential in the diff) and pushed unchanged with a normal push: `faf8a392..00a2db0b`.
- This round's commits, all pushed to `origin/feat/knowledge-base` without force:

| SHA | Subject |
|---|---|
| `0d7a14d8` | measured diagnosis of the holdout failure |
| `eb090342` | rebuilt corpus, section-merging chunker, manifest generator, digest independent of line endings |
| `57e2123b` | **benchmark v2 frozen before any tuning** |
| `4bf2fbce` | coverage keyword branch, query-level gate, diacritic restoration, **configuration locked on dev** (committed before the test split was read) |
| `5a1ac224` | security and licence suites, test-split results, this report (tested SHA for sections K and I) |

- `origin/feat/knowledge-base` equals the local branch at `5a1ac224` (checked with `git ls-remote`). `.env` and `.local/` (including the Voyage ledger) are not in any commit.
- GitHub Actions for `5a1ac224`: https://github.com/mhiu05/MoodPrint/actions/runs/42553524643. A report cannot hold the CI result of the commit that contains it, so the result for this SHA, and for any docs-only follow-up, is recorded in `integration-report.md`.

## M. Known limitations and recommended next steps

1. **No-result accuracy (D2-07).** In-domain gaps score high on similarity (cosine 0.42 to 0.64, above the median answerable query at 0.52), so no threshold separates "related but not covered" from "covered, asked in other words". Options, each needing an owner decision: a reranker (outside the recorded Voyage authorization), a curated abstain catalogue of intents the corpus must not answer (penalties, criminal age, named schools, medication), or letting the Companion judge answerability from the returned text. After any of these, re-run on a **new** equivalent query set; the current test split has been read.
2. Expand the corpus toward the 350-chunk target with real content, and read the official text of Luật Trẻ em 2016 and Thông tư 06/2019 to add a second legal source.
3. Human proofreading of the NĐ 80 transcription and of the card wording; a blind second labelling pass on the benchmark.
4. Measure end-to-end latency with live Voyage embeddings (the 56 / 132 ms figure excludes the network call).
5. Integrator: do not publish this corpus to hosted Supabase or switch any default retriever for real students on this evidence.

## N. Integration readiness

Ready to merge for wiring and internal demonstration: the retriever protocol is unchanged, the corpus `kb-20261109-06` is stored and validated, citations verify, and security tests pass. **Not** ready as a verified quality release: D2-07 fails and the limits above stand.
