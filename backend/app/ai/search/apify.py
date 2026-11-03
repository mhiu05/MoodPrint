"""Fixed-endpoint Apify adapter; no paid start retries, contact data or arbitrary URLs."""

import asyncio
import re
from dataclasses import dataclass, field
from decimal import Decimal
from urllib.parse import urlencode

import httpx

from app.ai.search.maps import PlaceResult
from app.infrastructure.database.models import now

CATEGORIES = {"cafe": "quán cà phê", "park": "công viên", "restaurant": "nhà hàng", "museum": "bảo tàng", "activity": "địa điểm vui chơi"}
SAFE_ID = re.compile(r"^[a-zA-Z0-9_-]{1,100}$")
REQUEST_TIMEOUT_SECONDS = 3
MAX_TOTAL_CHARGE_USD = "0.5"


@dataclass(frozen=True)
class ProviderRunRef:
    run_id: str
    dataset_id: str | None = None
    storage_refs: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderRunStatus:
    state: str
    charged_usd: Decimal | None = None


class ApifyMapsProvider:
    def __init__(self, client: httpx.AsyncClient, token: str, *, build: str):
        if not build or not SAFE_ID.fullmatch(build.replace(".", "_")):
            raise ValueError("pinned actor build required")
        self.client, self.token, self.build = client, token, build

    async def _request(self, method, path, *, params=None, body=None):
        # HTTPX's read timeout bounds idle gaps, not the lifetime of a streaming body.
        async with asyncio.timeout(REQUEST_TIMEOUT_SECONDS):
            return await self._read_request(method, path, params=params, body=body)

    async def _read_request(self, method, path, *, params=None, body=None):
        async with self.client.stream(method, "https://api.apify.com/v2/" + path,
            headers={"Authorization": "Bearer " + self.token}, params=params, json=body,
            timeout=httpx.Timeout(3), follow_redirects=False) as response:
            if method == "DELETE" and response.status_code == 404:
                return {}  # Idempotent cleanup after a partial worker attempt.
            response.raise_for_status()
            chunks, size = [], 0
            async for chunk in response.aiter_bytes():
                size += len(chunk)
                if size > 65536:
                    raise ValueError("provider body limit")
                chunks.append(chunk)
            if not size:
                return {}
            import json
            return json.loads(b"".join(chunks))

    @staticmethod
    def _id(value):
        if not value or not SAFE_ID.fullmatch(value):
            raise ValueError("invalid provider reference")
        return value

    async def start(self, *, category: str, area: str) -> ProviderRunRef:
        if category not in CATEGORIES or not 2 <= len(area) <= 120:
            raise ValueError("invalid Maps request")
        data = (await self._request("POST", "acts/compass~crawler-google-places/runs",
            params={"waitForFinish": "0", "timeout": "60", "maxTotalChargeUsd": MAX_TOTAL_CHARGE_USD,
                    "restartOnError": "false", "build": self.build},
            body={"searchStringsArray": [CATEGORIES[category]], "locationQuery": area,
                "maxCrawledPlacesPerSearch": 5, "language": "vi", "scrapePlaceDetailPage": False,
                "scrapeContacts": False, "maxReviews": 0, "maxImages": 0,
                "maximumLeadsEnrichmentRecords": 0}))['data']
        return ProviderRunRef(self._id(data["id"]), self._id(data["defaultDatasetId"]),
            {kind: self._id(data[key]) for kind, key in (("key-value-stores", "defaultKeyValueStoreId"),
             ("request-queues", "defaultRequestQueueId")) if data.get(key)})

    async def status(self, ref: ProviderRunRef) -> ProviderRunStatus:
        try:
            data = (await self._request("GET", f"actor-runs/{self._id(ref.run_id)}"))["data"]
        except httpx.HTTPStatusError as error:
            if error.response.status_code == 404:
                return ProviderRunStatus("missing")
            raise
        state = {"READY": "pending", "RUNNING": "pending", "SUCCEEDED": "succeeded", "FAILED": "failed",
                 "TIMED-OUT": "timed_out", "ABORTED": "aborted", "ABORTING": "pending", "TIMING-OUT": "pending"}.get(data["status"])
        if state is None:
            raise ValueError("unknown actor state")
        charge = data.get("usageTotalUsd")
        money = Decimal(str(charge)) if charge is not None else None
        if money is not None and (not money.is_finite() or money < 0):
            raise ValueError("invalid usage")
        return ProviderRunStatus(state, money)

    async def results(self, ref: ProviderRunRef) -> list[PlaceResult]:
        rows = await self._request("GET", f"datasets/{self._id(ref.dataset_id)}/items",
            params={"limit": 5, "clean": "true", "format": "json"})
        if not isinstance(rows, list):
            raise ValueError("invalid dataset")
        places = []
        for row in rows[:5]:
            if not isinstance(row, dict) or not isinstance(row.get("title"), str) or not row["title"].strip():
                continue
            name, address = row["title"][:200], str(row.get("address") or "")[:300]
            identity = row.get("placeId")
            identity = identity if isinstance(identity, str) and SAFE_ID.fullmatch(identity) else None
            query = {"api": "1", "query": name + " " + address}
            if identity:
                query["query_place_id"] = identity
            rating, count = row.get("totalScore"), row.get("reviewsCount")
            rating = rating if isinstance(rating, (int, float)) and not isinstance(rating, bool) and 0 <= rating <= 5 else None
            count = count if isinstance(count, int) and not isinstance(count, bool) and count >= 0 else None
            hours = row.get("openingHours")
            hours = [f"{h['day'][:30]}: {h['hours'][:100]}" for h in hours[:7]
                if isinstance(h, dict) and isinstance(h.get("day"), str) and isinstance(h.get("hours"), str)] if isinstance(hours, list) else None
            places.append(PlaceResult(place_id=identity, name=name, category=str(row["categoryName"])[:100] if row.get("categoryName") else None,
                address=address, rating=rating, rating_count=count, opening_hours=hours,
                maps_url="https://www.google.com/maps/search/?" + urlencode(query), fetched_at=now()))
        return places

    async def abort(self, ref):
        await self._request("POST", f"actor-runs/{self._id(ref.run_id)}/abort")

    async def cleanup(self, ref):
        # Remove input/KV, queue, dataset and run metadata/logs; fixed types and validated IDs.
        for kind, identity in ref.storage_refs.items():
            if kind not in ("key-value-stores", "request-queues"):
                raise ValueError("invalid storage kind")
            await self._request("DELETE", f"{kind}/{self._id(identity)}")
        if ref.dataset_id:
            await self._request("DELETE", f"datasets/{self._id(ref.dataset_id)}")
        await self._request("DELETE", f"actor-runs/{self._id(ref.run_id)}")
