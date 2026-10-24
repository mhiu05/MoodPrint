"""Live Voyage relevance calibration on synthetic Vietnamese memories.

Uses the production VoyageProvider (one input per request, same parameters) and the
production lexical_rank. Reports ranking metrics and cosine distributions only; no
text from the provider is stored. Requires --live and a server-side VOYAGE_API_KEY.
"""

import argparse
import asyncio
import json
import math
import statistics
import time
from pathlib import Path

import httpx
from dotenv import dotenv_values
from pydantic import SecretStr

from app.ai.embedding_config import EmbeddingSettings
from app.ai.embeddings import lexical_rank
from app.ai.voyage import EmbeddingError, VoyageProvider

ROOT = Path(__file__).resolve().parent
DATASET = ROOT / "fixtures/memory_semantic_vi.json"


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


def ranking_metrics(ranked: list[list[str]], relevant: list[list[str]]) -> dict:
    hits1 = sum(r[0] in rel for r, rel in zip(ranked, relevant, strict=True))
    hits3 = sum(any(i in rel for i in r[:3]) for r, rel in zip(ranked, relevant, strict=True))
    mrr = 0.0
    for r, rel in zip(ranked, relevant, strict=True):
        mrr += next((1 / (k + 1) for k, i in enumerate(r) if i in rel), 0.0)
    n = len(ranked)
    return {"hit@1": round(hits1 / n, 3), "hit@3": round(hits3 / n, 3), "mrr": round(mrr / n, 3)}


async def run(output: Path, spacing: float) -> dict:
    env = dotenv_values(ROOT.parent / ".env")
    settings = EmbeddingSettings(
        semantic_memory_enabled=True,
        voyage_api_key=env.get("VOYAGE_API_KEY") or "",
        voyage_model=env.get("VOYAGE_MODEL") or "voyage-4-lite",
        voyage_dimensions=int(env.get("VOYAGE_DIMENSIONS") or 1024),
    )
    if not settings.semantic_memory_available:
        raise SystemExit("VOYAGE_API_KEY is not configured")
    data = json.loads(DATASET.read_text(encoding="utf-8"))
    usage = {"requests": 0, "tokens": 0, "failures": 0, "status": {}}
    latencies: list[float] = []

    async def record(response: httpx.Response):
        await response.aread()
        usage["requests"] += 1
        usage["status"][str(response.status_code)] = usage["status"].get(str(response.status_code), 0) + 1
        if response.status_code == 200:
            usage["tokens"] += response.json().get("usage", {}).get("total_tokens", 0)

    async with httpx.AsyncClient(event_hooks={"response": [record]}) as client:
        provider = VoyageProvider(settings, client=client)

        async def embed(text: str, kind: str) -> list[float]:
            for attempt in range(3):
                start = time.perf_counter()
                try:
                    vector = await provider.embed(text, kind)  # type: ignore[arg-type]
                    latencies.append((time.perf_counter() - start) * 1000)
                    await asyncio.sleep(spacing)
                    return vector
                except EmbeddingError:
                    usage["failures"] += 1
                    await asyncio.sleep(5 * (attempt + 1))
            raise SystemExit("Voyage failed three times for one input")

        docs = {m["id"]: await embed(m["text"], "document") for m in data["memories"]}
        queries = [await embed(q["text"], "query") for q in data["queries"]]
        negatives = [await embed(text, "query") for text in data["negatives"]]

        # Provider failure modes through the same adapter (no successful billing).
        bad_key = VoyageProvider(settings.model_copy(update={"voyage_api_key": SecretStr("invalid-key")}))
        # model_copy skips validation, so the real request runs with a 1 ms budget.
        slow = VoyageProvider(settings.model_copy(update={"voyage_timeout_seconds": 0.001}))
        failures = {}
        for name, candidate in (("invalidKey", bad_key), ("timeout", slow)):
            try:
                await candidate.embed("Tôi đọc sách", "query")
                failures[name] = "UNEXPECTED_SUCCESS"
            except EmbeddingError as error:
                failures[name] = str(error)

    ids = [m["id"] for m in data["memories"]]
    relevant = [q["relevant"] for q in data["queries"]]
    semantic_ranked, relevant_scores, best_irrelevant = [], [], []
    for q, vector in zip(data["queries"], queries, strict=True):
        scores = {i: cosine(vector, docs[i]) for i in ids}
        semantic_ranked.append(sorted(ids, key=lambda i: -scores[i]))
        relevant_scores.append(max(scores[i] for i in q["relevant"]))
        best_irrelevant.append(max(s for i, s in scores.items() if i not in q["relevant"]))
    negative_best = [max(cosine(v, docs[i]) for i in ids) for v in negatives]
    text_to_id = {m["text"]: m["id"] for m in data["memories"]}
    lexical_ranked = [
        [text_to_id[t] for t in lexical_rank([(i, m["text"]) for i, m in enumerate(data["memories"])], q["text"], len(ids))]  # type: ignore[misc]
        for q in data["queries"]
    ]

    def returned_at(threshold: float) -> dict:
        return {
            "queriesWithRelevantAboveThreshold": sum(s >= threshold for s in relevant_scores),
            "negativesReturningAnything": sum(s >= threshold for s in negative_best),
        }

    report = {
        "status": "PASS",
        "provider": "Voyage",
        "model": settings.voyage_model,
        "dimensions": settings.voyage_dimensions,
        "syntheticOnly": True,
        "counts": {"memories": len(ids), "queries": len(queries), "negatives": len(negatives)},
        "semantic": ranking_metrics(semantic_ranked, relevant),
        "lexical": ranking_metrics(lexical_ranked, relevant),
        "cosine": {
            "relevantMin": round(min(relevant_scores), 3),
            "relevantMedian": round(statistics.median(relevant_scores), 3),
            "bestIrrelevantMedian": round(statistics.median(best_irrelevant), 3),
            "negativeBestMax": round(max(negative_best), 3),
            "negativeBestMedian": round(statistics.median(negative_best), 3),
        },
        "thresholds": {str(t): returned_at(t) for t in (0.3, 0.35, 0.4, 0.45, 0.5)},
        "failureModes": failures,
        "usage": usage,
        "latencyMs": {
            "p50": round(statistics.median(latencies)),
            "p95": round(sorted(latencies)[int(0.95 * (len(latencies) - 1))]),
            "max": round(max(latencies)),
        },
    }
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Make real, billable Voyage calls")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--spacing", type=float, default=0.25, help="Seconds between requests")
    args = parser.parse_args()
    if not args.live:
        parser.error("--live is required; this runner has no fake fallback")
    if args.output.exists():
        parser.error("Refusing to overwrite existing evidence")
    report = asyncio.run(run(args.output, args.spacing))
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
