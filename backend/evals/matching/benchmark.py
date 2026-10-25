"""Offline v1 vs v2 matching benchmark (no network, no provider calls, no real data).

python -m evals.matching.benchmark --out evals/matching/report.json   (from backend/)

For every persona as viewer it ranks all others with each scorer (eligibility applied)
and reports NDCG@5 and Precision@5 against mean proxy labels, coverage, candidates per
viewer, exposure Gini, reason faithfulness, symmetry violations and per-viewer timing at
60 and 600 personas. The gate is 05 section 12; with provisional labels a passing gate is
recorded but does not by itself switch MATCHING_SCORER.
"""

import argparse
import json
import math
import random
import statistics
import time
import uuid
from datetime import UTC, date, datetime
from pathlib import Path

from app.modules.matching import explain, ranking, scoring, scoring_v2
from app.modules.profiles import taxonomy

HERE = Path(__file__).parent
DAY = date(2026, 10, 25)
NOW = datetime(2026, 10, 25, 9, tzinfo=UTC)
TOP = 5


def pid(identifier: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"moodprint-eval:{identifier}")


def shares_language(a: dict, b: dict) -> bool:
    return bool(set(a["languages"]) & set(b["languages"]))


def rank_v1(viewer: dict, pool: list[dict]) -> list[str]:
    mine = scoring.v1_view(viewer["profile"])
    scored = []
    for peer in pool:
        other = peer["profile"]
        if other["goal"] != viewer["profile"]["goal"] or not shares_language(
            viewer["profile"], other
        ):
            continue
        points = scoring.score(mine, scoring.v1_view(other))
        if points >= 30:
            scored.append((points, str(pid(peer["id"])), peer["id"]))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [item[2] for item in scored]


def rank_v2(viewer: dict, pool: list[dict]) -> list[str]:
    own = viewer["profile"]
    candidates, ids = [], {}
    for peer in pool:
        other = peer["profile"]
        if not shares_language(own, other) or not scoring_v2.goal_allowed(own, other):
            continue
        breakdown = scoring_v2.score(own, other)
        if scoring_v2.eligible(breakdown):
            key = pid(peer["id"])
            ids[key] = peer["id"]
            candidates.append(ranking.Candidate(key, breakdown.score, other))
    # Production ranks a shortlist of 10; the tail keeps score order for NDCG over labels.
    head = ranking.rank(pid(viewer["id"]), candidates, DAY, NOW, 10)
    tail = sorted(
        (item for item in candidates if item.peer_id not in set(head)),
        key=lambda item: (-item.score, str(item.peer_id)),
    )
    return [ids[key] for key in head] + [ids[item.peer_id] for item in tail]


def allowed_reasons(a: dict, b: dict) -> set[str]:
    breakdown = scoring_v2.score(a, b)
    shared = breakdown.shared
    allowed = {taxonomy.ACTIVITY_REASONS[t] for t in shared["activities"]}
    allowed |= {f"Cùng thích {taxonomy.INTERESTS[t].lower()}" for t in shared["interests"]}
    allowed |= {f"Cùng coi trọng {taxonomy.VALUES[t].lower()}" for t in shared["values"]}
    allowed |= {f"Hay rảnh {taxonomy.AVAILABILITY[t].lower()}" for t in shared["availability"]}
    if a["style"] == b["style"]:
        allowed.add("Cùng cách trò chuyện")
    return allowed


def gini(values: list[int]) -> float:
    if not values or not sum(values):
        return 0.0
    ordered = sorted(values)
    n = len(ordered)
    weighted = sum((index + 1) * value for index, value in enumerate(ordered))
    return (2 * weighted) / (n * sum(ordered)) - (n + 1) / n


def ndcg(ranked: list[str], gains: dict[str, float]) -> float | None:
    ideal = sorted(gains.values(), reverse=True)[:TOP]
    idcg = sum(gain / math.log2(index + 2) for index, gain in enumerate(ideal))
    if idcg == 0:
        return None
    shown = [peer for peer in ranked if peer in gains][:TOP]
    return sum(gains[peer] / math.log2(index + 2) for index, peer in enumerate(shown)) / idcg


def krippendorff_alpha_interval(pairs: list[dict]) -> float:
    """Interval-metric alpha for complete 3-rater data."""
    units = [[pair["r1"], pair["r2"], pair["r3"]] for pair in pairs]
    values = [v for unit in units for v in unit]
    n = len(values)
    disagreement_observed = sum(
        (a - b) ** 2
        for unit in units
        for i, a in enumerate(unit)
        for j, b in enumerate(unit)
        if i != j
    ) / (n * (len(units[0]) - 1))
    mean = statistics.fmean(values)
    disagreement_expected = sum((v - mean) ** 2 for v in values) * 2 / (n - 1)
    return 1 - disagreement_observed / disagreement_expected if disagreement_expected else 1.0


def evaluate(personas: list[dict], labels: list[dict], ranker, faithful_check: bool) -> dict:
    by_id = {persona["id"]: persona for persona in personas}
    gains: dict[str, dict[str, float]] = {persona["id"]: {} for persona in personas}
    for pair in labels:
        mean = (pair["r1"] + pair["r2"] + pair["r3"]) / 3
        gains[pair["a"]][pair["b"]] = mean
        gains[pair["b"]][pair["a"]] = mean
    ndcgs, precisions, counts, timings = [], [], [], []
    exposure = {persona["id"]: 0 for persona in personas}
    unfaithful = shown_total = 0
    for viewer in personas:
        pool = [peer for peer in personas if peer["id"] != viewer["id"]]
        start = time.perf_counter()
        ranked = ranker(viewer, pool)
        timings.append(time.perf_counter() - start)
        counts.append(len(ranked))
        for peer in ranked[:TOP]:
            exposure[peer] += 1
            shown_total += 1
            if faithful_check:
                reasons = explain.reasons(
                    scoring_v2.score(viewer["profile"], by_id[peer]["profile"])
                )
                if not reasons or not set(reasons) <= allowed_reasons(
                    viewer["profile"], by_id[peer]["profile"]
                ):
                    unfaithful += 1
        value = ndcg(ranked, gains[viewer["id"]])
        if value is not None:
            ndcgs.append(value)
            labelled = [peer for peer in ranked if peer in gains[viewer["id"]]][:TOP]
            precisions.append(
                sum(gains[viewer["id"]][peer] >= 1.5 for peer in labelled) / len(labelled)
                if labelled
                else 0.0
            )
    return {
        "ndcg_at5": round(statistics.fmean(ndcgs), 4) if ndcgs else None,
        "precision_at5": round(statistics.fmean(precisions), 4) if precisions else None,
        "coverage": round(sum(count > 0 for count in counts) / len(counts), 4),
        "mean_candidates": round(statistics.fmean(counts), 2),
        "exposure_gini": round(gini(list(exposure.values())), 4),
        "faithfulness": round(1 - unfaithful / shown_total, 4)
        if faithful_check and shown_total
        else 1.0,
        "viewers_evaluated": len(ndcgs),
        "p95_ms_per_viewer": round(1000 * sorted(timings)[int(0.95 * (len(timings) - 1))], 3),
    }


def replicate(personas: list[dict], factor: int) -> list[dict]:
    rng = random.Random(600)
    result = []
    for copy in range(factor):
        for persona in personas:
            profile = json.loads(json.dumps(persona["profile"]))
            if copy and len(profile["interests"]) < 10:
                extra = rng.choice(sorted(set(taxonomy.INTERESTS) - set(profile["interests"])))
                if persona["shape"] != "v1":
                    profile["interests"].append(extra)
            result.append({**persona, "id": f"{persona['id']}-{copy}", "profile": profile})
    return result


def symmetry_violations(personas: list[dict]) -> dict:
    v1 = v2 = 0
    for i, a in enumerate(personas):
        for b in personas[i + 1 :]:
            pa, pb = a["profile"], b["profile"]
            if abs(scoring_v2.score(pa, pb).score - scoring_v2.score(pb, pa).score) > 1e-12:
                v2 += 1
            if scoring.score(scoring.v1_view(pa), scoring.v1_view(pb)) != scoring.score(
                scoring.v1_view(pb), scoring.v1_view(pa)
            ):
                v1 += 1
    return {"v1": v1, "v2": v2}


def run(personas: list[dict], labels: list[dict], provisional: bool) -> dict:
    v1 = evaluate(personas, labels, rank_v1, faithful_check=False)
    v2 = evaluate(personas, labels, rank_v2, faithful_check=True)
    large = replicate(personas, 10)
    v1["p95_ms_per_viewer_600"] = evaluate(large, [], rank_v1, False)["p95_ms_per_viewer"]
    v2["p95_ms_per_viewer_600"] = evaluate(large, [], rank_v2, False)["p95_ms_per_viewer"]
    symmetry = symmetry_violations(personas)
    v1["symmetry_violations"], v2["symmetry_violations"] = symmetry["v1"], symmetry["v2"]
    criteria = {
        "ndcg_gain_ge_0_05": v2["ndcg_at5"] >= v1["ndcg_at5"] + 0.05,
        "coverage_not_lower": v2["coverage"] >= v1["coverage"],
        "gini_not_higher": v2["exposure_gini"] <= v1["exposure_gini"],
        "faithfulness_100": v2["faithfulness"] == 1.0,
        "symmetry_0": v2["symmetry_violations"] == 0,
        "p95_600_lt_50ms": v2["p95_ms_per_viewer_600"] < 50,
    }
    passed = all(criteria.values())
    return {
        "dataset": {
            "personas": len(personas),
            "labelled_pairs": len(labels),
            "labels_provisional": provisional,
            "krippendorff_alpha": round(krippendorff_alpha_interval(labels), 3) if labels else None,
        },
        "v1": v1,
        "v2": v2,
        "gate": {
            "passed": passed,
            "criteria": criteria,
            "labels_provisional": provisional,
            "decision": (
                "Metric gate met on provisional proxy labels: keep MATCHING_SCORER=v1 by default; "
                "run shadow on staging and confirm with human-rated labels before switching to v2."
                if passed and provisional
                else "Gate met: MATCHING_SCORER=v2 may be enabled."
                if passed
                else "Gate not met: keep MATCHING_SCORER=v1."
            ),
        },
    }


def load(name: str) -> dict:
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(HERE / "report.json"))
    args = parser.parse_args()
    personas, labels = load("personas_v2.json"), load("pair_labels.json")
    report = run(personas["personas"], labels["pairs"], bool(labels.get("provisional")))
    Path(args.out).write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report["gate"], ensure_ascii=False))


if __name__ == "__main__":
    main()
