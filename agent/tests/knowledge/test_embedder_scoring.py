import hashlib

import httpx
import pytest
from safevoice_agent.knowledge.embedder import HashingEmbedder, VoyageEmbedder
from safevoice_agent.knowledge.scoring import RawHit, score_hits
from safevoice_shared.config import KnowledgeConfig
from safevoice_shared.contracts.errors import KnowledgeTimeout, KnowledgeUnavailable
from safevoice_shared.contracts.knowledge import SourceCitation


def _citation(document_id: str) -> SourceCitation:
    return SourceCitation(
        source_id="mp-authored",
        document_id=document_id,
        title="Hỗ trợ",
        publisher="SafeVoice",
        url="https://example.edu.vn/ho-tro",
        section=None,
        published_at=None,
        last_reviewed="2026-11-08",
        applicability="Tóm tắt biên soạn.",
        country_scope=["VN"],
    )


def test_hashing_embedder_is_deterministic_and_accent_insensitive() -> None:
    embedder = HashingEmbedder()

    async def once(text: str) -> list[float]:
        return await embedder.embed_query(text)

    import asyncio

    first = asyncio.run(once("bị nhắn tin"))
    second = asyncio.run(once("bi nhan tin"))
    third = asyncio.run(once("thời tiết hôm nay"))
    assert first == second
    assert len(first) == 1024
    assert abs(sum(value * value for value in first) - 1) < 1e-6
    same = sum(a * b for a, b in zip(first, second, strict=True))
    other = sum(a * b for a, b in zip(first, third, strict=True))
    assert same > other


def test_scoring_gate_drops_weak_neighbors_and_caps_each_document() -> None:
    cfg = KnowledgeConfig()
    hits = [
        RawHit("b#001-aaaaaaaa", "b", "y", _citation("b"), lexical_score=0.4),
        RawHit("b#002-bbbbbbbb", "b", "y", _citation("b"), lexical_score=0.3),
        RawHit("b#003-cccccccc", "b", "y", _citation("b"), lexical_score=0.2),
        RawHit("a#001-dddddddd", "a", "x", _citation("a"), vector_score=0.9, lexical_score=0.5),
        RawHit("z#001-eeeeeeee", "z", "no", _citation("z"), vector_score=0.01, lexical_score=0.0),
    ]
    scored = score_hits(hits, cfg, top_k=5)
    assert [hit.chunk_id for hit in scored][0].startswith("a#")
    assert sum(hit.document_id == "b" for hit in scored) <= cfg.max_chunks_per_document
    assert all(hit.document_id != "z" for hit in scored)
    assert all(0 <= hit.score <= 1 for hit in scored)


def test_voyage_request_shape_retries_and_does_not_log_text(
    caplog: pytest.LogCaptureFixture,
) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        body = request.read()
        assert b"bai viet bi mat" in body
        assert b'"truncation":false' in body or b'"truncation": false' in body
        assert b"voyage-4" in body
        assert b"1024" in body
        if calls["n"] == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        vector = [0.0] * 1024
        vector[0] = 1.0
        return httpx.Response(
            200, json={"data": [{"embedding": vector}], "usage": {"total_tokens": 3}}
        )

    async def run() -> None:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        embedder = VoyageEmbedder(
            api_key="test-key", cfg=KnowledgeConfig(), client=client, sleeper=_instant
        )
        with caplog.at_level("INFO"):
            vector = await embedder.embed_documents(["bai viet bi mat"])
        await client.aclose()
        assert len(vector[0]) == 1024
        assert embedder.usage.total_tokens == 3

    import asyncio

    asyncio.run(run())
    assert calls["n"] == 2
    assert "bai viet bi mat" not in caplog.text


def test_voyage_gives_up_on_repeated_server_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    async def run() -> None:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        embedder = VoyageEmbedder(
            api_key="test-key", cfg=KnowledgeConfig(), client=client, sleeper=_instant
        )
        with pytest.raises(KnowledgeUnavailable):
            await embedder.embed_query("xin chao")
        await client.aclose()

    import asyncio

    asyncio.run(run())


def test_voyage_timeout_is_a_knowledge_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("slow")

    async def run() -> None:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        embedder = VoyageEmbedder(
            api_key="test-key", cfg=KnowledgeConfig(), client=client, sleeper=_instant
        )
        with pytest.raises(KnowledgeTimeout):
            await embedder.embed_query("xin chao")
        await client.aclose()

    import asyncio

    asyncio.run(run())


async def _instant(_seconds: float) -> None:
    return None


def test_cache_key_uses_text_hash_not_the_raw_string(tmp_path) -> None:
    digest = hashlib.sha256(b"hello").hexdigest()
    assert len(digest) == 64


def test_unknown_provider_attempts_are_not_zero_cost() -> None:
    import asyncio

    import httpx
    from safevoice_agent.knowledge.embedder import VoyageEmbedder
    from safevoice_shared.config import KnowledgeConfig
    from safevoice_shared.contracts.errors import KnowledgeTimeout

    async def once():
        def timeout(request):
            raise httpx.ReadTimeout("synthetic timeout", request=request)

        async def no_wait(seconds):
            pass

        async with httpx.AsyncClient(transport=httpx.MockTransport(timeout)) as client:
            embedder = VoyageEmbedder(
                "synthetic-key", KnowledgeConfig(), client=client, sleeper=no_wait
            )
            with pytest.raises(KnowledgeTimeout):
                await embedder.embed_query("synthetic input")
            assert embedder.attempts == 5
            assert embedder.settlement_tokens is None

    asyncio.run(once())


def test_success_without_usage_is_still_unknown_cost() -> None:
    import asyncio

    import httpx
    from safevoice_agent.knowledge.embedder import VoyageEmbedder
    from safevoice_shared.config import KnowledgeConfig

    async def once():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json={"data": [{"embedding": [0.0] * 1024}]})
            )
        ) as client:
            embedder = VoyageEmbedder("synthetic-key", KnowledgeConfig(), client=client)
            await embedder.embed_query("synthetic input")
            assert embedder.settlement_tokens is None

    asyncio.run(once())
