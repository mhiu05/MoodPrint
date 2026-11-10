"""Fresh-provider latency only: frozen every-sixth case, five warmups, three repeats."""

import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from evals.real_knowledge import factory
from moodprint_shared.config import AppConfig
from moodprint_shared.contracts.knowledge import KnowledgeQuery, RetrievalScope


def cases_to_measure():
    return [
        json.loads(line)
        for line in Path("agent/evals/knowledge/cases/benchmark_v3.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ][::6]


async def measure(cases):
    cfg = AppConfig()
    records = []
    async with factory(cfg, "kb-20261109-07") as retriever:
        for case in cases[:5]:
            await retriever.search(
                KnowledgeQuery(text=case["text"]),
                scope=RetrievalScope(request_id="latency-warm", corpus_version="kb-20261109-07"),
                timeout_s=15,
            )
        for repeat in range(1, 4):
            for case in cases:
                start = time.perf_counter()
                result = await retriever.search(
                    KnowledgeQuery(text=case["text"]),
                    scope=RetrievalScope(
                        request_id="latency-measure", corpus_version="kb-20261109-07"
                    ),
                    timeout_s=15,
                )
                records.append(
                    dict(
                        id=case["id"],
                        repeat=repeat,
                        latency_ms=(time.perf_counter() - start) * 1000,
                        status=result.status,
                    )
                )
        usage = retriever.embedder.inner.usage
        tokens, calls = usage.total_tokens, usage.calls
    lat = sorted(r["latency_ms"] for r in records)
    result = dict(
        scope="fresh live Voyage embeddings + authenticated PostgreSQL + evidence support; synthetic frozen every-sixth case; not another quality holdout",
        cases=len(cases),
        warmups=5,
        repeats=3,
        measurements=len(records),
        p50_ms=statistics.median(lat),
        p95_ms=lat[int(0.95 * (len(lat) - 1))],
        provider_calls_including_warmups=calls,
        tokens=tokens,
        records=records,
    )
    return result


def main():
    result = asyncio.run(measure(cases_to_measure()))
    out = Path("agent/evals/knowledge/results/closure-latency-v3.json")
    import hashlib
    import subprocess

    result["source_sha"] = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    result["support_sha256_lf"] = hashlib.sha256(
        Path("shared/src/moodprint_shared/knowledge_support.py")
        .read_bytes()
        .replace(b"\r\n", b"\n")
    ).hexdigest()
    result["corpus_version"] = "kb-20261109-07"
    result["corpus_sha256"] = "f5e14a3b96c14c8aed2ba3d144d29e680c52132861b18c470185a07e8343ffe8"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "records"}))


if __name__ == "__main__":
    main()
