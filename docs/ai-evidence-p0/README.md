# Evidence-grounded conversational intelligence — P0 F01/F02/F04

26 October 2026, Asia/Bangkok. **Final status: PARTIAL**: implementation and observed
privacy/grounding regressions pass; the bounded live comparison demonstrates
improvements, but subjective quality and one disputed judge gate need human review.
This is a Draft integration change, not deployment approval.

## Integration and scope

Branch: `feat/evidence-grounded-conversation-p0`, based on F03 commit
`cd029216ca6a6b41378792b6decca187f65a24a7` from
[Draft PR #15](https://github.com/mhiu05/MoodPrint/pull/15). Remote refs were fetched
before branching. PR #15 was open/unmerged; both published verification jobs passed
when rechecked. The stacked PR targets `fix/ai-context-privacy-p0` while it remains
unmerged. The original `dev` checkout lacked F03, so it was not used as the base.

Existing worktrees and the pre-existing untracked `.worktrees/` were preserved.
`.gitignore`, historical personas/prompts, the existing reserved evaluation dataset,
hosted schemas and production data were not changed. No merge or deployment ran.

| Finding | Implemented behavior | Remaining boundary |
|---|---|---|
| F01 | Explicit backend source state in runtime instructions; short follow-ups retain mood intent; previous authorization is not claimed as a successful read. A visible re-share button restores selected dates only after a click, then requires Send. | No cross-turn snapshot reuse. Dates are local to the mounted conversation and are not restored from private transcripts after reload. |
| F02 | Typed, ephemeral evidence bound to owner/run/data version/range/expiry; backend statistics; private SDK plan instead of writable numerical claims in scoped turns. | Free-form unscoped dialogue is instruction-grounded, not a general semantic proof against every possible hallucination. |
| F04 | Description of actual records, limited first/last comparison, explicit missingness; no trend inference without a validated method. | No validated trend/causal method is enabled, even at three records. |
| Continuity | Bounded F03-safe context, latest corrections and resolved-request guidance; memory authorization metadata for the relevant bots. Mood instructions only reach Nhịp. | Privacy cutoffs can discard useful constraints; no unsafe reconstruction or automatic long-term memory. |

The optional reuse feature is **design only**, separately specified in
[conversation-reuse-proposal.md](conversation-reuse-proposal.md). It has no active
grant, migration, persistence or feature switch in this implementation.

## Runtime contract

`EvidenceEnvelope` in `backend/app/ai/evidence.py` contains identity/kind,
server-only owner/run/data-version binding, authorized dates, retrieval and expiry
times, source revisions, score observations, missing-day statistics, analytical
capabilities and `current_run_only` reuse. Owner/run binding is omitted from its
model projection. Notes are never selected. Successful empty retrieval differs
from absent authorization, unavailable tools and execution failure in `SourceState`.

The existing owner/date-scoped tool still takes `{}`; model prose cannot select an
owner or widen the date range. Its legacy keys remain, with a versioned `evidence`
projection added. `insightAvailable` is no longer a three-record inference switch
for this tool. The separate public mood dashboard contract is unchanged.

For explicitly scoped Nhịp turns, the SDK returns a private `MoodAnalysisPlan`:
`focus` selects overview/records/comparison/limits and `next_step` selects a bounded
optional suggestion, including none. Dates, means, counts, trends and free-form
claims are not writable fields. The backend constructs the public `AiOutput`
from verified observations. Malformed/forged plans and plans without a verified
read fail before final SSE. There is no global regex classifying ordinary numbers
as mood statistics. The trade-off is deliberately constrained language in scoped
data analysis; other conversations retain free-form responses and existing cards.

Description requires an actual observation. Comparison requires two actual
observations because a difference needs two operands, not because of an arbitrary
sufficiency threshold. Missing dates remain unknown. A difference between two
records is explicitly not a whole-week trend. Inference stays disabled because
there is no reviewed method, rather than assuming three days prove a pattern.

The runtime checks live policy before tools, before model calls and before final
persistence/emission. Envelope binding/expiry is checked before rendering and at
runtime return, then the envelope is cleared on every terminal path. Source edits,
deletion and consent changes retain F03's monotonic `data_version` fencing. This
relies on the existing mutation invariant; arbitrary administrative rewrites that
bypass versioning are outside the verified contract. No snapshot survives a run,
saved-chat reload or worker restart. Existing `text-v1`/`mood-turn-v1` projection,
24-message/24,000-byte history limit, legacy NULL handling and memory approval
boundaries remain intact. Accounting versions include `mood-evidence-v1`.

The public AiOutput, SSE version/order, API request schemas and generated frontend
contracts are unchanged. No dependency or database migration was added. F03's
existing migration 0015 remains a prerequisite for a future separately approved
rollout. The SDK use was checked against installed `openai-agents==0.24.0` and
[official typed-output guidance](https://developers.openai.com/api/docs/guides/agents/define-agents).

## Executed verification

Python commands used `backend/.venv/Scripts/python.exe`, with Ruff/mypy from
`backend/`; frontend commands used `npm.cmd` or the direct installed Playwright
CLI. All database tests targeted dedicated loopback PostgreSQL `*_test` databases.
Credentials stayed in process environment and were not copied into reports.
Synthetic credential-shaped DSNs in parameterized JUnit test identifiers were
redacted before committing the artifacts; test outcomes/counts are unchanged.

| Command actually executed | Observed outcome |
|---|---|
| `python -m pytest tests/test_context_privacy.py tests/test_context_selection.py tests/test_scoped_mood_tool.py tests/test_sdk_adapter.py -q --tb=short` before implementation | Baseline **49 passed** |
| `python -m pytest -q --tb=short --junitxml=../docs/ai-evidence-p0/backend-tests-final.xml` | Intermediate full run **593 passed**, exit 0 |
| `python -m pytest -q --tb=short --junitxml=../docs/ai-evidence-p0/backend-tests-release.xml` | Final full collection **598 passed**, 566.68 seconds, exit 0; no failures/skips or teardown errors |
| `python -m pytest tests/test_evidence_eval_preparation.py tests/test_mood_evidence.py tests/test_sdk_adapter.py -q --tb=short` | **46 passed**, including the two eval-preparation tests added after the final full-suite collection |
| `python -m pytest tests/test_context_privacy.py tests/test_context_privacy_migration.py tests/test_mood_evidence.py tests/test_mood_evidence_runtime.py tests/test_evidence_eval_preparation.py -q --tb=short --junitxml=../docs/ai-evidence-p0/privacy-evidence-regressions.xml` | **61 passed**, 83.45 seconds, exit 0; includes all 22 inherited F03 cases and the two later eval-preparation tests |
| `python -m ruff check app tests evals alembic ../scripts/load_chat_memory.py ../scripts/apply_supabase_review.py ../scripts/test_supabase_fullstack.py ../scripts/load_social_mood.py ../scripts/test_fullstack.py` | All checks passed |
| `python -m mypy app` | **88 source files**, no issues |
| `python -m alembic upgrade head`; `python -m alembic check` | Dedicated local migration DB upgraded through 0015; no new upgrade operations/ORM drift |
| `python ../scripts/export_openapi.py`; `npm.cmd run contracts:generate`; contract `git diff --exit-code` | Exit 0; no public schema drift |
| `npm.cmd run typecheck`; `npm.cmd test`; `npm.cmd run build` | Passed; **54 frontend unit tests**; production bundle built |
| `node node_modules/@playwright/test/cli.js test tests/e2e/real.spec.ts tests/e2e/chat-history.spec.ts --reporter=line` | **33 passed**, mocked HTTP coverage |
| `python ../scripts/test_fullstack.py mood-evidence.spec.ts local-mvp.spec.ts chat-history.spec.ts` | **4 passed** with the standard CI harness: real local HTTP/API/PostgreSQL/SDK, synthetic model; new desktop/mobile/keyboard/axe journeys plus existing five-agent persistence and saved-history journeys |

Coverage includes the fixed 20–26 October three-turn incident; both explicitly
re-shared and unauthorized follow-ups; 0/1/2/3 records; missing days; forged means,
counts, dates and trends; owner/run/range/expiry/cancellation binding; source edits
and deletion; read failures; consent revoke/regrant; saved conversations; process
and worker restoration; and the inherited F03 derivative/copy-chain regressions.
Synthetic assertions capture actual SDK model inputs. Browser screenshots were
visually inspected and are not included in the commit.

The standard full-stack synthetic model now supports the private mood plan while
preserving its earlier generic replies. The new spec uses dedicated actors 47–48
and runs with the default harness, so CI discovery does not require a special server.

Earlier failures were not counted as PASS: an exception-code assertion initially
matched a message instead of `DomainError.code`; five full-suite prompt assertions
needed the new runtime suffix; the initial full-stack fixture selected an
ineligible actor and expected an empty composer to be enabled; axe exposed existing
heading-order and roster-label mismatches, which were fixed without disabling rules.
A card selector accidentally changed with the roster selector was restored. The
final replacement commands above completed successfully where stated.

## Real-model comparison

The new `backend/evals/fixtures/evidence_p0_cases.json` has 12 synthetic conversations,
25 turns, all five agents, memory revocation, source correction, restart, sparse
records, prose-only permission and the incident with/without re-sharing. No reserved
heldout case was read for tuning. Selected historical prompts are byte-frozen in
`evidence_p0_baseline.json`; baseline execution used the unchanged F03 worktree.

Executed `evals/evidence_live.py --live --runtime-root <checkout> --variant
baseline|candidate --output <new-file>` for baseline, initial candidate and final
candidate. Both comparison arms used `gpt-6-luna`, SDK 0.24.0, concurrency 1,
1,200 output tokens, max 3 turns, 30-second timeout, no retries, no provider storage
and disabled tracing. Each arm reserved at most 60 requests/1,000,000 conservative
token units before calls. Judging reserved at most 15 requests/500,000 units per
batch, with one explicit failed-case repair. Total budget stayed below $2 at the
repository's versioned rate snapshot. There was no fake fallback.

The initial live round exposed unrelated mood guidance priming Mây after memory
revocation; the final candidate limits mood-specific instructions to Nhịp. The
same frozen cases were rerun. Initial results remain in the report directory.

`python -m evals.evidence_judge --live --inputs <baseline> <candidate> --output
<new-file>` scored blinded whole conversations and reversed order for 3/12 cases.
The final judge received actual retrieved date ranges/statistics, correcting an
earlier evaluator omission that penalized a truthful year. Both arms received the
same evidence conditions. `python -m evals.evidence_report ../docs/ai-evidence-p0`
rebuilds the metrics and [human-review examples](human-review-examples.md) offline.

| Final observed metric | F03 baseline | Candidate |
|---|---:|---:|
| Completed turns | 25/25 | 25/25 |
| Missed authorized mood reads | 2 | 0 |
| Runtime deterministic assertion failures | 2 | 0 |
| Provider requests with known usage | 33/33 | 35/35 |
| Input / cached-input / output tokens | 46,331 / 12,022 / 2,938 | 63,356 / 18,582 / 3,572 |
| Estimated model cost, USD | 0.005020 | 0.006449 |
| Turn latency p50 / p95, seconds | 5.217 / 22.897 | 3.694 / 10.613 |
| Blinded factual accuracy, 1–5 | 4.750 | 4.917 |
| Multi-turn consistency | 4.333 | 4.500 |
| Relevance/usefulness | 4.167 | 4.500 |
| Tool correctness | 4.667 | 5.000 |
| Natural Vietnamese | 4.750 | 4.667 |
| Appropriate initiative | 3.583 | 3.917 |
| Uncertainty calibration | 4.583 | 4.750 |
| Persona differentiation | 4.083 | 4.333 |
| Raw judge privacy score | 4.667 | 4.667 |

The final comparison including judging cost an estimated **$0.021192**. All live
rounds including the initial candidate/judges cost **$0.037196 in known usage**.
An initial judge schema failure has unknown token usage and is excluded from that
known-cost estimate; its conservative reservation was retained. Costs use
`openai-standard-2026-10-24` rates, not an invoice or a fresh pricing guarantee.

Do not treat the quality means as statistical significance: this is one small,
sequential, non-interleaved sample using a mutable model alias and the same model
as judge. Reversed-order scores differed by up to two points. Natural Vietnamese
slightly declined. No independent human review has occurred.

The raw judge flagged **both** arms' `P0-MAY-REVOKED-MEMORY` first turn for memory
use with mood `scope=false`. That conflates two permissions: the fixture explicitly
enables MEM and approves that synthetic memory before turn 1, then revokes MEM
before turn 2. SDK captures show no revoked source replay on turn 2. These flags
and original scores are retained, not silently converted to PASS. They require
independent adjudication; they are not evidence of an observed F03 replay failure.

## Limits and release decision

Implementation/privacy/contract checks: **PASS where observed**. Overall delivery:
**PARTIAL**, pending independent review of the judge dispute and conversational
examples. No claim of production incident reconstruction or universal hallucination
elimination is made. Scoped analysis is intentionally less expressive; unscoped
answers still rely on runtime instructions and the existing guardrails. Tool
failures continue to use the existing public failure classification, which can
remain generic. Conversation-scoped reuse and validated trend inference remain
separate future work. Hosted migration, deployment and production testing were
outside authorization and were not executed.
