# Integration report: Phase 2 (Knowledge Base) and Phase 3 (AI Companion)

Branch `integration/phase-2-3`, 2026-11-09. Everything here uses synthetic data and local databases only.

## A. Overall status

| Item | Status |
|---|---|
| `PHASE_2` | **NOT_VERIFIED.** Recall@5 0.869 and citation integrity 1.0 pass; no-result accuracy 0.556 (10/18) against 0.90 fails (D2-07). See `phase-2-report.md`. |
| `PHASE_3` | **NOT_VERIFIED.** Q3-03 not demonstrated; live repeats incomplete because the OpenAI call ceiling (900 of 900) is spent. Unchanged by this work. See `phase-3-report.md`. |
| `G_INTEGRATION` | **Cannot be claimed.** It needs both phases verified and external safety review. No `baseline/phase-2-3-verified` tag was created. |
| `DEVELOPMENT_MERGE_STATUS` | **INTEGRATED_FOR_INTERNAL_DEVELOPMENT**, under the restricted policy in `docs/implementation/decisions/DR-INT-02-internal-merge.md`. Result of the merge: section H. |

This is an internal development integration. It is not a release, not a hosted-staging approval and not approval for real students.

## B. Git

| Ref | SHA |
|---|---|
| `origin/feat/knowledge-base` (Phase 2 head merged) | `b2c0586af6868ff996bddcec4ba99f2b4d565949` |
| `origin/feat/agent-companion` (Phase 3 head merged) | `505ea9b828811b40385e6ad59e317188bcf8713c` |
| `origin/mhiu05/feat-refactor` at the start of integration | `0976736f99c5bd8162ec3f39726ad768e781f871` (merge of PR #53; was `3ff7cb35` = `baseline/phase-2-3-start-rc3`) |
| `origin/main`, before and after | `8b329980af4038f4c2a565a6472fd01472fbdfef`, unchanged |
| Tags | `baseline/phase-2-3-start-rc1..rc3` untouched; no new tag |

- Both feature heads descend from `baseline/phase-2-3-start-rc3` (checked with `merge-base --is-ancestor`). Ownership PASS for both (`ci_ownership.py`, 159 and 261 paths).
- Merges, all `--no-ff`, no rebase, no rewrite of either feature branch, no `-X ours/theirs`: Phase 2, Phase 3, then Phase 2 again after its CI fix.
- Only two files conflicted, both generated: `backend/openapi.json` and `frontend/src/services/http/schema.gen.ts`. They were regenerated from source (`export_openapi.py`, `npm run gen:api`), not hand-merged. `shared/.../config.py` merged cleanly with both `KnowledgeConfig` and the Phase 3 `AgentConfig` additions intact. Files changed by both branches: those two, `config.py` and `test_storage_access.py` (target already carries the PR #53 fix).
- Compatibility PR #53 (`compat/cc-p3-003-storage-expiry`) was inspected, found to fail the required `offline` job (`F821 Undefined name 'secret'` from a dead `del secret`), fixed on its own branch (`03158a09`), re-run green, and merged as `0976736f`. The expired-URL invariant is still tested: a past-expiry re-signed token must be refused and a future-expiry control must pass.

## C. Knowledge Base

Corpus `kb-20261109-06` (54 documents, 74 chunks, `voyage-4`, manifest `95435827…`). Test-split results, sources, licensing and limits are in `phase-2-report.md`; they are not restated as passes here. Phase 2 CI: green on `b2c0586a` (run 42557140430). Earlier heads failed the integration job for reasons fixed in that commit.

## D. AI Companion and the real retriever

- **No silent fixture.** `build_context` used to replace a missing retriever with `FixtureKnowledgeRetriever()`. It now fails the turn. The routers still pass the app's retriever.
- **Explicit retriever choice.** `KnowledgeConfig.retriever` defaults to `pgvector`. The backend factory fails closed without a Voyage key, logs a warning when the fixture is chosen on purpose, and refuses the fixture when `APP_ENV=production`. Tests: `backend/tests/knowledge/test_factory.py`, `backend/tests/agent/test_wiring.py`.
- **Deterministic harnesses choose the fixture explicitly:** `scripts/e2e_app.py` (then swaps in the real retriever over the seeded corpus), the integration test builders and every `produce()` caller.
- **Real retrieval inside the real Companion** (`backend/tests/integration/test_integration_vertical_slice.py`): the real `PgVectorKnowledgeRetriever` over a published corpus, real PostgreSQL and RLS, scripted model. Verified: a real citation survives and names a document and source of the published corpus; a forged `[S9]` marker is dropped; an out-of-scope query yields no citation even if the model writes a marker; no write before approval, and the approved event equals what the user saw; history restores; user B gets 404 on user A's conversation and case. IT-05: three injected failures (rejected embedder credentials, embedder hang, database down) each end the run within the budget with no citation.
- **E2E seam.** With the real retriever behind the E2E app, Phase 3's `E-AG-01` and `E-AG-12` failed because they expected the fixture's chip title and because the Voyage-calibrated gate rejects `HashingEmbedder` vectors. The E2E retriever now lowers only the vector gate to 0.25 (measured: related queries 0.27 to 0.39 normalised, the closest unrelated query 0.22; test-only, documented in `testing.py`), and `E-AG-01` expects the real card title.
- **Q3-04.** `docs/implementation/decisions/DR-INT-01-q3-04.md`: accepted under the owner's written delegation as a product-policy decision, **not** independent child-safety validation. The original row stays in plan 07 with an amendment beside it, and `CC-P3-004` keeps its text under a status update. Deterministic tests on this branch: `test_safety_closure.py` and `test_safety.py` 246 passed, including the SC-04 pairs; no case identifier appears in source. Existing live evidence for `chat-07` stands (elevated 3/3); the present-contact variant is deterministic only.
- **Q3-03 is unchanged and unmet.** No independent urgency dataset exists.

## E. Database

- Migrations: 22 `f0/f1/ag` plus 1 `kb`, unique versions, `migration_scope_check` VERIFIED (6 phase migrations), `test_migration_versions.py` 11 passed.
- `int` stack (offset 300, `--lite`), clean initialisation: **pgTAP 20 files, 460 tests, PASS**.
- `migration_order_check.py`: **VERIFIED `order=kb-first` and `order=ag-first`**, using the real migrations of both phases.
- Publish, rollback and the single-published rule: Phase 2 integration tests (8) pass against the `int` stack as well as `kb`.
- Hosted Supabase: not touched. No migration, no corpus publish, no Auth setting changed.

## F. Tests

PENDING_F

## G. Security

| Area | Result |
|---|---|
| Critical findings | None known. |
| High | None known. |
| RLS and grants | `knowledge.*`: RLS on every table; `anon` fully revoked; `authenticated` reads the published version only; `licence_note` lives in a private table with no client access; `ingestion_runs` closed to clients. pgTAP covers it. |
| Cross-user isolation | Phase 3 isolation matrix (`test_phase3_isolation_matrix`), the slice test (user B 404), E2E `E-AG-10` and `E-KB-01` second user. |
| Prompt injection | Retrieved text is data; the synthetic trap card is returned as plain text; retrieval cannot trigger a tool. Phase 3 injection cases unchanged. |
| SSRF and evidence privacy | Phase 3 evidence fetcher tests unchanged and passing. Phase 2 ingestion SSRF guard resolves names with `socket.getaddrinfo` only (an AST test pins that; one reviewed exception in the network-client boundary test). |
| Secrets | Tracked-file scan test; frontend bundle scan, 0 hits. |
| Hosted safety | Fixture refused in production; no hosted write. |
| **Finding, Low** | `moodprint_api` has an unrestricted policy and write grants on `knowledge.source_confidential` (internal licence notes, no user data), although only the admin ingestion CLI needs to write. Not reachable from a runtime code path (queries are parameterised and fuzzed). Recommended: revoke in a later migration; not changed here to avoid altering a Phase 2 migration unreviewed. |

## H. CI and PRs

PENDING_H

## I. Remaining blockers for formal verification

1. D2-07 no-result accuracy (needs a reranker or abstain catalogue, an owner decision, then a new equivalent query set).
2. Q3-03: an independent urgency dataset and external safety review.
3. Live repeats for Phase 3 (needs the owner to raise `max_calls_total` and extend `expires_on`).
4. Human proofreading of the NĐ 80/2017 transcription; official text of Luật Trẻ em 2016 and Thông tư 06/2019; confirmation of NĐ 80/2017's current status.
5. Voyage training opt-out (O-06) and OpenAI data-handling approval for model-assisted safety.
6. Hosted staging deployment, which is separately authorised and not done.

## J. Owner handoff

| Use | Ready? |
|---|---|
| Internal MVP demonstration (synthetic data, demo workspace and scripted or opted-in live Companion) | Yes, after the merge below. |
| Further engineering and testing on one integrated branch | Yes. |
| Hosted staging deployment | **No.** Needs its own authorisation, a hosted corpus publish and a hosted migration. |
| Real-student release | **No.** Needs `PHASE_2` and `PHASE_3` verified, an independent safety review and legal and consent conditions of the original architecture. |

These four levels are not interchangeable.
