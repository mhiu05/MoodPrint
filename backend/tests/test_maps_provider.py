import asyncio
import json

import httpx
import pytest


async def test_provider_total_deadline_closes_a_continuously_streaming_body(monkeypatch):
    from app.ai.search import apify

    closed = asyncio.Event()
    class Dripping(httpx.AsyncByteStream):
        async def __aiter__(self):
            while True:
                yield b" "
                await asyncio.sleep(0.01)

        async def aclose(self):
            closed.set()

    monkeypatch.setattr(apify, "REQUEST_TIMEOUT_SECONDS", 0.03, raising=False)
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, stream=Dripping()))) as client:
        provider = apify.ApifyMapsProvider(client, "synthetic", build="test123")
        task = asyncio.create_task(provider.status(apify.ProviderRunRef("run123")))
        done, _ = await asyncio.wait({task}, timeout=0.5)
        if not done:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            pytest.fail("a stream without idle gaps must still obey the total request deadline")
        with pytest.raises(TimeoutError):
            task.result()
        assert closed.is_set()


async def test_apify_start_is_async_bounded_and_drops_contact_fields():
    from app.ai.search.apify import ApifyMapsProvider

    requests = []
    def transport(request):
        requests.append(request)
        if request.method == "POST":
            return httpx.Response(201, json={"data": {"id": "run123", "defaultDatasetId": "data123", "defaultKeyValueStoreId": "kv123", "defaultRequestQueueId": "q123"}})
        if "datasets" in str(request.url):
            return httpx.Response(200, json=[{"title": "Cà phê", "address": "Quận 3", "categoryName": "Cafe",
                "totalScore": 4.5, "reviewsCount": 10, "phone": "PRIVATE", "email": "PRIVATE",
                "url": "https://evil.example/", "placeId": "ChIJabc"}])
        return httpx.Response(200, json={"data": {"status": "SUCCEEDED", "usageTotalUsd": 0.015}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        provider = ApifyMapsProvider(client, "synthetic-token", build="abc123")
        ref = await provider.start(category="cafe", area="Quận 3")
        view = await provider.status(ref)
        places = await provider.results(ref)
    start = requests[0]
    assert start.headers["Authorization"] == "Bearer synthetic-token"
    assert "token" not in str(start.url)
    assert start.url.params["waitForFinish"] == "0"
    # The pinned actor's live pricing rejects caps below $0.50.
    assert start.url.params["maxTotalChargeUsd"] == "0.5"
    assert start.url.params["timeout"] == "60"
    body = json.loads(start.content)
    assert body["maxCrawledPlacesPerSearch"] == 5
    assert body["scrapeContacts"] is False and body["maxReviews"] == 0
    assert body["locationQuery"] == "Quận 3"
    assert view.state == "succeeded"
    assert len(places) == 1 and places[0].rating == 4.5
    assert places[0].maps_url.startswith("https://www.google.com/maps/search/")
    assert "PRIVATE" not in places[0].model_dump_json()


async def test_oversized_provider_body_and_bad_reference_fail_closed():
    from app.ai.search.apify import ApifyMapsProvider, ProviderRunRef
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, content=b"x" * 65537))) as client:
        provider = ApifyMapsProvider(client, "fake", build="123")
        with pytest.raises(ValueError):
            await provider.status(ProviderRunRef(run_id="run123"))
        with pytest.raises(ValueError):
            await provider.status(ProviderRunRef(run_id="../../private"))
