import json
from pathlib import Path

import pytest
from moodprint_agent.knowledge.embedder import EmbeddingCache
from moodprint_agent.knowledge.ingest.acquire import assert_public_https
from moodprint_agent.knowledge.ingest.budget import (
    BudgetBlocked,
    commit,
    release,
    reserve,
    snapshot,
)
from moodprint_agent.knowledge.ingest.cli import main
from moodprint_agent.knowledge.ingest.embed import embed_missing
from moodprint_agent.knowledge.ingest.runtime import resolve_admin_url

ROOT = Path("agent/ingestion/corpus/manifest.toml")


def _card(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "+++",
                'document_id = "card-one"',
                'title = "Giữ lại tin nhắn"',
                'source_id = "mp-authored"',
                'language = "vi"',
                'country_scope = ["VN"]',
                'topics = ["evidence"]',
                'age_bands = ["11-13"]',
                "last_reviewed = 2026-11-08",
                'applicability = "Tóm tắt biên soạn."',
                "[[derived_from]]",
                'source_id = "mp-authored"',
                'locator = "thẻ kiểm thử"',
                "+++",
                "## Giữ lại",
                "",
                "Hãy chụp lại tin nhắn trước khi xóa, ghi ngày giờ, và chỉ đưa bản đó cho người lớn mà bạn tin. "
                "Không chuyển tiếp nội dung cho cả nhóm. Việc này giúp người lớn hiểu chuyện mà không buộc bạn kể hết ngay.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _corpus(root: Path) -> Path:
    sources = root / "sources"
    sources.mkdir(parents=True)
    (sources / "mp-authored.toml").write_text(
        "\n".join(
            [
                'source_id = "mp-authored"',
                'kind = "authored"',
                'publisher = "MoodPrint"',
                'title = "Thẻ biên soạn"',
                'language = "vi"',
                'country_scope = ["VN"]',
                "authority_tier = 4",
                'licence_class = "authored"',
                'licence_note = "Nội dung kiểm thử."',
                "verified_on = 2026-11-08",
                "",
            ]
        ),
        encoding="utf-8",
    )
    _card(root / "card.md")
    manifest = root / "manifest.toml"
    manifest.write_text(
        "\n".join(
            [
                'version_label = "kb-test"',
                "[[document]]",
                'document_id = "card-one"',
                'source_id = "mp-authored"',
                'path = "card.md"',
                'topics = ["evidence"]',
                "last_reviewed = 2026-11-08",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return manifest


def test_plan_reads_the_checked_in_manifest() -> None:
    assert main(["plan", "--manifest", str(ROOT)]) == 0


def test_invalid_open_reuse_licence_exits_1(tmp_path: Path) -> None:
    sources = tmp_path / "sources"
    sources.mkdir()
    (sources / "bad.toml").write_text(
        "\n".join(
            [
                'source_id = "bad-source"',
                'kind = "law"',
                'publisher = "Test"',
                'title = "Missing quote"',
                'language = "vi"',
                'country_scope = ["VN"]',
                "authority_tier = 1",
                'licence_class = "open_reuse"',
                'licence_note = "No quote."',
                "verified_on = 2026-11-09",
                "",
            ]
        ),
        encoding="utf-8",
    )
    manifest = tmp_path / "manifest.toml"
    manifest.write_text('version_label = "kb-test"\n', encoding="utf-8")
    assert main(["plan", "--manifest", str(manifest)]) == 1


def test_bad_arguments_do_not_exit_2() -> None:
    assert main(["embed"]) == 1
    assert main(["nope"]) == 1


def test_build_is_byte_stable_and_embed_resumes(tmp_path: Path) -> None:
    manifest = _corpus(tmp_path / "corpus")
    first = tmp_path / "build-a"
    second = tmp_path / "build-b"
    assert main(["build", "--manifest", str(manifest), "--out", str(first)]) == 0
    assert main(["build", "--manifest", str(manifest), "--out", str(second)]) == 0
    assert (first / "chunks.jsonl").read_bytes() == (second / "chunks.jsonl").read_bytes()
    assert main(["embed", "--build", str(first), "--embedder", "hashing"]) == 0
    meta = json.loads((first / "embed.json").read_text(encoding="utf-8"))
    assert meta["complete"] is True
    assert meta["dims"] == 1024
    assert meta["model"] == "hashing"
    assert main(["embed", "--build", str(first), "--embedder", "hashing"]) == 0
    again = json.loads((first / "embed.json").read_text(encoding="utf-8"))
    assert again["cache_hits"] == again["embedded"]
    (first / "chunks.jsonl").write_text("{", encoding="utf-8")
    assert main(["embed", "--build", str(first), "--embedder", "hashing"]) == 1


def test_acquire_with_no_open_reuse_sources_is_a_real_empty_result(tmp_path: Path) -> None:
    manifest = _corpus(tmp_path / "corpus")
    assert main(["acquire", "--manifest", str(manifest), "--offline"]) == 0


def test_ssrf_guard_rejects_loopback_and_plain_http() -> None:
    with pytest.raises(ValueError):
        assert_public_https("http://example.com/a", {"example.com"})
    with pytest.raises(ValueError):
        assert_public_https("https://127.0.0.1/secret", {"127.0.0.1"})


def test_remote_database_target_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "TEST_ADMIN_DATABASE_URL",
        "postgresql+asyncpg://moodprint_api:local@db.example.com/postgres",
    )
    with pytest.raises(ValueError):
        resolve_admin_url("test-env")


def test_budget_is_fail_closed_and_does_not_reset(tmp_path: Path) -> None:
    ledger = tmp_path / "voyage-ledger.json"
    held = reserve(1_000, ledger=ledger)
    commit(held, 800, ledger=ledger)
    spent = snapshot(ledger)["spent_usd"]
    ledger.unlink()
    assert snapshot(ledger)["spent_usd"] == spent
    with pytest.raises(BudgetBlocked):
        reserve(20_000_000, ledger=ledger)
    release("missing", ledger=ledger)


async def test_interrupted_embedding_resumes_from_cache(tmp_path: Path) -> None:
    cache = EmbeddingCache(tmp_path / "embeddings.sqlite")
    calls = {"n": 0}

    async def flaky(batch: list[str]) -> list[list[float]]:
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("interrupted")
        return [[1.0, *([0.0] * 1023)] for _ in batch]

    with pytest.raises(RuntimeError):
        await embed_missing(
            ["một", "hai"],
            flaky,
            cache,
            model="hashing",
            dims=1024,
            input_type="document",
            batch_size=1,
        )

    async def healthy(batch: list[str]) -> list[list[float]]:
        calls["n"] += 1
        return [[1.0, *([0.0] * 1023)] for _ in batch]

    before = calls["n"]
    vectors, hits = await embed_missing(
        ["một", "hai"],
        healthy,
        cache,
        model="hashing",
        dims=1024,
        input_type="document",
        batch_size=1,
    )
    assert hits == 1
    assert calls["n"] == before + 1
    assert len(vectors) == 2
    cache.close()


def test_voyage_command_stops_before_a_client_when_the_budget_refuses(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    manifest = _corpus(tmp_path / "corpus")
    build = tmp_path / "build"
    assert main(["build", "--manifest", str(manifest), "--out", str(build)]) == 0

    def refuse(*_args: object, **_kwargs: object) -> str:
        raise BudgetBlocked("cap")

    def explode(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("voyage client should not be constructed")

    monkeypatch.setattr("moodprint_agent.knowledge.ingest.commands.reserve", refuse)
    monkeypatch.setattr("moodprint_agent.knowledge.ingest.commands.VoyageEmbedder", explode)
    assert main(["embed", "--build", str(build), "--embedder", "voyage"]) == 3


def test_voyage_embed_requires_existing_cumulative_ledger(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    manifest = _corpus(tmp_path / "corpus")
    build = tmp_path / "build"
    assert main(["build", "--manifest", str(manifest), "--out", str(build)]) == 0
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "moodprint_agent.knowledge.ingest.commands._voyage_key", lambda: "synthetic-key"
    )

    def unexpected(*args, **kwargs):
        raise AssertionError("missing ledger must fail before provider construction")

    monkeypatch.setattr("moodprint_agent.knowledge.ingest.commands.VoyageEmbedder", unexpected)
    assert main(["embed", "--build", str(build), "--embedder", "voyage"]) == 3
    assert not (tmp_path / ".local/voyage-ledger.json").exists()


def test_embed_timeout_keeps_conservative_cost(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from types import SimpleNamespace

    from moodprint_shared.contracts.errors import KnowledgeTimeout

    manifest = _corpus(tmp_path / "corpus")
    build = tmp_path / "build"
    assert main(["build", "--manifest", str(manifest), "--out", str(build)]) == 0
    monkeypatch.chdir(tmp_path)
    initial = reserve(1)
    commit(initial, 0)
    monkeypatch.setattr(
        "moodprint_agent.knowledge.ingest.commands._voyage_key", lambda: "synthetic-key"
    )

    class TimeoutEmbedder:
        attempts = 1
        settlement_tokens = None
        usage = SimpleNamespace(total_tokens=0, usd=0)

        def __init__(self, *args, **kwargs):
            pass

        async def embed_documents(self, batch):
            raise KnowledgeTimeout()

        async def aclose(self):
            pass

    monkeypatch.setattr("moodprint_agent.knowledge.ingest.commands.VoyageEmbedder", TimeoutEmbedder)
    with pytest.raises(KnowledgeTimeout):
        main(["embed", "--build", str(build), "--embedder", "voyage"])
    assert float(snapshot()["spent_usd"]) > 0
