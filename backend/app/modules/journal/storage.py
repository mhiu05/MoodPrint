"""Private Storage control plane; large bytes travel browser-to-Storage only."""

import logging
import re
from datetime import timedelta
from urllib.parse import parse_qs, quote, urlsplit

import httpx
from sqlalchemy import delete, select, update

from app.core.errors import DomainError
from app.infrastructure.database.models import now
from app.modules.journal.models import JournalMedia, JournalStorageDeletion
from app.modules.journal.service import queue_media_deletion

BUCKET = "journal-media"
READ_TTL = 60
# Upload tokens last 2h. Delay from queue insertion also covers a token renewed just before erase.
DELETE_DELAY = timedelta(hours=2, minutes=5)
MEDIA_LIMITS = {"image": 10 * 1024**2, "audio": 20 * 1024**2, "video": 50 * 1024**2}
MIME_EXTENSIONS = {
    "image/jpeg": ("image", "jpg"),
    "image/png": ("image", "png"),
    "image/webp": ("image", "webp"),
    "image/gif": ("image", "gif"),
    "audio/webm": ("audio", "webm"),
    "audio/ogg": ("audio", "ogg"),
    "audio/mp4": ("audio", "m4a"),
    "audio/mpeg": ("audio", "mp3"),
    "audio/wav": ("audio", "wav"),
    "video/mp4": ("video", "mp4"),
    "video/webm": ("video", "webm"),
    "video/quicktime": ("video", "mov"),
}


def storage_origins(value: str) -> tuple[str, ...]:
    if not value:
        return ()
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
        or not re.fullmatch(r"[A-Za-z0-9.-]+", parsed.netloc)
    ):
        raise ValueError("Journal Storage requires a plain HTTPS provider origin")
    origin = f"https://{parsed.hostname}"
    if parsed.hostname.endswith(".supabase.co") and not parsed.hostname.endswith(
        ".storage.supabase.co"
    ):
        direct = f"https://{parsed.hostname.removesuffix('.supabase.co')}.storage.supabase.co"
        return origin, direct
    return (origin,)


def unavailable() -> DomainError:
    return DomainError(
        503,
        "MEDIA_UNAVAILABLE",
        "Tệp đính kèm chưa sẵn sàng. Bạn có thể lưu bản nháp và thử lại.",
        retryable=True,
    )


class SupabaseJournalStorage:
    def __init__(self, settings, *, transport=None):
        origins = storage_origins(settings.supabase_url)
        self.origin = origins[0] if origins else ""
        self.direct_origin = origins[-1] if origins else ""
        self.key = settings.journal_storage_key.get_secret_value()
        self.transport = transport

    @property
    def available(self) -> bool:
        return bool(self.origin and self.key)

    async def _request(self, method, path, *, body=None, missing_ok=False):
        if not self.available:
            raise unavailable()
        try:
            async with httpx.AsyncClient(
                transport=self.transport, timeout=15, follow_redirects=False
            ) as client:
                response = await client.request(
                    method,
                    f"{self.origin}/storage/v1/{path}",
                    headers={"Authorization": f"Bearer {self.key}", "apikey": self.key},
                    json=body,
                )
            if response.status_code == 404 and missing_ok:
                return None
            if response.status_code == 400 and missing_ok:
                detail = response.json()
                if isinstance(detail, dict) and detail.get("error") in ("not_found", "NoSuchKey"):
                    return None
            if not response.is_success:
                raise unavailable()
            return response.json()
        except (httpx.HTTPError, ValueError):
            raise unavailable() from None

    async def _private_bucket(self):
        bucket = await self._request("GET", f"bucket/{BUCKET}")
        if not isinstance(bucket, dict) or bucket.get("public") is not False:
            raise unavailable()

    def _public_url(self, raw: str) -> str:
        url = raw if raw.startswith("https://") else f"{self.origin}/storage/v1/{raw.lstrip('/')}"
        parsed = urlsplit(url)
        if f"{parsed.scheme}://{parsed.netloc}" != self.origin or not parsed.path.startswith(
            "/storage/v1/object/"
        ):
            raise unavailable()
        return url

    async def sign_upload(self, path: str) -> dict:
        await self._private_bucket()
        result = await self._request(
            "POST", f"object/upload/sign/{BUCKET}/{quote(path, safe='/')}", body={}
        )
        if not isinstance(result, dict) or not isinstance(result.get("url"), str):
            raise unavailable()
        url = self._public_url(result["url"])
        token = parse_qs(urlsplit(url).query).get("token", [""])[0]
        if not token:
            raise unavailable()
        return {
            "uploadUrl": url,
            "token": token,
            "resumableUrl": f"{self.direct_origin}/storage/v1/upload/resumable/sign",
            "objectPath": path,
            "bucket": BUCKET,
        }

    async def info(self, path: str) -> dict | None:
        result = await self._request(
            "GET", f"object/info/{BUCKET}/{quote(path, safe='/')}", missing_ok=True
        )
        if result is None:
            return None
        if not isinstance(result, dict):
            raise unavailable()
        # Info v2's nested metadata is caller-controlled user metadata, never authoritative.
        # Only legacy info responses without either canonical field may use nested object metadata.
        metadata = (
            result if "size" in result or "content_type" in result else result.get("metadata")
        )
        if not isinstance(metadata, dict):
            raise unavailable()
        return {
            "size": metadata.get("size"),
            "contentType": metadata.get(
                "content_type", metadata.get("mimetype", metadata.get("contentType"))
            ),
        }

    async def sign_read(self, path: str) -> str:
        await self._private_bucket()
        result = await self._request(
            "POST", f"object/sign/{BUCKET}/{quote(path, safe='/')}", body={"expiresIn": READ_TTL}
        )
        if not isinstance(result, dict) or not isinstance(result.get("signedURL"), str):
            raise unavailable()
        return self._public_url(result["signedURL"])

    async def delete(self, path: str) -> None:
        await self._request(
            "DELETE", f"object/{BUCKET}", body={"prefixes": [path]}, missing_ok=True
        )


async def process_storage_cleanup(app) -> None:
    storage = getattr(app.state, "journal_storage", None)
    if storage is None or not app.state.database.sessions:
        return
    # Capture work under short transactions; never await provider IO while holding an owner lock.
    async with app.state.database.sessions.begin() as db:
        abandoned = (
            await db.scalars(
                select(JournalMedia)
                .where(
                    JournalMedia.status == "pending",
                    JournalMedia.created_at < now() - timedelta(hours=24),
                )
                .order_by(JournalMedia.created_at)
                .limit(100)
                .with_for_update(skip_locked=True)
            )
        ).all()
        for item in abandoned:
            await queue_media_deletion(db, item)
            await db.delete(item)
        jobs = [
            (j.id, j.object_path)
            for j in (
                await db.scalars(
                    select(JournalStorageDeletion)
                    .where(JournalStorageDeletion.created_at < now() - DELETE_DELAY)
                    .order_by(JournalStorageDeletion.created_at)
                    .limit(50)
                )
            ).all()
        ]
    for job_id, path in jobs:
        try:
            await storage.delete(path)
        except DomainError:
            async with app.state.database.sessions.begin() as db:
                await db.execute(
                    update(JournalStorageDeletion)
                    .where(JournalStorageDeletion.id == job_id)
                    .values(attempts=JournalStorageDeletion.attempts + 1)
                )
            logging.getLogger("moodprint").warning("journal_cleanup_retry")
        else:
            async with app.state.database.sessions.begin() as db:
                await db.execute(
                    delete(JournalStorageDeletion).where(JournalStorageDeletion.id == job_id)
                )
