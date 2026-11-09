# Benchmark v2: how it was built and what it is not

Frozen before any retrieval tuning on corpus `kb-20261109-04` (`benchmark_v2.jsonl`, LF SHA-256
in `benchmark_v2.summary.json`). Rebuild with `uv run python agent/evals/knowledge/cases/build_v2.py`.

## Method

- 150 answerable and 30 no-result Vietnamese queries, written from the information needs of the
  14 core topics, in five styles (standard, slang, narrative, English-mixed, no-diacritics).
  13 no-diacritic queries are machine-stripped copies of written queries; 24 were typed by hand.
- 10 of the 30 no-result queries are *in-domain gaps* (penalty amounts, age of criminal
  responsibility, a named school's rules, other countries' law, local directories, medical
  advice). Several of the 20 out-of-scope queries are lexical traps that reuse a corpus word
  ("đánh bóng bàn", "chặn quảng cáo", "báo cáo môn hóa", "bắt cá").
- Labels are graded per document: 2 answers the need directly, 1 helps in part.
- Split is stratified by topic and style with largest-remainder apportionment and a fixed seed:
  dev 60 + 12, test 90 + 18. Every topic appears in both splits. (Benchmark v1 split by topic:
  dev and test shared only one topic, so thresholds were tuned on different material.)
- Pooled review: before freezing, the top-3 documents of lexical-only, vector-only and hybrid
  runs were pooled and every unlabelled document that at least two systems agreed on was read
  against the query. 133 of 150 queries had such a candidate; 30 grade-1 labels were added for
  27 queries (for example the legal excerpt for a "what counts as bullying" query). The other
  candidates were judged not relevant.

## What this is not

- **Not independent.** The same coding agent wrote the corpus, the queries and the labels, so
  results here can be optimistic. No human reviewed any label.
- **No blind second labelling pass.** Plan section 7.3 asks for a 20 percent blind relabel with
  an agreement score. It was not done; the pooled-vote review above replaced it and a
  same-session recheck would not be blind. Label agreement is therefore unmeasured.
- Candidates with fewer than two system votes were not reviewed, so some relevant documents may
  be unlabelled. That makes Recall@5 slightly pessimistic, not optimistic.
- Style counts differ from the plan's 50/35/30/25/10 (actual: standard 46, no-diacritic 37,
  slang 27, narrative 25, English 15).
- Benchmark v1 (`benchmark.jsonl`, hash `0bedae78…19eb` after line-ending normalisation) and its
  results stay in the repository as diagnostic history. Its labels were whole-topic clusters of
  near-duplicate cards and cannot support an acceptance claim.

The `test` split is for one pre-registered run of the final configuration. Do not tune on it.
