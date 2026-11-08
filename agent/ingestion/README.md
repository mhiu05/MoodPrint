# Knowledge ingestion

Chạy từ gốc repo:

```powershell
uv run python -m moodprint_agent.knowledge.ingest plan --manifest agent/ingestion/corpus/manifest.toml
uv run python -m moodprint_agent.knowledge.ingest build --manifest agent/ingestion/corpus/manifest.toml --out .local/corpus/build-1
uv run python -m moodprint_agent.knowledge.ingest seed-synthetic --target test-env
```

`--target test-env` chỉ nhận database loopback. Không có đích hosted. Voyage chỉ chạy khi có `.local/eval-budget.json` và khóa do owner cấp.
