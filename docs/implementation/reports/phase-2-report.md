# Phase 2 report

## A. Overall status

`PHASE_2 = NOT_VERIFIED`

The ingestion CLI, local Postgres schema, Voyage embeddings, hybrid retriever, and the real Knowledge Hub path all run. The holdout retrieval benchmark does not meet Recall@5 or no-result accuracy. There is still no verified `open_reuse` source whose article text was extracted. This branch is not a quality sign-off for students.

## B. Task completion

| Task | State | Evidence |
|---|---|---|
| P2-00 | Done | Branch `feat/knowledge-base`. Baseline `baseline/phase-2-3-start-rc3` (`3ff7cb35`) merged without rewriting the Knowledge Base commits. Stack `kb` offset 100 is up. `foundation` and `ag` were left running. |
| P2-01 | Partial | 13 sources re-checked. Official catalog page for Nghị định 80/2017/NĐ-CP was read. The signed PDF is an image scan, so it was not transcribed. No source moved to `open_reuse`. |
| P2-02 | Done | Migration applied on stack `kb`. pgTAP: 16 files, 300 tests, PASS, including `kb_00_schema.sql` and `kb_01_rls_grants.sql`. |
| P2-03 | Done | `plan`, `acquire`, manifest validation, parse/normalize path, SSRF guard. `acquire` reads the manifest. There are still no `open_reuse` acquire blocks, so a real run records zero downloads instead of pretending work happened. |
| P2-04 | Done | Existing chunk/dedupe path reused. Build is byte-stable: 51 documents, 726 chunks. |
| P2-05 | Partial | Authored cards reused. They are templated and overlap heavily. That overlap is the main reason the benchmark missed its targets. Cards were not rewritten after the holdout was scored. |
| P2-06 | Done | `voyage-4`, 1024 dimensions, `input_type` document and query. Live probe and the 726-chunk job succeeded. Hashing remains a separate embedder. Cache resume returned 726 hits and 0 new tokens. |
| P2-07 | Done | `plan`, `acquire`, `build`, `embed`, `store`, `validate`, `publish`, `rollback`, `status`, `verify-citations`, `seed-synthetic` perform real work. Exit `0` / `1` / `3`. Loopback only. |
| P2-08 | Done | `PgVectorKnowledgeRetriever` against Postgres. Empty filters are cast to `text[]`. `search_path` includes `extensions` after `SET ROLE authenticated`, which is required for `vector`. Contract-shaped integration tests passed with `HashingEmbedder`. Voyage smoke returned `syn-threat-messages` for the seeded threat query and `no_results` for an off-topic cooking query on that corpus. |
| P2-09 | Done | 180 frozen queries. SHA256 `0bedae78047fa0c04262f5f785dd73131d05fa67c63cba064d150e32624b19eb`. Dev 72 (60 answerable + 12 no-result). Test 108 (90 + 18). |
| P2-10 | Fail, recorded | Dev sweep locked hybrid at `min_vector_score=0.35`, `min_lexical_score=0.12`. Holdout was scored once and was not used to pick another configuration. Targets missed. |
| P2-11 | Present | Authenticated routes from the previous commits remain. Search 502s are `upstream_error`. The API-role search bug above was fixed in the retriever, which the API calls. |
| P2-12 | Present | Hub keeps "Tra cứu từ nguồn", loading, results, empty, error/retry, citation chip, and document drawer. Vitest still sees a null adapter because `VITEST` is set. Playwright does not. |
| P2-13 | Partial | Real Playwright `E-KB-01` passed on stack `kb` (search, citation, diacritics, no-result, 502 retry, second user, 8 widths, axe WCAG 2A/AA). Demo Playwright was not re-run in this session. |
| P2-14 | Partial | pgTAP covers RLS, anon denial, authenticated read of published rows only, and the single-published unique index. Personal-data scan is in `validate`. SSRF rejects loopback and plain HTTP. A full 500-string injection fuzz and a demo bundle secret scan were not re-run as a separate suite. |
| P2-15 | Partial | This report. GitHub CI on the final SHA is recorded after push. |

## C. Acceptance matrix

| ID | Status | Evidence |
|---|---|---|
| D2-01 | PASS for the pipeline, FAIL for source coverage | `build → embed voyage → store → validate → publish` on `kb-20261109-03`. 726 chunks, model `voyage-4`. No `open_reuse` full text. |
| D2-02 | PASS | `supabase_worktree.py test --name kb --offset 100`: 300 tests, PASS. |
| D2-03 | PASS | Live vectors are 1024-d, finite, L2 norm 1.0. `validate` accepted `kb-20261109-03`. |
| D2-04 | PASS | API-role search and admin search both return `KnowledgeResult`. Citation fields are populated. |
| D2-05 | PASS | `verify-citations` on `kb-20261109-03` exited 0 with `problems: []`. |
| D2-06 | PASS for the real spec that ran | `E-KB-01` passed. Demo suite not re-run. |
| D2-07 | FAIL | Holdout hybrid Recall@5 = 0.368, no-result accuracy = 0.167. Citation integrity = 1.0. Thresholds were not lowered after seeing the holdout. |
| D2-08 | PASS for the suites that ran | Knowledge unit tests 24 passed. Integration `test_publish_pg.py` 5 passed. pgTAP 300 passed. |
| D2-09 | PARTIAL | RLS pgTAP passed. Broader fuzz and bundle scan not repeated. |
| D2-10 | Pending CI | Ownership is run before commit. CI URL is filled after the push. |
| D2-11 | PASS as a report, not as a quality sign-off | This file. |

## D. Environment

- Worktree: `C:\Users\minhh\orca\workspaces\MoodPrint\knowledge-base`
- Branch: `feat/knowledge-base`
- Stack: `kb`, offset 100, API `54421`, DB `54422`. Also still running and untouched: `moodprint-foundation`, `moodprint-ag`.
- Python used by `uv`: 3.12.13. Node: 24.22.1.
- Voyage model: `voyage-4`. Dimensions: 1024. Price read 2026-11-09 from `https://docs.voyageai.com/docs/pricing`: USD 0.06 per million tokens. First 200 million tokens are free on the provider account; the local ledger still counts the list price.
- Credential: `VOYAGE_API_KEY` is present once in the worktree `.env` (46 characters, no BOM, no quotes, no surrounding whitespace). `EnvSettings` loads it when `APP_ENV` is not `test`. The process environment itself does not contain the variable until settings are constructed. `APP_ENV=test` still does not read the root dotenv. The earlier "missing key" result came from looking for `.env.live` and `.local/eval-budget.json`, not from this file.
- Ledger: `.local/voyage-ledger.json` (not committed). Hard cap USD 1.00. Spent USD 0.00401370. Reserved USD 0.
- Baseline: `baseline/phase-2-3-start-rc3` commit `3ff7cb35e86a4fd1278fe5053b93dc4712e6e681`, merged. Tag object is `1e7d61ae`; the commit is `3ff7cb35`. `origin/mhiu05/feat-refactor` is that same commit.
- Final source SHA: filled after the commit below.

## E. Corpus

- Registered sources: 13. `authored` 1 (`mp-authored`). `reference_only` 4 (UNICEF, WHO, Tổng đài 111, Bộ GD&ĐT). `unverified` 8.
- Verified `open_reuse`: 0. Rejected for embedding: the eight unverified sources, plus the image-only signed PDF of Nghị định 80/2017/NĐ-CP.
- Official metadata that was read: `https://vanban.chinhphu.vn/default.aspx?docid=190430&pageid=27160` — số 80/2017/NĐ-CP, ban hành 17-07-2017, hiệu lực 05-09-2017, Chính phủ, người ký Nguyễn Xuân Phúc. PDF `https://datafiles.chinhphu.vn/cpp/files/vbpq/2017/07/80.signed.pdf`, SHA256 `cdede8a6aa3fec59064f795483f937d179d0d6f37d9acee6914fa9bf6937a8e4`, 8 pages, 0 extracted characters. Not OCR'd and not copied from a commercial mirror. The file is only in `.local/corpus-cache/`.
- Điều 15 khoản 2 of the intellectual-property consolidation still says normative legal documents are outside copyright. That is a basis for a future text transcription. It is not a licence for a page we did not extract.
- Authored documents: 51. Chunks: 726. Version embedded with Voyage: `kb-20261109-03`.
- Manifest SHA256 after the source-note edit: `bc4a485ff5f42ca7113f37c92d59e898732c9e5af3d2cce5d234482a2ad53eae`.
- Coverage gap: no extracted Vietnamese statute text. Authored cards share a template, so topic separation is weak.

## F. Ingestion

| Command | Result |
|---|---|
| `plan` | Exit 0. 13 sources, 51 documents, 1 exclusion. |
| `build` | Exit 0. 51 documents, 726 chunks. Second build matched `chunks.jsonl`. |
| `embed --embedder hashing` | Exit 0. 726 vectors. |
| `embed --embedder voyage` | Exit 0. Model `voyage-4`, 65,148 tokens, USD 0.00390888, cache hits 0. |
| `embed --embedder voyage` again | Exit 0. Cache hits 726, tokens 0, USD 0. |
| `store/validate/publish --version kb-20261109-03` | Exit 0, then `verify-citations` exit 0. |
| `store` onto existing `kb-20261109-02` with a different manifest | Exit 1. That version was the synthetic integration fixture and stays immutable. |
| `rollback` to a missing version, and to the version that is already published | Exit 1. |
| `rollback` retired → published → retired | Exit 0 both ways (`kb-20261108-01` and `kb-20261109-03`). |
| `seed-synthetic` | Exit 0, including a second run. |

After Playwright, `seed-synthetic` published `kb-20261108-01` (hashing, 3 documents, 4 chunks) again. `kb-20261109-03` (Voyage, 51/726) is retained and `retired`. Restoring it is `rollback --target test-env --to kb-20261109-03`.

## G. Retrieval

- PostgreSQL retriever tests: `agent/tests/knowledge/test_publish_pg.py` (marker `integration`, so the default suite skips it), 5 passed. The API login (`moodprint_api` → `SET ROLE authenticated`) searches the published synthetic corpus and returns `syn-threat-messages` for "bị nhắn tin dọa trong nhóm lớp".
- Empty `country_scope` and `topics` arrays are cast to `text[]`. Without that cast Postgres reported `could not determine polymorphic type`.
- `vector` is not on the `authenticated` search path. The retriever sets `search_path` to `public, extensions` for the transaction. Without that, the operator `<=>` is missing and the Hub returns 502.
- Hybrid rank fusion, no-result on the synthetic cooking query, and citation fields were observed. Degraded lexical mode remains the embedder-failure path; it was not the path used for the Voyage smoke.
- `KnowledgeRetriever` and `build_knowledge_retriever` signatures were not changed. `use_vector` / `use_lexical` are optional constructor flags for the benchmark only. Defaults keep both branches.

## H. Benchmark

- Dataset: `agent/evals/knowledge/cases/benchmark.jsonl`
- SHA256: `0bedae78047fa0c04262f5f785dd73131d05fa67c63cba064d150e32624b19eb`
- Split: dev 60 answerable + 12 no-result; test 90 answerable + 18 no-result. No query id is in both splits.
- Dev threshold sweep (hybrid only) locked `min_vector_score=0.35`, `min_lexical_score=0.12` because it kept Recall@5 within 0.03 of the best dev recall (0.493) and had the best no-result accuracy in that band (0.25).
- Holdout, one pass, Voyage query embeddings, corpus `kb-20261109-03`:

| Config | Recall@5 | MRR@5 | nDCG@5 | No-result accuracy | Citation integrity | p50 ms | p95 ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| lexical | 0.230 | 0.311 | 0.235 | 0.167 | 1.0 | 33 | 58 |
| vector | 0.316 | 0.473 | 0.339 | 1.0 | 1.0 | 316 | 786 |
| hybrid (locked) | 0.368 | 0.467 | 0.369 | 0.167 | 1.0 | 59 | 92 |
| blend | 0.406 | 0.481 | 0.401 | 0.167 | 1.0 | 73 | 167 |

- Targets: Recall@5 ≥ 0.80 FAIL. No-result accuracy ≥ 0.90 FAIL for the locked hybrid. Citation integrity 100% PASS.
- Vector-only no-result accuracy on the holdout was 1.0. That was not used to change the locked hybrid choice.
- Cost of the 180 query embeddings: 1,191 tokens, USD 0.00007146, 180 calls. Query vectors were cached inside the run so the four configs did not re-bill the same text.
- Failed cases are dominated by shared template wording across topics. Lexical overlap also lets unrelated queries pass `min_lexical_score`.
- Decision: keep the dev-locked hybrid thresholds in `KnowledgeConfig`. Do not declare the quality gate passed.

## I. Full stack

- APIs: `GET /v1/knowledge/search`, `/documents/{documentId}`, `/sources`, `/corpus`, authenticated.
- Frontend: live section renders when the adapter is present. Empty copy is "Chưa tìm thấy nguồn phù hợp". Errors expose "Thử lại" and do not fill the live region with static articles.
- Real E2E: `uv run python scripts/e2e_stack.py --run --project real --name kb --offset 100 --grep E-KB-01` → 1 passed. The spec covers the threat query, citation drawer, undiacritic query, cooking no-result, forced 502 plus retry, a second user on the same document URL, widths 320–1440, and axe WCAG 2A/AA on `main`. It uses the synthetic seeded corpus and `HashingEmbedder`, not paid Voyage calls.
- Demo E2E: not re-run in this session.
- The first E2E attempts failed for three local reasons that were fixed: the route is `/support/knowledge`, the API role could not see `vector`, and the second login has to leave `/auth` before the deep link.

## J. Security

- RLS: anon cannot read sources. Authenticated reads published documents only. Authenticated cannot insert sources. `licence_note` is not readable. One published row is enforced. pgTAP passed.
- Licence: `validate` rejects a document whose class is not `open_reuse` or `authored`. Unverified sources are not stored.
- Secrets: the Voyage key is not printed. HTTP client logs already redact `Authorization`. The ledger and `.env` are outside Git.
- Prompt injection: the synthetic trap chunk is stored as data. Retrieval does not treat it as a tool instruction.
- Privacy: search logs length and status, not the query text, in the existing API logger.
- SSRF: `assert_public_https` rejects non-HTTPS and loopback resolutions. Redirects are re-checked against the allow-list.
- The authored corpus does not contain student records. The legal PDF was not embedded.

## K. Compatibility

- Merged `baseline/phase-2-3-start-rc3` (`969900f1` schema-drift allow-list and fixture timeout, via merge `3ff7cb35`). No rebase, no force-push, no Phase 3 source edits.
- `EnvSettings` test isolation was not changed.
- Migration checker deviation kept: `heading_norm` and `fts` are ordinary columns filled in Python, because generated columns and helper functions are still rejected by the frozen checker. Functional checks cover non-empty `fts` and folded headings.
- No new compatibility request. `build_knowledge_retriever` is unchanged.

## L. Tests and CI

Commands run on this worktree before the final commit:

| Command | Exit | Result |
|---|---|---|
| `uv run pytest agent/tests/knowledge -q` | 0 | 24 passed |
| `uv run pytest -m integration agent/tests/knowledge/test_publish_pg.py -q` | 0 | 5 passed |
| `uv run python scripts/dev/supabase_worktree.py test --name kb --offset 100` | 0 | 16 files, 300 tests, PASS |
| `uv run pyright agent/src/moodprint_agent/knowledge/ingest` | 0 | 0 errors |
| Real Playwright `E-KB-01` | 0 | 1 passed |
| `uv run python scripts/check.py` | 0 | ruff, pyright, import-linter, pytest: 834 passed, 84 deselected |
| `uv run python scripts/ci_ownership.py --branch feat/knowledge-base --local` | 0 | PASS against base `3ff7cb35` |
| GitHub Actions | filled after push | |

Tested SHA for the pre-commit suites is the worktree at the time of those commands. The CI row must match the pushed SHA. If they differ, this section is updated.

## M. Git

- Starting SHA: `faf8a392095b053700cd8737e39696ad474b4f30` (`origin/feat/knowledge-base` at the start of this session).
- RC3 merge is already on the branch before the completion commit.
- Final local SHA, remote SHA, and PR link: filled after commit and push.
- `.env` and `.local/voyage-ledger.json` are not in the commit.

## N. Integration readiness

**Is `feat/knowledge-base` ready to integrate with Phase 3?**

No, if "ready" means `PHASE_2 = VERIFIED`. Recall@5 and no-result accuracy failed, and there is no verified open-licence statute text.

Yes, as a functional branch the integrator can merge for wiring: the retriever protocol is intact, the CLI and schema exist, Voyage embeddings for `kb-20261109-03` are stored, and the Hub talks to the real API. The integrator should not treat hashing or the holdout numbers as a quality pass, and should rollback to `kb-20261109-03` on a local stack before judging Voyage retrieval. Do not deploy this to students.
