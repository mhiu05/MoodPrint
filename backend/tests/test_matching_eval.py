"""T-EVAL-01 harness check on a 10-persona slice (the full run is the committed report)."""

from evals.matching import benchmark


def test_benchmark_reports_every_metric_on_a_small_fixture():
    personas = benchmark.load("personas_v2.json")["personas"][:10]
    ids = {persona["id"] for persona in personas}
    labels = [
        pair
        for pair in benchmark.load("pair_labels.json")["pairs"]
        if pair["a"] in ids and pair["b"] in ids
    ]
    report = benchmark.run(personas, labels, provisional=True)
    for scorer in ("v1", "v2"):
        metrics = report[scorer]
        assert {
            "ndcg_at5",
            "precision_at5",
            "coverage",
            "mean_candidates",
            "exposure_gini",
            "faithfulness",
            "symmetry_violations",
            "p95_ms_per_viewer",
            "p95_ms_per_viewer_600",
        } <= metrics.keys()
        assert 0 <= metrics["coverage"] <= 1 and 0 <= metrics["exposure_gini"] <= 1
        assert metrics["ndcg_at5"] is None or 0 <= metrics["ndcg_at5"] <= 1
        assert metrics["symmetry_violations"] == 0
    assert report["v2"]["faithfulness"] == 1.0
    assert report["gate"]["labels_provisional"] is True
    assert set(report["gate"]["criteria"]) >= {"ndcg_gain_ge_0_05", "faithfulness_100"}


def test_dataset_shape_matches_the_methodology():
    personas = benchmark.load("personas_v2.json")
    labels = benchmark.load("pair_labels.json")
    assert len(personas["personas"]) == 60 and len(labels["pairs"]) == 300
    assert personas["provisional"] is True and labels["provisional"] is True
    shapes = [persona["shape"] for persona in personas["personas"]]
    assert shapes.count("v1") == 12  # 20 %
    assert all({"r1", "r2", "r3"} <= pair.keys() for pair in labels["pairs"])
