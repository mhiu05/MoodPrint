# Retrieval closure evaluation registration

Frozen final data: `benchmark_v3.jsonl`, SHA256 LF `ad457c367dd883eefe10b0b98e8efcbd69969a3ff59d73f03222432a18f8dc84`.

- 120 synthetic queries: 90 answerable (30 seeds, three correlated styles) and30 no-result. All14 subject areas represented; ambiguous descriptions, diacritic-free input, exact facts, legal jurisdiction, institutions and out-of-domain task collisions.
- Same coding agent created labels and support code. This is not unseen independent validation; final outcomes have not been consulted before this registration. Existing v2 test is already inspected and is regression evidence only.
- Development: v2 dev72, original corpus06. Initial support revision reduced recall from.8611 to.8278 through two scope false negatives. Root cause was missing regex token boundary (`theo phap luat` matched countryFrance) and treating general emergency-number queries as local directories. Paired regression tests fixed both; revision2 dev Recall@5.8611, no-result12/12. No similarity thresholds changed.
- Final corpus: `kb-20261109-07`, manifest `f5e14a3b96c14c8aed2ba3d144d29e680c52132861b18c470185a07e8343ffe8`,57documents/80chunks. It adds privacy/reporting/teacher responsibilities and no answer to the frozen unsupported scopes.
- Registered methods: historical topic-only score gate; evidence-support with locked defaults; evidence-support lexical-only, vector-only, hybridRRF and blend. `rerank-3` NOT_RUN (authorization only voyage-4). No method selection from final results; production stays vector-led locked scores plus support validation.
- Targets unchanged: Recall@5>=.80, no-result>=.90, citation integrity1.0. Report all other original metrics, precision, false-no-result and latency limits too, including failures. No rejecting nearly all positives.
- Final execution once per registered method. Any subsequent rerun is explicitly regression/reproducibility, not a new holdout. Labels never changed based on outcomes.
- Cached provider embeddings allowed; API calls only under existing original cumulative Voyage ledger, never a new ledger. Cached latency does not count as live latency validation. No OpenAI/model judge.
- Frozen labels have one primary answer-bearing document per positive query rather than full pooled multi-document relevance. Disclose this limit; v2 metrics provide the historical multi-label regression comparison. Bootstrap CIs are descriptive; correlated styles reduce effective sample size.
Freeze metadata correction before first evaluation: initial raw CRLF digest retained in freeze file; corrected to LF. Dataset rows/labels untouched.
