"""Build benchmark_v2.jsonl from benchmark_v2.src.txt. Deterministic; prints the frozen hash.

Benchmark design: 150 answerable and 30 no-result Vietnamese
queries, graded per-document labels (2 = answers directly, 1 = useful in part), five styles, and a
split stratified by topic and style (dev about 40 percent, test about 60 percent). The same coding
agent wrote the corpus, the queries and the labels, so this is NOT independent validation.

    uv run python agent/evals/knowledge/cases/build_v2.py
"""

from __future__ import annotations

import hashlib
import json
import random
import re
import sys
import tomllib
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SRC = HERE / "benchmark_v2.src.txt"
OUT = HERE / "benchmark_v2.jsonl"
MANIFEST = ROOT / "agent" / "ingestion" / "corpus" / "manifest.toml"
SEED = "kb-benchmark-v2-20261109"
DEV_FRACTION = 0.4

ALIASES = {
    "L-bat-nat-la-gi": "legacy-bat-nat-la-gi",
    "L-chan-bao-cao": "legacy-chan-va-bao-cao-noi-dung",
    "L-luu-anh": "legacy-luu-anh-chup-co-ngu-canh",
    "L-giao-vien": "legacy-noi-chuyen-voi-giao-vien",
    "L-cham-soc": "legacy-noi-chuyen-voi-nguoi-cham-soc",
    "L-lo-lang": "legacy-tam-dung-khi-lo-lang",
    "L-theo-doi": "legacy-theo-doi-sau-khi-nho-giup",
    "L-tom-tat": "legacy-tom-tat-trung-tinh",
    "L-111": "legacy-tong-dai-111",
    "ND80": "vn-nd-80-2017-trich",
}


def expand(alias: str) -> str:
    return ALIASES.get(alias, f"kb-{alias}")


def fold(text: str) -> str:
    import unicodedata

    decomposed = unicodedata.normalize("NFD", text.lower())
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return stripped.replace("đ", "d")


def apportion(
    strata: dict[tuple[str, ...], list[int]], dev_total: int, rng: random.Random
) -> set[int]:
    """Largest-remainder apportionment of dev slots across strata, then seeded picks inside."""
    quotas = {key: len(items) * DEV_FRACTION for key, items in strata.items()}
    take = {key: int(quota) for key, quota in quotas.items()}
    remaining = dev_total - sum(take.values())
    order = sorted(
        strata,
        key=lambda key: (-(quotas[key] - take[key]), rng.random()),
    )
    for key in order:
        if remaining <= 0:
            break
        if take[key] < len(strata[key]):
            take[key] += 1
            remaining -= 1
    dev: set[int] = set()
    for key in sorted(strata):
        items = list(strata[key])
        rng.shuffle(items)
        dev.update(items[: take[key]])
    return dev


def main() -> None:
    manifest = tomllib.loads(MANIFEST.read_text(encoding="utf-8"))
    document_ids = {item["document_id"] for item in manifest["document"]}
    rows: list[dict[str, object]] = []
    answerable_no = 0
    no_result_no = 0
    for raw in SRC.read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.startswith("#"):
            continue
        topic, style, query, rel = (part.strip() for part in raw.split("|", 3))
        if topic == "none":
            no_result_no += 1
            rows.append(
                {
                    "id": f"N{no_result_no:03d}",
                    "text": query,
                    "style": "standard",
                    "topic": "",
                    "age_band": "any",
                    "answerable": False,
                    "gap": style == "gap",
                    "filters": {"languages": ["vi"]},
                    "relevant": [],
                    "notes": "in-domain gap: corpus intentionally lacks it"
                    if style == "gap"
                    else "out of scope",
                }
            )
            continue
        answerable_no += 1
        relevant = []
        for item in rel.split(","):
            alias, grade = item.split(":")
            doc = expand(alias.strip())
            if doc not in document_ids:
                raise SystemExit(f"unknown document in label: {doc} ({query})")
            relevant.append({"document_id": doc, "grade": int(grade)})
        if len({r["document_id"] for r in relevant}) != len(relevant):
            raise SystemExit(f"duplicate label for query: {query}")
        text = fold(query) if style == "auto" else query
        notes = "auto-stripped diacritics" if style == "auto" else ""
        rows.append(
            {
                "id": f"A{answerable_no:03d}",
                "text": text,
                "style": "nodiac" if style in {"auto", "nodiac"} else style,
                "topic": topic,
                "age_band": "any",
                "answerable": True,
                "filters": {"languages": ["vi"]},
                "relevant": relevant,
                "notes": notes,
            }
        )

    # near-duplicate and exact-duplicate query checks
    words = [set(re.findall(r"\w+", fold(str(row["text"])))) for row in rows]
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            union = words[i] | words[j]
            if union and len(words[i] & words[j]) / len(union) >= 0.8:
                raise SystemExit(f"near-duplicate queries: {rows[i]['id']} / {rows[j]['id']}")

    rng = random.Random(SEED)
    answerable_idx = [i for i, row in enumerate(rows) if row["answerable"]]
    strata: dict[tuple[str, ...], list[int]] = defaultdict(list)
    for i in answerable_idx:
        strata[(str(rows[i]["topic"]), str(rows[i]["style"]))].append(i)
    dev = apportion(strata, round(len(answerable_idx) * DEV_FRACTION), rng)
    no_idx = [i for i, row in enumerate(rows) if not row["answerable"]]
    no_strata: dict[tuple[str, ...], list[int]] = defaultdict(list)
    for i in no_idx:
        no_strata[("gap" if rows[i]["gap"] else "oos",)].append(i)
    dev |= apportion(no_strata, round(len(no_idx) * DEV_FRACTION), rng)
    for i, row in enumerate(rows):
        row["split"] = "dev" if i in dev else "test"

    payload = "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n"
    OUT.write_text(payload, encoding="utf-8", newline="\n")
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    split_counts = Counter(
        (row["split"], "answerable" if row["answerable"] else "no_result") for row in rows
    )
    style_counts = Counter((row["split"], row["style"]) for row in rows if row["answerable"])
    topic_counts = Counter((row["split"], row["topic"]) for row in rows if row["answerable"])
    summary = {
        "sha256_lf": digest,
        "rows": len(rows),
        "splits": {f"{k[0]}/{k[1]}": v for k, v in sorted(split_counts.items())},
        "styles": {f"{k[0]}/{k[1]}": v for k, v in sorted(style_counts.items())},
        "topics_both_splits": sorted(
            t
            for t in {k[1] for k in topic_counts}
            if topic_counts[("dev", t)] and topic_counts[("test", t)]
        ),
        "gap_queries": {
            split: sum(1 for r in rows if not r["answerable"] and r["gap"] and r["split"] == split)
            for split in ("dev", "test")
        },
    }
    (HERE / "benchmark_v2.summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    sys.stdout.buffer.write(
        (json.dumps(summary, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )


if __name__ == "__main__":
    main()
