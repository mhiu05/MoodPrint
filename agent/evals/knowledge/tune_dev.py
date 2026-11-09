"""Dev-split sweep for benchmark v2. Never reads the test split.

Selection rule, registered before the first run:
  1. Keep settings with false-no-result rate <= 0.08 and no-result accuracy >= 0.90 on dev.
  2. Among them take the best nDCG@10; settings within 0.01 are ties and the simpler wins
     (lexical weight 0 over a fused branch, cap 1 over 2, no phrase bonus over one).
  3. Within the winning structure pick the MEDIAN feasible vector gate, not an edge, because dev
     has only 12 no-result queries.
  4. If nothing is feasible, report that and do not relax the constraints.

    uv run python agent/evals/knowledge/tune_dev.py --version kb-... [--out path.json]
"""

from __future__ import annotations

import argparse
import asyncio
import itertools
import json
import os
import statistics
import sys
from dataclasses import replace
from pathlib import Path

from dotenv import dotenv_values
from moodprint_agent.knowledge.retriever import Collected, PgVectorKnowledgeRetriever
from moodprint_agent.knowledge.scoring import score_hits
from moodprint_shared.config import KnowledgeConfig
from moodprint_shared.contracts.knowledge import KnowledgeFilters, KnowledgeQuery, RetrievalScope
from sqlalchemy.ext.asyncio import create_async_engine

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
from metrics import hit_at_k, mrr_at_k, ndcg_at_k, recall_at_k  # noqa: E402
from run_v2 import DiskCachedEmbedder, load_cases  # noqa: E402

VECTOR_GATES = [round(0.10 + 0.025 * i, 3) for i in range(17)]  # 0.10 .. 0.50
LEXICAL_GATES = [0.4, 0.5, 0.6, 0.7, 0.8, 1.01]  # 1.01 disables the lexical gate
LEXICAL_WEIGHTS = [0.0, 0.25, 0.5]
RRF_KS = [50]  # 20 and 50 gave identical results in the first sweep
CAPS = [1, 2]
PHRASE_BONUSES = [0.0, 0.15]
# (gate_scope, chunk_floor_vector, chunk_floor_lexical); floors are ignored for scope "chunk"
SCOPES = [
    ("chunk", 0.0, 0.0),
    ("query", 0.1, 0.2),
    ("query", 0.1, 0.3),
    ("query", 0.2, 0.2),
    ("query", 0.2, 0.3),
]


def docs_of(hits: list[object]) -> list[str]:
    out: list[str] = []
    for hit in hits:
        doc = str(hit.document_id)  # type: ignore[attr-defined]
        if doc not in out:
            out.append(doc)
    return out


def simplicity(row: dict[str, object]) -> tuple[float, int, float]:
    return (float(row["lexical_weight"]), int(row["cap"]), float(row["phrase_bonus"]))  # type: ignore[arg-type]


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--out", type=Path, default=HERE / "results" / "dev-sweep-v2.json")
    args = parser.parse_args()

    values = dotenv_values(ROOT / ".local/stacks/kb/test.env")
    database = str(values["TEST_ADMIN_DATABASE_URL"])
    if "127.0.0.1" not in database and "localhost" not in database:
        raise SystemExit("refusing a non-loopback database")
    os.environ["TEST_ADMIN_DATABASE_URL"] = database
    engine = create_async_engine(database, hide_parameters=True)
    base = KnowledgeConfig()
    embedder = DiskCachedEmbedder(None, base.resolved_query_model())
    cases = load_cases("dev")
    assert all(case["split"] == "dev" for case in cases)

    collected: dict[float, list[Collected]] = {}
    try:
        for bonus in PHRASE_BONUSES:
            cfg = replace(
                base, lexical_phrase_bonus=bonus, lexical_candidates=40, vector_candidates=40
            )
            retriever = PgVectorKnowledgeRetriever(engine, embedder, cfg, read_role=None)
            rows: list[Collected] = []
            for case in cases:
                item = await retriever.collect(
                    KnowledgeQuery(
                        text=str(case["text"]),
                        filters=KnowledgeFilters(languages=["vi"]),
                        top_k=10,
                    ),
                    RetrievalScope(request_id=str(case["id"]), corpus_version=args.version),
                )
                assert item is not None
                rows.append(item)
            collected[bonus] = rows
    finally:
        await engine.dispose()

    results: list[dict[str, object]] = []
    grid = itertools.product(
        PHRASE_BONUSES, LEXICAL_WEIGHTS, RRF_KS, CAPS, SCOPES, LEXICAL_GATES, VECTOR_GATES
    )
    for bonus, weight, rrf_k, cap, (scope, floor_v, floor_l), lex_gate, vec_gate in grid:
        cfg = replace(
            base,
            lexical_phrase_bonus=bonus,
            lexical_weight=weight,
            rrf_k=rrf_k,
            max_chunks_per_document=cap,
            min_lexical_score=lex_gate,
            min_vector_score=vec_gate,
            gate_scope=scope,
            chunk_floor_vector=floor_v,
            chunk_floor_lexical=floor_l,
            lexical_candidates=40,
            vector_candidates=40,
        )
        recall5: list[float] = []
        hit5: list[float] = []
        mrr: list[float] = []
        ndcg: list[float] = []
        false_nr = 0
        answerable = 0
        correct_nr = 0
        negatives = 0
        gap_ok = 0
        gaps = 0
        for case, item in zip(cases, collected[bonus], strict=True):
            hits = score_hits(item.hits, cfg, top_k=10, lexical_only=not item.has_vector)
            docs = docs_of(list(hits))
            if case["answerable"]:
                answerable += 1
                grades = {r["document_id"]: int(r["grade"]) for r in case["relevant"]}
                rel = set(grades)
                recall5.append(recall_at_k(rel, docs, 5))
                hit5.append(hit_at_k(rel, docs, 5))
                mrr.append(mrr_at_k(rel, docs, 10))
                ndcg.append(ndcg_at_k(grades, docs, 10))
                false_nr += 1 if not hits else 0
            else:
                negatives += 1
                ok = not hits
                correct_nr += 1 if ok else 0
                if case.get("gap"):
                    gaps += 1
                    gap_ok += 1 if ok else 0
        results.append(
            {
                "phrase_bonus": bonus,
                "lexical_weight": weight,
                "rrf_k": rrf_k,
                "cap": cap,
                "min_lexical": lex_gate,
                "min_vector": vec_gate,
                "gate_scope": scope,
                "floor_vector": floor_v,
                "floor_lexical": floor_l,
                "recall_at_5": round(statistics.fmean(recall5), 4),
                "hit_at_5": round(statistics.fmean(hit5), 4),
                "mrr_at_10": round(statistics.fmean(mrr), 4),
                "ndcg_at_10": round(statistics.fmean(ndcg), 4),
                "false_no_result_rate": round(false_nr / answerable, 4),
                "no_result_accuracy": round(correct_nr / negatives, 4),
                "gap_accuracy": round(gap_ok / gaps, 4) if gaps else None,
            }
        )

    under_cap = [r for r in results if float(r["false_no_result_rate"]) <= 0.08]  # type: ignore[arg-type]
    feasible = [r for r in under_cap if float(r["no_result_accuracy"]) >= 0.90]  # type: ignore[arg-type]
    summary: dict[str, object] = {
        "corpus_version": args.version,
        "split": "dev",
        "configs_evaluated": len(results),
        "configs_under_false_no_result_cap": len(under_cap),
        "feasible_configs": len(feasible),
    }
    if feasible:
        pool = feasible
        summary["selection"] = "feasible: both dev constraints met"
    else:
        # Registered fallback: do not relax the constraints, report them as unmet, and take the
        # best no-result accuracy that the false-no-result cap allows.
        best_accuracy = max(float(r["no_result_accuracy"]) for r in under_cap)  # type: ignore[arg-type]
        pool = [r for r in under_cap if float(r["no_result_accuracy"]) >= best_accuracy - 1e-9]  # type: ignore[arg-type]
        summary["no_feasible_config"] = True
        summary["selection"] = (
            "fallback: no_result_accuracy >= 0.90 is NOT met on dev; best accuracy under the "
            "false-no-result cap"
        )
        summary["best_no_result_accuracy_under_cap"] = best_accuracy
    best = max(float(r["ndcg_at_10"]) for r in pool)  # type: ignore[arg-type]
    near = [r for r in pool if float(r["ndcg_at_10"]) >= best - 0.01]  # type: ignore[arg-type]
    simplest = min(simplicity(r) for r in near)
    structure = [r for r in near if simplicity(r) == simplest]
    keys = (
        "phrase_bonus",
        "lexical_weight",
        "rrf_k",
        "cap",
        "min_lexical",
        "gate_scope",
        "floor_vector",
        "floor_lexical",
    )
    groups: dict[tuple[object, ...], list[dict[str, object]]] = {}
    for row in structure:
        groups.setdefault(tuple(row[k] for k in keys), []).append(row)
    _key, members = max(
        groups.items(),
        key=lambda kv: (len(kv[1]), max(float(m["ndcg_at_10"]) for m in kv[1])),  # type: ignore[arg-type]
    )
    members.sort(key=lambda m: float(m["min_vector"]))  # type: ignore[arg-type]
    chosen = members[len(members) // 2]
    summary.update(
        best_ndcg_at_10_in_pool=best, chosen=chosen, plateau=[m["min_vector"] for m in members]
    )
    top = sorted(results, key=lambda r: -float(r["ndcg_at_10"]))[:40]  # type: ignore[arg-type]
    summary["top_by_ndcg_unconstrained"] = top[:10]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sys.stdout.buffer.write(
        (json.dumps(summary, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )


if __name__ == "__main__":
    asyncio.run(main())
