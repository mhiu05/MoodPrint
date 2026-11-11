"""Reproducible closure benchmark; cached embeddings by default, never a paid judge.

The old v2 set is inspected development/regression evidence. V3 is a self-authored
frozen final set, not independent validation. No label is modified by this runner.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

from dotenv import dotenv_values
from safevoice_agent.knowledge.embedder import VoyageEmbedder
from safevoice_agent.knowledge.ingest.budget import commit, reserve, snapshot
from safevoice_agent.knowledge.retriever import PgVectorKnowledgeRetriever
from safevoice_agent.knowledge.scoring import RawHit, score_hits
from safevoice_shared.config import KnowledgeConfig
from safevoice_shared.contracts.knowledge import KnowledgeQuery, RetrievalScope
from safevoice_shared.knowledge_support import VERSION, assess_support
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_v2 as benchmark  # noqa: E402


class TopicOnlyRetriever(PgVectorKnowledgeRetriever):
    """Historical score gate, solely for the registered experiment comparator."""

    def _supported_hits(self, query: KnowledgeQuery, hits: list[RawHit]) -> list[RawHit]:
        return hits


def source_identity() -> dict[str, str]:
    root = benchmark.ROOT
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    paths = [
        *sorted((root / "agent/src").rglob("*.py")),
        *sorted((root / "shared/src").rglob("*.py")),
        Path(__file__).resolve(),
    ]
    h = hashlib.sha256()
    for path in paths:
        h.update(str(path.relative_to(root)).replace("\\", "/").encode())
        h.update(path.read_bytes().replace(b"\r\n", b"\n"))
    return {"source_sha": sha, "source_tree_sha256": h.hexdigest()}


async def run(args: argparse.Namespace) -> dict[str, object]:
    benchmark.CASES = args.cases
    benchmark.QUERY_CACHE = args.query_cache
    cases = benchmark.load_cases(args.split)
    if args.freeze:
        frozen = json.loads(args.freeze.read_text(encoding="utf-8"))
        if frozen["sha256_lf"] != benchmark.lf_sha256(args.cases):
            raise ValueError("frozen dataset digest mismatch")
    values = dotenv_values(args.env_file)
    database = values.get("TEST_ADMIN_DATABASE_URL")
    if not database or make_url(database).host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("only an explicitly configured loopback database is allowed")
    engine = create_async_engine(database, hide_parameters=True)
    cfg = KnowledgeConfig()
    embedder = benchmark.DiskCachedEmbedder(None, cfg.resolved_query_model())
    live: VoyageEmbedder | None = None
    reservation: str | None = None
    if args.live_embeddings:
        if (
            not args.ledger
            or not args.ledger.is_file()
            or not args.ledger.with_suffix(".jsonl").is_file()
        ):
            raise ValueError("existing cumulative Voyage ledger and log are required")
        authorization = json.loads(args.ledger.read_text(encoding="utf-8"))
        if (
            authorization.get("model") != "voyage-4"
            or authorization.get("scope") != "phase-2-voyage"
        ):
            raise ValueError("Voyage authorization scope/model mismatch")
        secrets = dotenv_values(args.key_file)
        key = secrets.get("VOYAGE_API_KEY")
        if not key:
            raise ValueError("Voyage key is unavailable; no call made")
        reservation = reserve(
            sum(len(str(c["text"]).encode("utf-8")) + cfg.query_max_chars * 4 for c in cases) * 5,
            ledger=args.ledger,
        )
        live = VoyageEmbedder(key, cfg)
        embedder.inner = live
    try:
        async with engine.connect() as conn:
            corpus = (
                (
                    await conn.execute(
                        text(
                            "select version,manifest_sha256,embedding_model from knowledge.corpus_versions where version=:v"
                        ),
                        {"v": args.version},
                    )
                )
                .mappings()
                .one()
            )
            sizes = (
                (
                    await conn.execute(
                        text(
                            "select (select count(*) from knowledge.documents where corpus_version=:v) as documents, (select count(*) from knowledge.chunks where corpus_version=:v) as chunks"
                        ),
                        {"v": args.version},
                    )
                )
                .mappings()
                .one()
            )
        if corpus["embedding_model"] != "voyage-4":
            raise ValueError("quality run requires the pinned real Voyage corpus")
        if args.manifest_sha and corpus["manifest_sha256"] != args.manifest_sha:
            raise ValueError("pinned corpus digest mismatch")
        methods: dict[str, object] = {}
        names = args.methods.split(",")
        for name in names:
            if name == "topic_only":
                overrides, use_vector, use_lexical = benchmark.CONFIGS["locked"]
                cls = TopicOnlyRetriever
            else:
                overrides, use_vector, use_lexical = benchmark.CONFIGS[name]
                cls = PgVectorKnowledgeRetriever
            result = await benchmark.evaluate(
                engine,
                embedder,
                cases,
                args.version,
                replace(cfg, **overrides),
                use_vector=use_vector,
                use_lexical=use_lexical,
                keep_outputs=True,
                retriever_type=cls,
            )
            result["summary"]["false_result_rate"] = round(
                1.0 - result["summary"]["no_result_accuracy"], 4
            )
            methods[name] = result
        diagnosis = []
        retriever = PgVectorKnowledgeRetriever(engine, embedder, cfg, read_role=None)
        for case in cases:
            if case["answerable"]:
                continue
            query = KnowledgeQuery(text=str(case["text"]), top_k=10)
            collected = await retriever.collect(
                query, RetrievalScope(request_id=str(case["id"]), corpus_version=args.version)
            )
            hits = [] if collected is None else collected.hits
            ranked = score_hits(hits, cfg, top_k=5)
            diagnosis.append(
                {
                    "id": case["id"],
                    "query": case["text"],
                    "expected": "no_results",
                    "baseline_status": "ok" if ranked else "no_results",
                    "candidates": [
                        {
                            "document_id": h.document_id,
                            "chunk_id": h.chunk_id,
                            "text": h.text,
                            "vector_score": h.vector_score,
                            "lexical_score": h.lexical_score,
                            "rank_score": h.score,
                            "support": assess_support(query.text, h).supported,
                            "reason": assess_support(query.text, h).reason,
                        }
                        for h in ranked
                    ],
                }
            )
        return {
            **source_identity(),
            "benchmark_sha256_lf": benchmark.lf_sha256(args.cases),
            "split": args.split,
            "data_provenance": "self-authored synthetic; not independent; v2 already inspected; v3 correlated styles disclosed in freeze",
            "corpus": dict(corpus),
            "corpus_sizes": dict(sizes),
            "support_version": VERSION,
            "config_values": benchmark.asdict(cfg),
            "methods": methods,
            "no_result_diagnosis": diagnosis,
            "embedding_calls_this_run": live.usage.calls if live else 0,
            "embedding_tokens_this_run": live.usage.total_tokens if live else 0,
            "latency_scope": "database + scoring with cached embeddings; provider latency is separate and not a live latency pass",
            "provider_network_ms": embedder.network_ms,
        }
    finally:
        embedder.save()
        if reservation is not None:
            commit(reservation, live.settlement_tokens if live else None, ledger=args.ledger)
        if live:
            await live.aclose()
        await engine.dispose()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cases", type=Path, default=benchmark.CASES)
    p.add_argument("--freeze", type=Path)
    p.add_argument("--split", choices=["dev", "test", "all"], default="dev")
    p.add_argument("--version", required=True)
    p.add_argument("--manifest-sha")
    p.add_argument("--env-file", type=Path, default=Path(".local/stacks/int/test.env"))
    p.add_argument("--query-cache", type=Path, default=benchmark.QUERY_CACHE)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument(
        "--methods",
        default="topic_only,locked,A_lexical_only,B_vector_only,C_hybrid_rrf,Cprime_blend",
    )
    p.add_argument("--live-embeddings", action="store_true")
    p.add_argument("--ledger", type=Path)
    p.add_argument("--key-file", type=Path, default=Path(".env"))
    args = p.parse_args()
    report = asyncio.run(run(args))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v["summary"] for k, v in report["methods"].items()}, ensure_ascii=True))
    if args.ledger:
        print(json.dumps({"voyage_ledger": snapshot(args.ledger)}))


if __name__ == "__main__":
    main()
