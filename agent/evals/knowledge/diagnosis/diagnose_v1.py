"""Read-only diagnosis of the Phase 2 holdout failure (corpus kb-20261109-03, benchmark v1).

It does not tune anything. It measures: template duplication, boilerplate share, the label
design, why lexical passes off-topic queries, and how separable answerable and no-result
queries are by raw score. Output: results/diagnosis-v1.json. Costs a few cents of Voyage
tokens at most (query embeddings are cached on disk for the benchmark only).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import re
import statistics
import sys
from collections import Counter
from itertools import combinations
from pathlib import Path

from dotenv import dotenv_values
from safevoice_agent.knowledge.embedder import VoyageEmbedder
from safevoice_agent.knowledge.ingest.budget import commit, reserve
from safevoice_agent.knowledge.query import STOPWORDS, lexical_tokens, prepare_query
from safevoice_agent.knowledge.retriever import _LEXICAL_SQL, _VECTOR_SQL, _vector_literal
from safevoice_shared.config import KnowledgeConfig
from safevoice_shared.env import get_settings
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent))
from metrics import hit_at_k, percentile, recall_at_k  # noqa: E402

VERSION = "kb-20261109-03"
CASES = HERE.parent / "cases" / "benchmark.jsonl"
CACHE = ROOT / ".local" / "eval-query-embeddings.json"


def lf_sha256(path: Path) -> str:
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def shingles(value: str, n: int = 5) -> set[str]:
    words = re.findall(r"\w+", value.casefold())
    return {" ".join(words[i : i + n]) for i in range(max(0, len(words) - n + 1))}


def auc(positives: list[float], negatives: list[float]) -> float:
    """P(score of a random answerable query > score of a random no-result query)."""
    if not positives or not negatives:
        return float("nan")
    wins = 0.0
    for p in positives:
        for q in negatives:
            wins += 1.0 if p > q else 0.5 if p == q else 0.0
    return wins / (len(positives) * len(negatives))


def load_cache() -> dict[str, list[float]]:
    if CACHE.exists():
        return json.loads(CACHE.read_text(encoding="utf-8"))
    return {}


async def main() -> None:
    values = dotenv_values(ROOT / ".local/stacks/kb/test.env")
    database = values["TEST_ADMIN_DATABASE_URL"]
    os.environ["TEST_ADMIN_DATABASE_URL"] = str(database)
    cases = [json.loads(x) for x in CASES.read_text(encoding="utf-8").splitlines() if x.strip()]
    engine = create_async_engine(str(database), hide_parameters=True)
    cfg = KnowledgeConfig()
    out: dict[str, object] = {
        "corpus_version": VERSION,
        "benchmark_lf_sha256": lf_sha256(CASES),
        "benchmark_cases": len(cases),
    }

    async with engine.connect() as conn:
        await conn.execute(text("set local search_path = public, extensions"))
        rows = (
            (
                await conn.execute(
                    text(
                        "select c.chunk_id, c.document_id, c.text, d.topics, d.title "
                        "from knowledge.chunks c join knowledge.documents d "
                        "on d.corpus_version=c.corpus_version and d.document_id=c.document_id "
                        "where c.corpus_version=:v order by c.chunk_id"
                    ),
                    {"v": VERSION},
                )
            )
            .mappings()
            .all()
        )
        chunks = [dict(r) for r in rows]
        doc_ids = {c["document_id"] for c in chunks}

        # 1. label audit
        by_topic: dict[str, set[str]] = {}
        for chunk in chunks:
            for topic in chunk["topics"]:
                by_topic.setdefault(topic, set()).add(chunk["document_id"])
        label_missing = sorted(
            {doc for case in cases for doc in case["relevant"] if doc not in doc_ids}
        )
        rel_sizes = Counter(len(case["relevant"]) for case in cases if not case["no_result"])
        split_topics = {
            split: sorted({c["topic"] for c in cases if c["split"] == split and not c["no_result"]})
            for split in ("dev", "test")
        }
        out["labels"] = {
            "relevant_doc_ids_missing_from_corpus": label_missing,
            "relevant_set_size_histogram": dict(rel_sizes),
            "labels_are_whole_topic_clusters": all(
                set(case["relevant"]) == by_topic.get(case["topic"], set())
                or case["topic"] == "definition"
                or case["topic"] == "evidence"
                for case in cases
                if not case["no_result"]
            ),
            "split_topics": split_topics,
            "topics_in_both_splits": sorted(set(split_topics["dev"]) & set(split_topics["test"])),
            "has_style_field": any("style" in c for c in cases),
            "no_result_queries_are_in_domain": 0,
        }

        # 2. template duplication
        sets = [shingles(c["text"]) for c in chunks]
        near = 0
        pair_n = 0
        max_j: list[float] = []
        for i, a in enumerate(sets):
            best = 0.0
            for j, b in enumerate(sets):
                if i == j or not a or not b:
                    continue
                inter = len(a & b)
                score = inter / (len(a) + len(b) - inter)
                best = max(best, score)
            max_j.append(best)
        for (_i, a), (_j, b) in combinations(list(enumerate(sets)), 2):
            if a and b:
                pair_n += 1
        near = sum(1 for v in max_j if v >= 0.5)
        sentence_df: Counter[str] = Counter()
        for chunk in chunks:
            seen = {
                s.strip().casefold()
                for s in re.split(r"(?<=[.!?])\s+", chunk["text"])
                if len(s.strip()) > 30
            }
            sentence_df.update(seen)
        common = [(s, n) for s, n in sentence_df.most_common(6) if n >= 20]
        chunk_chars = sum(len(c["text"]) for c in chunks)
        boiler_chars = sum(len(s) * n for s, n in sentence_df.items() if n >= 0.2 * len(chunks))
        mp_chunks = [c for c in chunks if c["document_id"].startswith("mp-")]
        out["duplication"] = {
            "chunks": len(chunks),
            "documents": len(doc_ids),
            "chunks_from_mp_documents": len(mp_chunks),
            "chunks_with_a_neighbour_jaccard_ge_0.5": near,
            "median_best_neighbour_jaccard": round(statistics.median(max_j), 3),
            "p90_best_neighbour_jaccard": round(percentile(max_j, 0.9), 3),
            "sentences_in_ge_20_percent_of_chunks": [
                {"sentence_prefix": s[:70], "chunks": n} for s, n in common
            ],
            "share_of_chunk_chars_in_boilerplate_sentences": round(boiler_chars / chunk_chars, 3),
            "pairs_compared": pair_n,
        }

        # 3. query embeddings (benchmark-only disk cache)
        queries = sorted({str(c["query"]) for c in cases})
        cache = load_cache()
        missing = [q for q in queries if q not in cache]
        usage = {"calls": 0, "tokens": 0}
        if missing:
            secret = get_settings().voyage_api_key
            assert secret is not None
            reservation = reserve(max(len(missing) * 16, 1))
            voyage = VoyageEmbedder(secret.get_secret_value(), cfg)
            try:
                for q in missing:
                    prepared = prepare_query(q, max_chars=cfg.query_max_chars)
                    cache[q] = await voyage.embed_query(prepared.embed_text)
                commit(reservation, voyage.usage.total_tokens)
                usage = {"calls": voyage.usage.calls, "tokens": voyage.usage.total_tokens}
            except Exception:
                commit(reservation, None)
                raise
            finally:
                await voyage.aclose()
            CACHE.parent.mkdir(parents=True, exist_ok=True)
            CACHE.write_text(json.dumps(cache), encoding="utf-8")
        out["query_embedding_usage_this_run"] = usage

        # 4. raw branch retrieval, thresholds off, pinned corpus version
        params_base = {
            "version": VERSION,
            "languages": ["vi"],
            "countries": [],
            "topics": [],
            "age": None,
        }
        # document frequency of every folded token over chunk text for IDF
        from safevoice_agent.knowledge.textnorm import fold_vietnamese

        df: Counter[str] = Counter()
        for chunk in chunks:
            df.update(set(re.findall(r"[a-z0-9]+", fold_vietnamese(chunk["text"]))))
        n_chunks = len(chunks)

        per_query: list[dict[str, object]] = []
        for case in cases:
            q = str(case["query"])
            prepared = prepare_query(q, max_chars=cfg.query_max_chars)
            vec = (
                (
                    await conn.execute(
                        text(_VECTOR_SQL),
                        {
                            **params_base,
                            "embedding": _vector_literal(cache[q]),
                            "limit": 30,
                        },
                    )
                )
                .mappings()
                .all()
            )
            lex = []
            if prepared.tsquery:
                lex = (
                    (
                        await conn.execute(
                            text(_LEXICAL_SQL),
                            {**params_base, "tsquery": prepared.tsquery, "limit": 30},
                        )
                    )
                    .mappings()
                    .all()
                )
            tokens = lexical_tokens(prepared.embed_text)
            token_df = {t: df.get(t, 0) for t in tokens}
            per_query.append(
                {
                    "id": case["id"],
                    "split": case["split"],
                    "topic": case["topic"],
                    "no_result": case["no_result"],
                    "query": q,
                    "relevant": case["relevant"],
                    "vec_docs": [r["document_id"] for r in vec],
                    "vec_scores": [float(r["vector_score"]) for r in vec],
                    "lex_docs": [r["document_id"] for r in lex],
                    "lex_scores": [float(r["lexical_score"]) for r in lex],
                    "tokens": tokens,
                    "token_chunk_share": {t: round(c / n_chunks, 3) for t, c in token_df.items()},
                }
            )

    def first_k_docs(docs: list[str], k: int) -> list[str]:
        ordered: list[str] = []
        for d in docs:
            if d not in ordered:
                ordered.append(d)
        return ordered[:k]

    answerable = [r for r in per_query if not r["no_result"]]
    no_result = [r for r in per_query if r["no_result"]]
    summary: dict[str, object] = {}
    for branch in ("vec", "lex"):
        for split in ("dev", "test"):
            rows_ = [r for r in answerable if r["split"] == split]
            strict = []
            hit = []
            topic_hit = []
            for r in rows_:
                rel = set(r["relevant"])  # type: ignore[arg-type]
                ranked = first_k_docs(r[f"{branch}_docs"], 30)  # type: ignore[arg-type]
                strict.append(recall_at_k(rel, ranked, 5))
                hit.append(hit_at_k(rel, ranked, 5))
                topic_hit.append(
                    1.0 if set(ranked[:5]) & by_topic.get(str(r["topic"]), set()) else 0.0
                )
            summary[f"{branch}_{split}"] = {
                "strict_recall_at_5_doc_level_unthresholded": round(statistics.fmean(strict), 3),
                "hit_at_5_unthresholded": round(statistics.fmean(hit), 3),
                "answerable_cases": len(rows_),
            }
    out["unthresholded_raw_retrieval"] = summary

    max_cos_ans = [max(r["vec_scores"]) for r in answerable]  # type: ignore[type-var]
    max_cos_no = [max(r["vec_scores"]) for r in no_result]  # type: ignore[type-var]
    max_lex_ans = [max(r["lex_scores"], default=0.0) for r in answerable]  # type: ignore[type-var]
    max_lex_no = [max(r["lex_scores"], default=0.0) for r in no_result]  # type: ignore[type-var]
    gate_cos = cfg.vector_cos_lo + cfg.min_vector_score * (cfg.vector_cos_hi - cfg.vector_cos_lo)
    out["no_result_separability"] = {
        "max_cosine_answerable": {
            "min": round(min(max_cos_ans), 3),
            "median": round(statistics.median(max_cos_ans), 3),
            "max": round(max(max_cos_ans), 3),
        },
        "max_cosine_no_result": {
            "min": round(min(max_cos_no), 3),
            "median": round(statistics.median(max_cos_no), 3),
            "max": round(max(max_cos_no), 3),
        },
        "auc_max_cosine": round(auc(max_cos_ans, max_cos_no), 3),
        "max_lexical_answerable_median": round(statistics.median(max_lex_ans), 3),
        "max_lexical_no_result_median": round(statistics.median(max_lex_no), 3),
        "auc_max_lexical": round(auc(max_lex_ans, max_lex_no), 3),
        "effective_cosine_gate_at_locked_config": round(gate_cos, 3),
        "no_result_queries_with_any_lexical_hit": sum(1 for r in no_result if r["lex_docs"]),
        "no_result_queries_passing_locked_lexical_gate": sum(
            1
            for r in no_result
            if max(r["lex_scores"], default=0.0) >= cfg.min_lexical_score  # type: ignore[type-var]
        ),
        "no_result_queries_passing_locked_vector_gate": sum(1 for v in max_cos_no if v >= gate_cos),
        "answerable_failing_locked_vector_gate": sum(1 for v in max_cos_ans if v < gate_cos),
    }
    stop_hits: Counter[str] = Counter()
    for r in no_result:
        for token, share in r["token_chunk_share"].items():  # type: ignore[union-attr]
            if share >= 0.2 and r["lex_docs"]:
                stop_hits[token] += 1
    out["lexical_false_positive_driver_tokens"] = {
        "tokens_present_in_ge_20pct_of_chunks_that_triggered_no_result_hits": dict(
            stop_hits.most_common(12)
        ),
        "current_stoplist_size": len(STOPWORDS),
        "tsquery_operator": "OR (' | ')",
    }
    out["no_result_examples"] = [
        {
            "query": r["query"],
            "tokens": r["tokens"],
            "token_chunk_share": r["token_chunk_share"],
            "max_cos": round(max(r["vec_scores"]), 3),  # type: ignore[type-var]
            "max_lex": round(max(r["lex_scores"], default=0.0), 3),  # type: ignore[type-var]
            "top_lex_doc": (r["lex_docs"] or [None])[0],  # type: ignore[index]
        }
        for r in no_result[:8]
    ]
    confusions: Counter[str] = Counter()
    for r in answerable:
        if r["split"] != "test":
            continue
        top = first_k_docs(r["vec_docs"], 5)  # type: ignore[arg-type]
        if top and top[0] not in set(r["relevant"]):  # type: ignore[arg-type]
            confusions[f"{r['topic']} -> {top[0]}"] += 1
    out["test_top1_wrong_doc_examples"] = confusions.most_common(10)
    out["math_pi"] = math.pi  # sentinel proving the script ran to the end
    dest = HERE.parent / "results" / "diagnosis-v1.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    del out["math_pi"]
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
