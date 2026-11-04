# Journal retrieval evaluation

Forty synthetic Vietnamese entries across 56 days, fifteen labelled queries:
five literal, six paraphrases and four emotion patterns. No real journal data.
The same SQL hybrid search is compared with keyword/recent fallback at six results.
Recall@6 is the fraction of labelled relevant entries returned; MRR@6 uses the
first relevant result. Latency includes query embedding and SQL, not indexing.

Prepare an owned local disposable `_test` database with schema 0029 and use its
session `TEST_DATABASE_URL`, `MOODPRINT_TEST_RUN_ID` and `APP_ENV=test`. Then:

```powershell
uv run --locked python -m evals.journal_retrieval.run --embedder fake --out ../.tmp/journal-retrieval
uv run --locked pytest -q tests/test_journal_retrieval_eval.py
```

The runner validates local host, disposable ownership and marker before inserting.
It creates one synthetic user and deletes only that user in cleanup. Settings use
`_env_file=None`; no application `.env` is read. No dependency is added.

Fake embeddings use deterministic token hashes and a small synonym dictionary.
Passing fake recall proves pipeline behavior, **not real semantic quality**.
Report results separately by query group, without rounding away failures.

The optional `--embedder voyage --confirm-cost` requires a key supplied explicitly
in the process environment, prior cost approval and a current pricing review.
It makes 55 calls. This implementation session runs **fake only**; live Voyage
and retrieval quality remain unverified. No hosted database is supported.
