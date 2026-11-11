"""Only gateway to privileged Supabase Storage. No object replacement operation."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

import httpx
from safevoice_shared.config import AppConfig
from safevoice_shared.env import EnvSettings

from app.core.errors import ApiError


@dataclass(frozen=True, slots=True)
class SignedUpload:
    url: str
    token: str
    chunk_size: int
    object_name: str
    bucket_name: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class ObjectInfo:
    byte_size: int
    mime_type: str | None
    etag: str | None


class StorageGateway:
    def __init__(self, settings: EnvSettings, cfg: AppConfig, http: httpx.AsyncClient):
        self.base = settings.supabase_url.rstrip("/")
        self.cfg, self.http = cfg.evidence, http
        self.secret = settings.supabase_secret_key

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        try:
            response = await self.http.request(
                method,
                self.base + "/storage/v1" + path,
                headers={
                    "apikey": self.secret.get_secret_value(),
                    "Authorization": "Bearer " + self.secret.get_secret_value(),
                },
                **kwargs,
            )
        except httpx.HTTPError as error:
            raise ApiError("upstream_error", "Kho tệp tạm thời chưa sẵn sàng.", 502) from error
        missing_object = False
        if response.status_code == 400:
            try:
                body = response.json()
                missing_object = body.get("statusCode") == "404" and body.get("code") == "NoSuchKey"
            except ValueError:
                pass
        if response.status_code >= 400 and response.status_code != 404 and not missing_object:
            raise ApiError("upstream_error", "Không thể hoàn tất thao tác với tệp.", 502)
        return response

    def _object(self, key: str) -> str:
        if not key.startswith("users/") or ".." in key or "\\" in key:
            raise ValueError("Invalid storage object key")
        return quote(self.cfg.bucket, safe="") + "/" + quote(key, safe="/")

    async def create_upload_token(self, key: str) -> SignedUpload:
        response = await self._request("POST", "/object/upload/sign/" + self._object(key), json={})
        data = response.json()
        if response.status_code != 200 or not data.get("token"):
            raise ApiError("upstream_error", "Chưa tạo được quyền tải tệp lên.", 502)
        endpoint = self.base + "/storage/v1/upload/resumable/sign"
        if self.base.endswith(".supabase.co"):
            endpoint = (
                self.base.replace(".supabase.co", ".storage.supabase.co")
                + "/storage/v1/upload/resumable/sign"
            )
        return SignedUpload(
            endpoint,
            data["token"],
            self.cfg.upload_chunk_bytes,
            key,
            self.cfg.bucket,
            datetime.now(UTC) + timedelta(hours=2),
        )

    async def object_info(self, key: str) -> ObjectInfo | None:
        response = await self._request("GET", "/object/info/" + self._object(key))
        if response.status_code == 404 or (
            response.status_code == 400 and response.json().get("code") == "NoSuchKey"
        ):
            return None
        data = response.json()
        metadata = data.get("metadata") or {}
        return ObjectInfo(
            int(metadata.get("size", data.get("size", 0))),
            metadata.get("mimetype") or data.get("content_type") or data.get("contentType"),
            metadata.get("eTag") or data.get("etag") or data.get("eTag"),
        )

    async def create_download_url(
        self, key: str, ttl_s: int, *, attachment_name: str | None
    ) -> str:
        if not 1 <= ttl_s <= self.cfg.download_url_ttl_s:
            raise ValueError("Invalid download URL lifetime")
        response = await self._request(
            "POST", "/object/sign/" + self._object(key), json={"expiresIn": ttl_s}
        )
        signed = response.json().get("signedURL") or response.json().get("signedUrl")
        if not isinstance(signed, str) or not signed.startswith("/object/sign/"):
            raise ApiError("upstream_error", "Chưa tạo được quyền tải tệp xuống.", 502)
        url = self.base + "/storage/v1" + signed
        if attachment_name:
            url += ("&" if "?" in url else "?") + "download=" + quote(attachment_name, safe="")
        return url

    async def delete(self, keys: list[str]) -> None:
        if not keys:
            return
        for key in keys:
            self._object(key)
        response = await self._request(
            "DELETE", "/object/" + quote(self.cfg.bucket, safe=""), json={"prefixes": keys}
        )
        if response.status_code >= 400:
            raise ApiError("upstream_error", "Chưa xóa được tệp. Hệ thống sẽ thử lại.", 502)
