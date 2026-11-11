import httpx
from safevoice_shared.contracts.auth import AuthContext
from safevoice_shared.env import EnvSettings

from app.core.errors import ApiError


class AuthAdmin:
    def __init__(self, settings: EnvSettings, http: httpx.AsyncClient):
        self.url = settings.supabase_url.rstrip("/") + "/auth/v1"
        self.secret = settings.supabase_secret_key
        self.http = http

    async def user_metadata(self, auth: AuthContext, token: str) -> dict:
        try:
            response = await self.http.get(
                self.url + "/user",
                headers={
                    "apikey": self.secret.get_secret_value(),
                    "Authorization": f"Bearer {token}",
                },
            )
        except httpx.HTTPError as error:
            raise ApiError("upstream_error", "Chưa kiểm tra được phiên đăng nhập.", 502) from error
        if response.status_code in (401, 403, 404):
            raise ApiError("unauthenticated", "Phiên đăng nhập không còn hiệu lực.", 401)
        if response.status_code != 200:
            raise ApiError("upstream_error", "Chưa kiểm tra được phiên đăng nhập.", 502)
        if response.json().get("id") != str(auth.user_id):
            raise ApiError("unauthenticated", "Phiên đăng nhập không còn hiệu lực.", 401)
        metadata = response.json().get("user_metadata")
        return metadata if isinstance(metadata, dict) else {}

    async def require_live_user(self, auth: AuthContext, token: str) -> None:
        await self.user_metadata(auth, token)

    async def delete_user(self, auth: AuthContext) -> None:
        try:
            response = await self.http.delete(
                self.url + "/admin/users/" + str(auth.user_id),
                headers={
                    "apikey": self.secret.get_secret_value(),
                    "Authorization": "Bearer " + self.secret.get_secret_value(),
                },
            )
        except httpx.HTTPError as error:
            raise ApiError(
                "upstream_error", "Chưa thể xóa tài khoản. Vui lòng thử lại.", 502
            ) from error
        if response.status_code not in (200, 204, 404):
            raise ApiError("upstream_error", "Chưa thể xóa tài khoản. Vui lòng thử lại.", 502)
