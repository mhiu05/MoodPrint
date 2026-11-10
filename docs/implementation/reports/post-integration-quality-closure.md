# MoodPrint post-integration quality closure

Work performed 9–10 November 2026. Public sources, synthetic data and isolated local `int` stack (offset 300) only. Historical phase/integration reports and failures remain intact.

## A. Delivery and overall status

- Branch: `mhiu05/feat-refactor`, used directly; upstream `origin/mhiu05/feat-refactor`. No new branch/worktree/PR, main change, destructive history operation or force push.
- Starting SHA: `2dde44dcac5eb57c061c362805dc612a542baa35`, initially clean and equal to upstream; PR #54 integration merge was `d20be7c936e23e14fb0f4fe52579fa062762ca63`.
- Final functional-source delivery: `e831a31d935aeb363f9e7689e21b31782e072568`; final integration-test correction: `5de00ced922a4ac95b9f8455a11cb1000fb53e2a`. Supplemental V4 is frozen and evaluated at `040816f8ec38c68dc2eb7d45ac5ac4d5653e80c7`. Later commits contain evidence/manifests/reports only. Resolve the final report-bearing SHA with `git log -1 --format=%H -- docs/implementation/reports/post-integration-quality-closure.md`; the final handoff records the actual verified remote SHA and its CI. A tracked report cannot embed the hash of the commit containing its own final bytes.
- Four workstreams implemented: retrieval/Companion evidence support; urgency/assessor hardening and independent-review materials; live-evaluation provenance, 3x repeats and original S-06 infrastructure; corpus/source provenance and forward-only DB least privilege.
- Formal status stays `PHASE_2=NOT_VERIFIED`, `PHASE_3=NOT_VERIFIED`, `G_INTEGRATION=NOT_VERIFIED`, `Q3-03=NOT_DEMONSTRATED`, `INTEGRATED_FOR_INTERNAL_DEVELOPMENT=YES`.

Engineering improvements and reproducible evidence are delivered. Independent safety review, paid observations, human legal review and original corpus/source acceptance remain unresolved. No verified-baseline tag, hosted action, deployment, real-student data, paid model judge or new OpenAI paid call occurred. `.gitignore` is unchanged from the starting SHA.

## B. Retrieval

The [retrieval report](quality-closure-retrieval.md) records root cause, every historical no-result failure, candidate scores/full chunk text, method comparisons, final errors and uncertainty.

| Evidence | Recall@5 | No-result | Citation integrity |
|---|---:|---:|---:|
| Original v2 test, exact corpus06, reproduced topical gate | 0.869444 | 10/18 | 1.0 |
| Same inspected v2 test/corpus06, evidence support | 0.869444 | 18/18 | 1.0 |
| Inspected v2 test/new corpus07, evidence support | 0.8750 | 18/18 | 1.0 |
| Frozen V3, corpus07 | 0.9889 | 30/30 | 889/889 |
| Supplemental frozen V4, corpus07 | **0.9600** | **28/30 (0.9333)** | **1461/1461** |

V3 has 120 synthetic queries and 13 primary topics, despite 14 intended in its registration. Its original results/labels remain intact. V4 repairs coverage and original positive style counts: 180 queries, all 14 topics, 150 answerable variants from 30 situations x 5 correlated styles, and 30 negatives (10 gaps / 20 OOS). It was authored after inspecting V3, then committed before its first evaluation; it is not an untouched independent holdout. Same coding agent authored code/cases/labels. No final labels or implementation changed after V4 results.

V4 locked Recall@10=0.9667, MRR@10=0.9089, nDCG@10=0.9221, P@1=0.86; false-no-result 5/150, false-result 2/30. Binary answerable precision among returned queries is 145/147; top-5 labelled-evidence precision is 144/147. Five slang abstentions and one narrative rank-6 miss remain. The two false results concern an unrecognized school-specific suspension question and a battery-optimization question. These also expose remaining Companion support-buffer scope gaps. All errors and source-score evidence are reported; no universal answerability guarantee is claimed.

V4 per-query bootstrap Recall@5 95% [0.927, 0.987]; positive-seed bootstrap [0.9267, 0.9867]; no-result Wilson [0.7868, 0.9815]. Small synthetic negatives and correlated variants limit inference. Required point targets pass while retaining answers, but do not establish formal Phase 2 acceptance.

The versioned bounded requirement catalogue separates answer support from similarity without raising locked thresholds. It checks full original questions before truncation, including generalized tool queries and approval resumes; knowledge policy version 2 invalidates older checkpoints without that binding. Recognized unsupported requirements, empty retrieval and provider errors produce insufficient-information guidance and an empty citation ledger. Precise SSE content is buffered until support resolution. Frozen public contracts stay unchanged. Unknown wording/institutions and multi-chunk entailment remain limitations.

Fresh provider timing: 20 systematic V3 queries, 5 warmups, 3 repeats / 60 measurements; live Voyage + authenticated PostgreSQL + support p50 **355.7 ms**, p95 **759.6 ms**. V4 locked cached p50/p95 **52.4/85.5 ms**. First-method cache misses are disclosed; those fields are not compared as cache-only timing.

## C. Urgency and safety

The [safety report](quality-closure-safety.md) and `agent/evals/results/safety-quality-closure-v2.json` preserve full confusion matrices, per-group errors, confidence intervals and dataset/source hashes.

- Previously inspected cross-model synthetic set: immediate recall **8/14 = 0.5714**, benign immediate false positives **0/10**, six immediate misses. Same-author final set: 32/32 and 0/22, but only 0.890625 exact three-level accuracy. Neither is independent human-labelled evidence.
- Clause-local context, timed conditional self-harm, third-person overdose and multi-turn actor/time relationships improved. Safe helpers no longer inherit an aggressor role. Approved Q3-04 present-danger policy is unchanged.
- Assessor errors/refusal/timeouts retain a conservative elevated/watch state and cannot lower deterministic immediate. Cancellation cleanup, injection resistance, refusal usage and roleplay/main-failure accounting are tested offline. `MOODPRINT_MODEL_ASSISTED_SAFETY` stays off by default.
- The [Vietnamese reviewer package](../safety-review/README.vi.md) provides taxonomy, labelling examples/counterexamples, blind annotation/adjudication, schema, confusion/CI workflow and sign-off fields. Human review is PENDING. Reputable external dataset resources were investigated; restricted conversations were not acquired/scraped or presented as reusable Vietnamese labels.

`Q3-03=NOT_DEMONSTRATED`. No independent safety certification or real-student readiness claim is made. Model-assisted safety still needs explicit data-handling approval.

## D. Live-evaluation readiness and budget

The [live-evaluation report](quality-closure-live-evals.md) gives exact scopes, prompts, cases, requests and approval fields. Pinned plans and explicit NOT_RUN status are under `agent/evals/plans/quality-closure/`, source snapshot `040816f8`.

Original OpenAI authorization remains unchanged: max USD 2.90, max calls 900, model `gpt-6-luna`, expiry 2026-11-12 UTC. **900/900 calls used; zero remain.** Ledger commitment $0.16324955 = reconciled provider-reported $0.15527855 + conservative holds $0.007971 across six unknown calls; known tokens 1796840 plus 33326 held. This task made zero paid OpenAI calls. Both paid entrypoints refuse at the call ceiling before constructing a provider. No ledger reset, cap/expiry change or replacement authorization occurred.

Missing current observations: 201 fixture-suite slots (67 x 3), 60 real-retriever slots (20 x 3), 240 original S-06 slots (20 x 4 x 3): **501 NOT_RUN**. Adaptive tool loops imply 696 minimum through 2418 maximum requests. Historical outputs lacking current source/prompt/case identity receive no current credit. Every output/assertion/grade binds provenance and exact-output digest; missing repeats, crashes, ungraded/stale outputs cannot pass.

Original S-06 structured-output mechanisms (JSON stream, closing read-only assessment tool, postprocess classifier plus plain reference) now have a runner and injected metered adapter. Offline tests verify mechanics, cancellation and malformed-output handling. They do not complete the live experiment or select a mechanism. Risk-detection architecture A/B/C remains a separate experiment.

For full paid continuation, the owner must amend the **existing** authorization and preserve the same ledger: proposed cumulative `max_calls_total=3318`, `max_tokens_total=32000000`, `max_usd=15.20`; keep 60000 tokens/run, 4096 output/request, same model/scopes. Additional conservative envelope: 2418 calls / 30060000 tokens / $15.03 at the recorded historical price snapshot. Owner approval fields, current pricing confirmation and a valid execution window are required. This request is not authorization; paid suites remain **BLOCKED**.

## E. Corpus and database security

See [corpus/security report](quality-closure-corpus-security.md), [primary legal audit](../../../agent/ingestion/legal/LEGAL-AUDIT-2026-11-09.md) and [human page-review queue](../../../agent/ingestion/legal/HUMAN-REVIEW-CHECKLIST.md).

New local corpus `kb-20261109-07`: **57 documents / 80 chunks**, manifest `f5e14a3b96c14c8aed2ba3d144d29e680c52132861b18c470185a07e8343ffe8`, voyage-4 / 1024 dimensions. Three substantive cards and two distinct source revisions add child privacy/reporting and teacher duties with preserved official originals/page locators. Existing cards, IDs and old versions remain unchanged. Two builds were byte-identical. Seventy-four embeddings were reused, six new chunks embedded, then local store/validation/citation/publication/rollback verified.

Registry: 15 candidates, 3 open_reuse + 1 authored + 4 reference_only + 7 unverified. Four usable sources and 80 chunks still miss six sources / 350 chunks. No padding. Primary legal text supports legal-text reuse; portal commentary/photos are excluded. Child Law under-16 scope and TT03/2026 replacement of TT06 Article 6 were checked. ND80 current status and human proofreading remain pending. An AI consistency review is not an independent legal review.

Forward migration `20261109132352_kb_fix_private_ingestion_privileges.sql` revokes table/column privileges on `knowledge.source_confidential` from runtime/PUBLIC/client/service roles, retains RLS/deny policy and preserves admin/owner ingestion. No historical migration edit, broad grant or security-definer bypass. Positive admin CRUD and negative runtime/client access tests cover preserved metadata. RED first showed 2/19 new TAP failures; final pgTAP **479** and integration **149** pass. Both clean migration order permutations pass. Four initial anon-test setup failures were fixed by using the admin session to assume anon, preserving the runtime's lack of anon membership.

Original cumulative Voyage ledger ends at **$0.00784422 / $1.00**, zero reserved. This task added 368 calls / 9021 tokens / $0.00054126: corpus 1 call / 1065 tokens, V3 120 / 2369, live timing 65 / 1200, v2 restorer cache 2 / 19, V4 180 / 4368. Authorization/model/scope were unchanged. Unknown usage retains conservative holds for all five possible attempts. No hosted action occurred.

## F. Testing and CI

Functional source and raw evaluation artifacts pin source SHAs/hashes. The final local offline rerun is at `040816f8`; earlier full DB/E2E receipt is at `5de00ced` with identical functional code. No test was weakened to pass.

| Command/check | Exit / measured result |
|---|---|
| `uv sync --all-packages --all-extras --locked` | 0; 77 resolved / 74 checked |
| `uv run python scripts/check.py` | 0; ruff, format, pyright, three import contracts; 1581 passed / 155 deselected |
| `uv run python scripts/export_contract_schemas.py --check` | 0; no drift |
| `uv run python scripts/export_openapi.py --check` | 0; no drift |
| `uv run python scripts/dev/migration_order_check.py` on int/300 | 0; kb-first and ag-first pass; restores source chronology |
| `uv run python scripts/dev/supabase_worktree.py test --name int --offset 300 --lite` | 0; 21 files / 479 assertions pass |
| `uv run python scripts/dev/migration_scope_check.py` | 0; seven phase migrations verified |
| `uv run pytest scripts/db/tests/test_migration_versions.py -q` | 0; 11 passed |
| `uv run pytest -m integration -q --tb=short` with int environment | 0; final 149 passed / 1587 deselected |
| Frontend `npm run typecheck`, `lint`, `build`, `check:boundaries` | 0 each; source/bundle secret and import scans clean |
| Frontend `npm test -- --maxWorkers=2` | 0; 26 files / 144 passed |
| Frontend `npm run format:check -- --end-of-line auto` | 0; all formatted (Windows checkout) |
| `uv run python scripts/e2e_stack.py --run --project real --name int --offset 300 --agent scripted` | 0; 36 passed + 1 urgent-help; final local code/test SHA 5de00ced |
| `uv run python scripts/e2e_stack.py --run --project demo --name int --offset 300` | 0; 13 passed |
| `uv run pytest agent/tests/knowledge/test_security_repo.py -q` | 0; five passed |
| Eval provenance / S-06 mechanics scoped regression | 69 passed; real-adapter/metering tests also pass; no paid calls |
| Frozen V3, full v2 regression on corpus06/07 | 0; all registered methods and failures preserved |
| Frozen V4 via `run_closure.py --split test --freeze ... --live-embeddings` | Complete 180-case report for each method; process exit receipt expired across continuation; source/corpus/hash verified |
| Paid `run.py --suite live` / `run_s06.py --live`, original ledger | Expected exit 3; call ceiling exhausted; zero provider calls |

Source CI: **[Foundation run 42636960052](https://github.com/mhiu05/MoodPrint/actions/runs/42636960052)** completed successfully on actual pushed SHA `5de00ced922a4ac95b9f8455a11cb1000fb53e2a`, both `offline` and `integration`. That workflow runs locked dependency sync, Python checks/exports, frontend generation/type/lint/format/tests/build/boundaries, clean local DB bootstrap/pgTAP/integration, demo and scripted real E2E. Subsequent evidence/report-only commit CI is checked separately at its actual remote SHA in the final handoff; no success is inferred from this earlier run.

Applicable Phase 0/1 checkpoints were executed individually on int. `verify_phase0.py --regression` and `verify_phase1.py` wrappers are NOT_RUN because they repeat full suites and reset the stack again. No single-command wrapper pass or formal phase verification is claimed. Hosted checks, paid live repeats/rubric grades, rerank/alternate models and independent human review remain NOT_RUN/BLOCKED.

Preserved failed checks: unsupported migration-scope `--all` (exit 2), then correct command passed; import formatting corrected before full check; expanded conversation exposed old history-window expectation after a fifth turn, now checks default 3 and explicit 4 while retaining original persistence assertion; a Windows Unicode transport error was corrected. CRLF needs local Prettier override; jsdom canvas and Vite chunk-size warnings are non-failing. On continuation Docker was off; a cache-only V4 replay exited 1 before retrieval and made no calls. Existing V4 output remained unchanged. Earlier Docker recovery and stopping ag/kb/foundation were performed only after explicit owner approval; their data/volumes were preserved.

## G. Readiness and blockers

| Area | Classification |
|---|---|
| Knowledge retrieval | Synthetic point targets pass; bounded support catalogue still has two V4 false-result cases and self-authored-label limits |
| Companion implementation | Integrated and regression-tested; generic evidence entailment and formal Phase 3 acceptance remain incomplete |
| Safety evaluation | NOT_DEMONSTRATED; cross-set recall 8/14 and independent human review missing |
| Internal demo | Available with synthetic/local data and scripted provider under existing restricted policy |
| Hosted staging | Not authorized; source/legal/data-handling gates pending; no hosted migration/publication performed |
| Real-student release | NOT_READY; independent safety, legal, consent and full phase requirements remain |

Remaining blockers: qualified independent Vietnamese safety evaluation; current-prompt 3x paid observations and rubric grades; human legal transcription review / ND80 status; original source/corpus coverage; Voyage opt-out / OpenAI data-handling approval; separately authorized hosted staging. CI green does not change PHASE_2, PHASE_3 or G_INTEGRATION to VERIFIED.

Last local DB receipt, before Docker subsequently stopped: E2E rollback restored corpus07 published; corpus06 retained with 54 documents / 74 chunks. Citation verifier problems were empty; runtime confidential mutation, anon read and authenticated mutation were denied; six source notes preserved. Other stacks were stopped under explicit owner permission with volumes retained.