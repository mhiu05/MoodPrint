"""The fake evaluation proves ranking plumbing, never Voyage quality."""

from evals.journal_retrieval.run import evaluate, load_dataset
from tests.fakes import FakeEmbedder


def test_synthetic_dataset_has_forty_entries_and_fifteen_labelled_queries():
    data = load_dataset()
    assert len(data["entries"]) == 40
    assert len(data["queries"]) == 15
    assert {group: sum(row["group"] == group for row in data["queries"])
            for group in ("keyword", "paraphrase", "pattern")} == {"keyword": 5, "paraphrase": 6, "pattern": 4}
    assert max(row["daysAgo"] for row in data["entries"]) <= 60
    ids = {row["id"] for row in data["entries"]}
    assert all(set(row["relevant"]) <= ids and row["relevant"] for row in data["queries"])


async def test_fake_hybrid_improves_paraphrases_without_regressing_other_groups(journal_configured):
    app, actors = journal_configured
    result = await evaluate(app.state.database, app.state.settings, actors[0][1], FakeEmbedder(256))
    for group in ("keyword", "paraphrase", "pattern"):
        assert result["hybrid"][group]["recall@6"] >= result["keyword"][group]["recall@6"]
    assert result["hybrid"]["paraphrase"]["recall@6"] > result["keyword"]["paraphrase"]["recall@6"]
    assert result["hybrid"]["paraphrase"]["recall@6"] >= .8
    assert result["providerCalls"] == 55
