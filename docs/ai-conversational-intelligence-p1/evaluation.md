# Real-model comparison

These are **12 new synthetic development conversations / 26 turns per arm**, not
reserved heldout cases and not production messages. Baseline is deployed P0
`5e73a130fd0f081887c3c2ab2093c43674388012`; final candidate application source is
`6da23ea1d151d0a67ff2ca06ec02f9391ec53300`. SDK 0.24.0, `gpt-6-luna`, 1,200 output
tokens, three SDK steps, 30-second model timeout, no retries, no provider storage
or tracing; each arm runs serially against its own guarded loopback PostgreSQL DB.
The model alias is mutable. Initial arms ran concurrently; the calibrated final
candidate ran later, so latency differences are not a controlled capacity result.

| Final observed metric | P0 baseline | Final P1 candidate |
| --- | ---: | ---: |
| Completed turns | 24/26 | 26/26 |
| Provider requests / responses with known usage | 30/30 | 30/30 |
| Observed deterministic privacy/numerical assertion failures | 0 | 0 |
| Objective intent assertion failures | 1 | 0 |
| Judge hard-gate flags | 0 | 0 |
| Factual accuracy, 1–5 | 5.000 | 5.000 |
| Multi-turn consistency | 4.458 | 4.750 |
| Relevance/usefulness | 4.208 | 4.583 |
| Intent alignment | 4.208 | 4.583 |
| Natural Vietnamese | 4.625 | 4.750 |
| Appropriate initiative | 4.125 | 4.500 |
| Persona differentiation | 4.542 | 4.625 |
| Tool correctness | 5.000 | 5.000 |
| Privacy/authorization wording | 5.000 | 5.000 |
| Uncertainty calibration | 5.000 | 4.833 |
| Turn latency p50 / p95, seconds | 2.475 / 4.060 | 3.869 / 9.305 |
| Input / cached / output tokens | 46,781 / 7,389 / 2,981 | 55,728 / 8,937 / 3,052 |
| Estimated arm cost, USD | 0.005504 | 0.006294 |

The two baseline failures occurred when a sharing scope was present but the user
explicitly wanted conversation or a topic change. The old private analysis schema
conflicted with answering without a mood read. The final candidate completed both
without a mood call. All authorized analysis turns still used current evidence;
no revoked canary or private mood note appeared in captured inputs after revocation.
These are observed assertions, not a universal hallucination-rate claim.

## Judging and independent review

The judge saw anonymous answer labels and actual permission state, verified mood
reads and approved-memory inputs. Three of twelve pairs were also scored with
reversed answer order. Case means are averaged before the overall mean, so repeated
pairs receive equal case weight. Maximum reversed-order score difference was one
point. The same model family judged its own outputs, and this small development
sample has not been independently human-reviewed. **No statistical significance
or general superiority is claimed.**

[Blinded human-review conversations](human-review-blind.md) contain the actual
complete conversation pairs; review before opening
[the separate label key](human-review-key.json). Failures remain visible. No human
review is claimed to have occurred.

## Preserved initial results and evaluator corrections

The initial candidate completed 26/26 turns but repeated one unstated sensory
detail and was too absolute about a message recipient's reaction. Two small persona
calibrations addressed those behaviors before the final run. Initial outputs and
scores remain in [live-candidate.json](live-candidate.json),
[live-judge.json](live-judge.json) and
[evaluation-summary-round1.json](evaluation-summary-round1.json).

One initial deterministic evaluator check required an unrequested mean to appear
in a focused comparison. The response omitted the mean and stated no false number.
That raw false assertion is retained; the initial summary records the objective
adjudication. The runner was corrected to validate a mean when stated, while all
existing F02 forged-number/evidence tests remain unchanged. The final run has zero
raw assertion failures. A first attempt to aggregate the final judge before its
file was complete failed read-only; aggregation was rerun only after completion.

The first judge also lacked the actual approved-memory text despite being told
that memory was authorized. It incorrectly penalized an authorized hobby reference.
The final judge receives that source text for both arms and no revoked memory for
later turns. No original score was overwritten or manually inflated.

## Usage, limits and release decision

The final comparison including its judge cost an estimated **USD 0.018466**.
All unique rounds—one baseline, two candidates and two judges—used **120 requests /
120 responses with known usage**, estimated **USD 0.031822**. Conservative reservations
were capped at USD 2 in total. Estimates use the repository's versioned
`openai-standard-2026-10-24` rates, not an invoice or a current pricing guarantee.
See [all-rounds usage](all-rounds-usage.json) and the unmodified raw reports.

**P1 release readiness: PARTIAL / HOLD.** Intent and completion improved in this
sample while privacy/number assertions remained intact. Uncertainty calibration
was slightly lower, and final latency was higher; these trade-offs must not be
hidden behind the other quality averages. Do not promote solely from these means.
Independent Vietnamese review, a larger untouched evaluation set and an interleaved
latency/cost comparison are recommended before a release decision. The implemented
branch is delivered only as a Draft PR, without merge or deployment.

## Reproduction

From `backend`, with a separately created loopback `*_test` DB in
`TEST_DATABASE_URL`, use the existing Python environment and the explicit local
credentials file argument; never put key values on the command line:

```text
python evals/conversation_live.py --live --runtime-root <verified-P0-checkout> --variant baseline --credentials-env <protected-env-path> --output <new-baseline.json>
python evals/conversation_live.py --live --runtime-root <P1-checkout> --variant candidate --credentials-env <protected-env-path> --output <new-candidate.json>
python -m evals.conversation_judge --live --inputs <baseline.json> <candidate.json> --credentials-env <protected-env-path> --output <new-judge.json>
python -m evals.conversation_report <report-directory> --candidate <candidate-filename> --judge <judge-filename>
```

The runners refuse existing output files and non-local/non-test databases, reserve
requests/tokens before network calls, and stop on unknown usage. The explicit
`historyLimit=1` stress case simulates truncation for both arms; production's normal
24-message/24,000-byte limits are unchanged.
