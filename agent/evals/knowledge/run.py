"""Retrieval benchmark. Query embeddings are cached; the holdout is scored once."""

from __future__ import annotations

import asyncio
import json
import os
import statistics
import sys
from dataclasses import replace
from pathlib import Path

from dotenv import dotenv_values
from moodprint_agent.knowledge.embedder import VoyageEmbedder
from moodprint_agent.knowledge.ingest.budget import commit, reserve, snapshot
from moodprint_agent.knowledge.retriever import PgVectorKnowledgeRetriever
from moodprint_shared.config import KnowledgeConfig
from moodprint_shared.contracts.errors import KnowledgeUnavailable
from moodprint_shared.contracts.knowledge import KnowledgeFilters, KnowledgeQuery, RetrievalScope
from moodprint_shared.env import get_settings
from sqlalchemy.ext.asyncio import create_async_engine

ROOT = Path(__file__).resolve().parents[3]
CASES = Path(__file__).parent / "cases" / "benchmark.jsonl"
sys.path.insert(0, str(Path(__file__).parent))
from metrics import mrr_at_k, ndcg_at_k, percentile, recall_at_k  # noqa: E402


class CachedEmbedder:
    def __init__(self, inner: VoyageEmbedder) -> None:
        self.inner = inner
        self.cache: dict[str, list[float]] = {}

    async def embed_query(self, text: str) -> list[float]:
        cached = self.cache.get(text)
        if cached is None:
            cached = await self.inner.embed_query(text)
            self.cache[text] = cached
        return cached


class OfflineEmbedder:
    async def embed_query(self, text: str) -> list[float]:
        del text
        raise KnowledgeUnavailable("lexical baseline", details={"reason": "embed_http"})


def load_cases() -> list[dict[str, object]]:
    return [
        json.loads(line) for line in CASES.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def ranked_documents(result_chunks: list[object]) -> list[str]:
    ordered: list[str] = []
    for chunk in result_chunks:
        document_id = str(chunk.citation.document_id)  # type: ignore[attr-defined]
        if document_id not in ordered:
            ordered.append(document_id)
    return ordered


async def score_split(
    retriever: PgVectorKnowledgeRetriever,
    cases: list[dict[str, object]],
    cfg: KnowledgeConfig,
) -> dict[str, float]:
    recalls: list[float] = []
    mrrs: list[float] = []
    ndcgs: list[float] = []
    no_result_hits = 0
    no_result_total = 0
    citation_ok = 0
    citation_total = 0
    latencies: list[float] = []
    for case in cases:
        result = await retriever.search(
            KnowledgeQuery(
                text=str(case["query"]),
                filters=KnowledgeFilters(languages=["vi"]),
                top_k=5,
            ),
            scope=RetrievalScope(request_id=str(case["id"])),
            timeout_s=cfg.timeout_s,
        )
        ranked = ranked_documents(list(result.chunks))
        latencies.append(float(result.latency_ms))
        for chunk in result.chunks:
            citation_total += 1
            citation = chunk.citation
            if citation.source_id and citation.document_id and citation.title:
                citation_ok += 1
        if case["no_result"]:
            no_result_total += 1
            if result.status == "no_results":
                no_result_hits += 1
            continue
        relevant = {str(item) for item in case["relevant"]}  # type: ignore[union-attr]
        recalls.append(recall_at_k(relevant, ranked, 5))
        mrrs.append(mrr_at_k(relevant, ranked, 5))
        ndcgs.append(ndcg_at_k({item: 1 for item in relevant}, ranked, 5))
    return {
        "recall_at_5": statistics.fmean(recalls) if recalls else 0.0,
        "mrr_at_5": statistics.fmean(mrrs) if mrrs else 0.0,
        "ndcg_at_5": statistics.fmean(ndcgs) if ndcgs else 0.0,
        "no_result_accuracy": no_result_hits / no_result_total if no_result_total else 0.0,
        "citation_integrity": citation_ok / citation_total if citation_total else 1.0,
        "latency_p50_ms": percentile(latencies, 0.50),
        "latency_p95_ms": percentile(latencies, 0.95),
        "cases": float(len(cases)),
    }


def choose_thresholds(
    dev_rows: list[tuple[float, float, dict[str, float]]],
) -> tuple[float, float]:
    best_recall = max(row[2]["recall_at_5"] for row in dev_rows)
    eligible = [row for row in dev_rows if row[2]["recall_at_5"] >= best_recall - 0.03]
    eligible.sort(key=lambda row: (row[2]["no_result_accuracy"], row[2]["ndcg_at_5"]), reverse=True)
    return eligible[0][0], eligible[0][1]


async def main() -> None:
    values = dotenv_values(ROOT / ".local/stacks/kb/test.env")
    database = values.get("TEST_ADMIN_DATABASE_URL")
    if not database:
        raise SystemExit("kb database is not bootstrapped")
    os.environ["TEST_ADMIN_DATABASE_URL"] = database
    cases = load_cases()
    dev = [case for case in cases if case["split"] == "dev"]
    holdout = [case for case in cases if case["split"] == "test"]
    secret = get_settings().voyage_api_key
    if secret is None:
        raise SystemExit("VOYAGE_API_KEY is not available")
    reservation = reserve(max(len({str(case["query"]) for case in cases}) * 16, 1))
    engine = create_async_engine(database, hide_parameters=True)
    voyage = VoyageEmbedder(secret.get_secret_value(), KnowledgeConfig())
    cached = CachedEmbedder(voyage)
    try:
        base = KnowledgeConfig()
        dev_rows: list[tuple[float, float, dict[str, float]]] = []
        for min_vector in (0.35, 0.45, 0.55):
            for min_lexical in (0.01, 0.05, 0.12, 0.2):
                cfg = replace(base, min_vector_score=min_vector, min_lexical_score=min_lexical)
                retriever = PgVectorKnowledgeRetriever(engine, cached, cfg)
                measured = await score_split(retriever, dev, cfg)
                dev_rows.append((min_vector, min_lexical, measured))
                print(
                    "dev",
                    min_vector,
                    min_lexical,
                    round(measured["recall_at_5"], 3),
                    round(measured["no_result_accuracy"], 3),
                )
        chosen_vector, chosen_lexical = choose_thresholds(dev_rows)
        print("chosen", chosen_vector, chosen_lexical)
        configs = {
            "lexical": (False, True, "rrf"),
            "vector": (True, False, "rrf"),
            "hybrid": (True, True, "rrf"),
            "blend": (True, True, "blend"),
        }
        report: dict[str, object] = {
            "corpus_version": "kb-20261109-03",
            "model": "voyage-4",
            "chosen_min_vector_score": chosen_vector,
            "chosen_min_lexical_score": chosen_lexical,
            "dev": [
                {"min_vector": vector, "min_lexical": lexical, **metrics}
                for vector, lexical, metrics in dev_rows
            ],
            "test": {},
        }
        test_report: dict[str, object] = {}
        for name, (use_vector, use_lexical, mode) in configs.items():
            cfg = replace(
                base,
                min_vector_score=chosen_vector,
                min_lexical_score=chosen_lexical,
                score_mode=mode,
            )
            embedder = cached if use_vector else OfflineEmbedder()
            retriever = PgVectorKnowledgeRetriever(
                engine,
                embedder,
                cfg,
                use_vector=use_vector,
                use_lexical=use_lexical,
            )
            test_report[name] = await score_split(retriever, holdout, cfg)
            print(name, test_report[name])
        report["test"] = test_report
        commit(reservation, voyage.usage.total_tokens)
        report["usage"] = {
            "calls": voyage.usage.calls,
            "tokens": voyage.usage.total_tokens,
            "usd": voyage.usage.usd,
            "ledger": snapshot(),
        }
        out = Path(__file__).parent / "results"
        out.mkdir(parents=True, exist_ok=True)
        (out / "phase2-voyage.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print("wrote", out / "phase2-voyage.json")
    except Exception:
        commit(reservation, None)
        raise
    finally:
        await voyage.aclose()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
