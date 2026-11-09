"""Benchmark v2 harness: pinned corpus version, plan section 7.5 metrics, bootstrap CIs, pooling.

    uv run python agent/evals/knowledge/run_v2.py --split dev --config hybrid --version kb-...
    uv run python agent/evals/knowledge/run_v2.py --pool --version kb-...   # label review aid

The harness connects with the admin loopback URL from .local/stacks/kb/test.env (never hosted),
pins ``scope.corpus_version`` so it never needs to publish, and caches query embeddings on disk
for these synthetic benchmark queries only (user queries are never cached by the product).
The ``test`` split is for one pre-registered run; do not tune on it.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import random
import statistics
import sys
import time
import tomllib
from dataclasses import asdict, replace
from pathlib import Path
from urllib.parse import urlparse

from dotenv import dotenv_values
from moodprint_agent.knowledge.embedder import VoyageEmbedder
from moodprint_agent.knowledge.ingest.budget import commit, reserve, snapshot
from moodprint_agent.knowledge.retriever import PgVectorKnowledgeRetriever
from moodprint_shared.config import KnowledgeConfig
from moodprint_shared.contracts.knowledge import KnowledgeFilters, KnowledgeQuery, RetrievalScope
from moodprint_shared.env import get_settings
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CASES = HERE / "cases" / "benchmark_v2.jsonl"
MANIFEST_DIR = ROOT / "agent" / "ingestion" / "corpus"
QUERY_CACHE = ROOT / ".local" / "eval-query-embeddings-v2.json"
RESULTS = HERE / "results"
sys.path.insert(0, str(HERE))
from metrics import hit_at_k, mrr_at_k, ndcg_at_k, percentile, recall_at_k  # noqa: E402

# name -> (KnowledgeConfig overrides, use_vector, use_lexical)
CONFIGS: dict[str, tuple[dict[str, object], bool, bool]] = {
    "lexical_v1": ({"min_lexical_score": 0.0, "min_vector_score": 0.0}, False, True),
    "vector_open": ({"min_lexical_score": 0.0, "min_vector_score": 0.0}, True, False),
    "hybrid_open": ({"min_lexical_score": 0.0, "min_vector_score": 0.0}, True, True),
    # The Phase 2 first-pass lock (dev-tuned on benchmark v1), kept as the v1 baseline.
    "hybrid_v1_locked": ({}, True, True),
    "vector_v1_locked": ({}, True, False),
    # Registered for the single test run (the plan's A, B, C and C'); rerank (D) is not run.
    "locked": ({}, True, True),
    "A_lexical_only": ({}, False, True),
    "B_vector_only": ({}, True, False),
    "C_hybrid_rrf": ({"lexical_weight": 1.0, "lexical_phrase_bonus": 0.15}, True, True),
    "Cprime_blend": ({"score_mode": "blend", "blend_vector_weight": 0.5}, True, True),
}


def lf_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def load_cases(split: str | None) -> list[dict[str, object]]:
    rows = [json.loads(x) for x in CASES.read_text(encoding="utf-8").splitlines() if x.strip()]
    return [row for row in rows if split in (None, "all", row["split"])]


class DiskCachedEmbedder:
    """Query embeddings for the synthetic benchmark, persisted so re-runs cost nothing."""

    def __init__(self, inner: VoyageEmbedder | None, model: str) -> None:
        self.inner = inner
        self.model = model
        self.cache: dict[str, list[float]] = {}
        if QUERY_CACHE.exists():
            self.cache = json.loads(QUERY_CACHE.read_text(encoding="utf-8"))
        self.dirty = False
        self.network_ms: list[float] = []

    async def embed_query(self, value: str) -> list[float]:
        key = f"{self.model}|{value}"
        hit = self.cache.get(key)
        if hit is None:
            if self.inner is None:
                raise RuntimeError("query embedding missing and live embedding is disabled")
            started = time.perf_counter()
            hit = await self.inner.embed_query(value)
            self.network_ms.append((time.perf_counter() - started) * 1000)
            self.cache[key] = hit
            self.dirty = True
        return hit

    def save(self) -> None:
        if self.dirty:
            QUERY_CACHE.parent.mkdir(parents=True, exist_ok=True)
            QUERY_CACHE.write_text(json.dumps(self.cache), encoding="utf-8")


def allow_hosts() -> set[str]:
    hosts: set[str] = set()
    for path in (MANIFEST_DIR / "sources").glob("*.toml"):
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
        if raw.get("url"):
            host = urlparse(str(raw["url"])).hostname
            if host:
                hosts.add(host.lower())
    return hosts


async def citation_ok(engine: AsyncEngine, version: str, chunk: object, hosts: set[str]) -> bool:
    cid = str(chunk.chunk_id)  # type: ignore[attr-defined]
    citation = chunk.citation  # type: ignore[attr-defined]
    async with engine.connect() as conn:
        row = (
            (
                await conn.execute(
                    text(
                        "select c.text, c.document_id, d.last_reviewed, d.language, d.country_scope,"
                        " s.source_id, d.primary_url, s.url as source_url, d.licence_class"
                        " from knowledge.chunks c join knowledge.documents d on"
                        " d.corpus_version=c.corpus_version and d.document_id=c.document_id"
                        " join knowledge.sources s on s.source_id=d.source_id"
                        " where c.corpus_version=:v and c.chunk_id=:c"
                    ),
                    {"v": version, "c": cid},
                )
            )
            .mappings()
            .first()
        )
    if row is None:
        return False
    if row["text"] != chunk.text:  # type: ignore[attr-defined]
        return False
    if row["document_id"] != citation.document_id or row["source_id"] != citation.source_id:
        return False
    if row["last_reviewed"] is None or row["language"] != "vi" or "VN" not in row["country_scope"]:
        return False
    if row["licence_class"] not in {"open_reuse", "authored"}:
        return False
    for raw in (row["primary_url"], row["source_url"]):
        if raw and (urlparse(str(raw)).hostname or "").lower() not in hosts:
            return False
    return bool(citation.title)


def doc_order(chunks: list[object]) -> list[str]:
    ordered: list[str] = []
    for chunk in chunks:
        doc = str(chunk.citation.document_id)  # type: ignore[attr-defined]
        if doc not in ordered:
            ordered.append(doc)
    return ordered


def bootstrap_ci(values: list[float], *, seed: int = 20261109, n: int = 1000) -> list[float]:
    if not values:
        return [0.0, 0.0]
    rng = random.Random(seed)
    means = sorted(statistics.fmean(rng.choice(values) for _ in values) for _ in range(n))
    return [round(means[int(0.025 * n)], 3), round(means[int(0.975 * n) - 1], 3)]


async def evaluate(
    engine: AsyncEngine,
    embedder: DiskCachedEmbedder,
    cases: list[dict[str, object]],
    version: str,
    cfg: KnowledgeConfig,
    *,
    use_vector: bool,
    use_lexical: bool,
    keep_outputs: bool = False,
) -> dict[str, object]:
    retriever = PgVectorKnowledgeRetriever(
        engine, embedder, cfg, read_role=None, use_vector=use_vector, use_lexical=use_lexical
    )
    hosts = allow_hosts()
    per: list[dict[str, object]] = []
    cite_ok = cite_total = 0
    for case in cases:
        query = KnowledgeQuery(
            text=str(case["text"]),
            filters=KnowledgeFilters(languages=["vi"]),
            top_k=10,
        )
        started = time.perf_counter()
        result = await retriever.search(
            query,
            scope=RetrievalScope(request_id=str(case["id"]), corpus_version=version),
            timeout_s=cfg.timeout_s,
        )
        latency = (time.perf_counter() - started) * 1000
        chunks = list(result.chunks)
        docs = doc_order(chunks)
        for chunk in chunks:
            cite_total += 1
            cite_ok += 1 if await citation_ok(engine, version, chunk, hosts) else 0
        grades = {r["document_id"]: int(r["grade"]) for r in case["relevant"]}  # type: ignore[union-attr]
        rel = set(grades)
        entry: dict[str, object] = {
            "id": case["id"],
            "style": case["style"],
            "topic": case["topic"],
            "answerable": case["answerable"],
            "gap": bool(case.get("gap")),
            "status": result.status,
            "latency_ms": latency,
            "top_docs": docs[:5],
        }
        if case["answerable"]:
            entry.update(
                hit5=hit_at_k(rel, docs, 5),
                recall5=recall_at_k(rel, docs, 5),
                recall10=recall_at_k(rel, docs, 10),
                mrr10=mrr_at_k(rel, docs, 10),
                ndcg10=ndcg_at_k(grades, docs, 10),
                p1=1.0 if docs and docs[0] in rel else 0.0,
                false_no_result=1.0 if result.status == "no_results" else 0.0,
            )
        else:
            entry["correct_no_result"] = 1.0 if result.status == "no_results" else 0.0
        if keep_outputs:
            entry["relevant"] = grades
        per.append(entry)

    def mean(key: str, items: list[dict[str, object]]) -> float:
        values = [float(e[key]) for e in items if key in e]  # type: ignore[arg-type]
        return round(statistics.fmean(values), 4) if values else float("nan")

    ans = [e for e in per if e["answerable"]]
    neg = [e for e in per if not e["answerable"]]
    lat = [float(e["latency_ms"]) for e in per]  # type: ignore[arg-type]
    summary: dict[str, object] = {
        "queries": len(per),
        "answerable": len(ans),
        "no_result_queries": len(neg),
        "hit_at_5": mean("hit5", ans),
        "recall_at_5": mean("recall5", ans),
        "recall_at_10": mean("recall10", ans),
        "mrr_at_10": mean("mrr10", ans),
        "ndcg_at_10": mean("ndcg10", ans),
        "precision_at_1": mean("p1", ans),
        "false_no_result_rate": mean("false_no_result", ans),
        "no_result_accuracy": mean("correct_no_result", neg),
        "no_result_correct": int(sum(float(e["correct_no_result"]) for e in neg)),  # type: ignore[arg-type]
        "no_result_gap_accuracy": mean("correct_no_result", [e for e in neg if e["gap"]]),
        "no_result_oos_accuracy": mean("correct_no_result", [e for e in neg if not e["gap"]]),
        "citation_integrity": round(cite_ok / cite_total, 4) if cite_total else 1.0,
        "citation_chunks_checked": cite_total,
        "latency_ms_p50_cached_embed": round(percentile(lat, 0.5), 1),
        "latency_ms_p95_cached_embed": round(percentile(lat, 0.95), 1),
        "ci95": {
            "recall_at_5": bootstrap_ci([float(e["recall5"]) for e in ans]),  # type: ignore[arg-type]
            "hit_at_5": bootstrap_ci([float(e["hit5"]) for e in ans]),  # type: ignore[arg-type]
            "no_result_accuracy": bootstrap_ci([float(e["correct_no_result"]) for e in neg]),  # type: ignore[arg-type]
        },
        "by_style": {
            style: {
                "n": len([e for e in ans if e["style"] == style]),
                "recall_at_5": mean("recall5", [e for e in ans if e["style"] == style]),
                "hit_at_5": mean("hit5", [e for e in ans if e["style"] == style]),
            }
            for style in sorted({str(e["style"]) for e in ans})
        },
        "by_topic_recall_at_5": {
            topic: mean("recall5", [e for e in ans if e["topic"] == topic])
            for topic in sorted({str(e["topic"]) for e in ans})
        },
    }
    return {"summary": summary, "per_query": per}


async def pool_review(engine: AsyncEngine, embedder: DiskCachedEmbedder, version: str) -> None:
    """Print, per query, top-5 documents from lexical, vector and hybrid that are not labelled."""
    cases = [c for c in load_cases("all") if c["answerable"]]
    titles: dict[str, str] = {}
    async with engine.connect() as conn:
        for row in (
            await conn.execute(
                text("select document_id, title from knowledge.documents where corpus_version=:v"),
                {"v": version},
            )
        ).mappings():
            titles[str(row["document_id"])] = str(row["title"])
    votes: dict[str, dict[str, int]] = {}
    for name in ("lexical_v1", "vector_open", "hybrid_open"):
        overrides, use_vector, use_lexical = CONFIGS[name]
        cfg = replace(KnowledgeConfig(), **overrides)  # type: ignore[arg-type]
        result = await evaluate(
            engine,
            embedder,
            cases,
            version,
            cfg,
            use_vector=use_vector,
            use_lexical=use_lexical,
            keep_outputs=True,
        )
        for entry in result["per_query"]:  # type: ignore[union-attr]
            top = entry["top_docs"][:3] if name != "lexical_v1" else entry["top_docs"][:3]
            tally = votes.setdefault(str(entry["id"]), {})
            for doc in top:
                tally[doc] = tally.get(doc, 0) + 1
    for case in cases:
        labelled = {r["document_id"] for r in case["relevant"]}  # type: ignore[union-attr]
        tally = votes.get(str(case["id"]), {})
        extra = sorted(doc for doc, n in tally.items() if n >= 2 and doc not in labelled)
        if extra:
            print(f"{case['id']} [{case['split']}] {case['text']}")
            print("   labelled:", ", ".join(sorted(labelled)))
            for doc in extra:
                print(f"   ? {doc} (votes {tally[doc]}) :: {titles.get(doc, '')}")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=["dev", "test", "all"], default="dev")
    parser.add_argument("--config", default="hybrid_open")
    parser.add_argument("--version", required=True)
    parser.add_argument("--pool", action="store_true")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--no-live", action="store_true", help="fail if an embedding is missing")
    args = parser.parse_args()

    values = dotenv_values(ROOT / ".local/stacks/kb/test.env")
    database = values.get("TEST_ADMIN_DATABASE_URL")
    if not database:
        raise SystemExit("kb database is not bootstrapped")
    if "127.0.0.1" not in str(database) and "localhost" not in str(database):
        raise SystemExit("refusing a non-loopback database")
    os.environ["TEST_ADMIN_DATABASE_URL"] = str(database)
    engine = create_async_engine(str(database), hide_parameters=True)
    base = KnowledgeConfig()
    voyage: VoyageEmbedder | None = None
    reservation: str | None = None
    if not args.no_live:
        secret = get_settings().voyage_api_key
        if secret is None:
            raise SystemExit("VOYAGE_API_KEY is not available")
        reservation = reserve(2000)
        voyage = VoyageEmbedder(secret.get_secret_value(), base)
    embedder = DiskCachedEmbedder(voyage, base.resolved_query_model())
    try:
        if args.pool:
            await pool_review(engine, embedder, args.version)
            return
        overrides, use_vector, use_lexical = CONFIGS[args.config]
        cfg = replace(base, **overrides)  # type: ignore[arg-type]
        cases = load_cases(args.split)
        result = await evaluate(
            engine,
            embedder,
            cases,
            args.version,
            cfg,
            use_vector=use_vector,
            use_lexical=use_lexical,
        )
        report = {
            "benchmark_sha256_lf": lf_sha256(CASES),
            "split": args.split,
            "config": args.config,
            "config_values": asdict(cfg),
            "use_vector": use_vector,
            "use_lexical": use_lexical,
            "corpus_version": args.version,
            "embedding_model": base.resolved_query_model(),
            **result,
        }
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
        sys.stdout.buffer.write(
            (json.dumps(report["summary"], ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        )
    finally:
        embedder.save()
        if reservation is not None:
            commit(reservation, voyage.usage.total_tokens if voyage else None)
        if voyage is not None:
            await voyage.aclose()
        await engine.dispose()
        print("ledger", snapshot(), file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
