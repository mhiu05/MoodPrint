"""The opt-in real eval adapter validates local configuration before any provider."""

import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_real_factory_refuses_non_loopback_database_before_any_client(monkeypatch):
    module = importlib.import_module("evals.real_knowledge")
    monkeypatch.setenv("MOODPRINT_EVAL_DATABASE_ENV", "synthetic.env")
    monkeypatch.setattr(
        module,
        "dotenv_values",
        lambda p: {"TEST_DATABASE_URL": "postgresql+asyncpg://synthetic@remote.example/postgres"},
    )
    with pytest.raises(ValueError, match="loopback"):
        module.local_database()


async def test_concurrent_query_reservations_reconcile_only_their_own_usage(monkeypatch, tmp_path):
    import asyncio
    from types import SimpleNamespace

    from evals import real_knowledge

    settled = []
    monkeypatch.setattr(real_knowledge, "reserve", lambda *args, **kwargs: "synthetic-reservation")
    monkeypatch.setattr(
        real_knowledge, "commit", lambda reservation, tokens, **kwargs: settled.append(tokens)
    )

    class Embedder:
        attempts = 0
        usage = SimpleNamespace(calls=0, total_tokens=0)

        @property
        def settlement_tokens(self):
            return self.usage.total_tokens

        async def embed_query(self, value):
            self.attempts += 1
            await asyncio.sleep(0)
            self.usage.calls += 1
            self.usage.total_tokens += 10
            return [1.0]

    metered = real_knowledge.MeteredQueryEmbedder(Embedder(), tmp_path / "synthetic-ledger")
    await asyncio.gather(metered.embed_query("one"), metered.embed_query("two"))
    assert settled == [10, 10]


def test_exhausted_openai_ledger_is_refused_before_key_or_client(monkeypatch, tmp_path):
    from types import SimpleNamespace

    from evals import live
    from evals.budget import BudgetError

    path = tmp_path / "existing-spend.jsonl"
    path.write_text("synthetic test fixture", encoding="utf-8")
    monkeypatch.setenv("MOODPRINT_EVAL_LEDGER", str(path))
    monkeypatch.setattr(live, "load_budget", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        live,
        "BudgetLedger",
        lambda *args, **kwargs: SimpleNamespace(
            reserved_calls=900, budget=SimpleNamespace(max_calls_total=900)
        ),
    )

    def forbidden():
        raise AssertionError("exhausted call cap must be checked first")

    monkeypatch.setattr(live, "api_key", forbidden)
    with pytest.raises(BudgetError, match="call cap"):
        live.open_ledger()
