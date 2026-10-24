"""Server-to-Supabase Auth calls. Errors never carry provider bodies, tokens or passwords."""

import base64
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

import httpx
from fastapi import Request

from app.core.errors import DomainError


@dataclass(frozen=True)
class ProviderSession:
    user_id: UUID
    session_id: UUID
    access_token: str
    expires_at: datetime


def _unavailable() -> DomainError:
    return DomainError(503, "AUTH_UNAVAILABLE", "Chưa kết nối được dịch vụ đăng nhập.", True)


def _rate_limited() -> DomainError:
    return DomainError(
        429, "AUTH_RATE_LIMITED", "Bạn đã thử quá nhiều lần. Vui lòng đợi vài phút.", True
    )


def _error_code(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return ""
    return str(body.get("error_code") or body.get("code") or body.get("error") or "")


class SupabaseAuth:
    def __init__(self, request: Request):
        settings = request.app.state.settings
        if not settings.supabase_url or not settings.supabase_publishable_key.get_secret_value():
            raise DomainError(503, "AUTH_UNAVAILABLE", "Đăng nhập chưa sẵn sàng.", True)
        self.base = f"{settings.supabase_url}/auth/v1"
        self.issuer = self.base
        self.headers = {"apikey": settings.supabase_publishable_key.get_secret_value()}
        self.transport = getattr(request.app.state, "auth_transport", None)
        self.redirect = settings.frontend_origin.rstrip("/") + "/auth/callback"

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=10, follow_redirects=False, transport=self.transport)

    async def _call(self, method: str, path: str, **kwargs) -> httpx.Response:
        try:
            async with self.client() as provider:
                response = await provider.request(
                    method, self.base + path, headers={**self.headers, **kwargs.pop("headers", {})}, **kwargs
                )
        except httpx.HTTPError:
            raise _unavailable() from None
        if response.status_code == 429:
            raise _rate_limited()
        if response.status_code >= 500:
            raise _unavailable()
        return response

    async def password_session(self, email: str, password: str) -> ProviderSession:
        auth = await self._call(
            "POST", "/token?grant_type=password", json={"email": email, "password": password}
        )
        if auth.status_code != 200:
            if _error_code(auth) == "email_not_confirmed":
                raise DomainError(
                    403,
                    "EMAIL_NOT_CONFIRMED",
                    "Email chưa được xác nhận. Hãy mở thư xác nhận hoặc gửi lại thư.",
                )
            raise DomainError(401, "LOGIN_FAILED", "Email hoặc mật khẩu chưa đúng.")
        try:
            token = auth.json()["access_token"]
        except (ValueError, KeyError, TypeError):
            raise _unavailable() from None
        return await self.verify_token(token)

    async def verify_token(self, token: str) -> ProviderSession:
        verified = await self._call("GET", "/user", headers={"Authorization": f"Bearer {token}"})
        if verified.status_code != 200:
            raise DomainError(401, "LOGIN_FAILED", "Không xác minh được phiên đăng nhập.")
        try:
            uid = UUID(verified.json()["id"])
            # Claims are read only after the provider itself accepted this token above.
            encoded = token.split(".")[1]
            claims = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
            if UUID(claims["sub"]) != uid or claims["iss"] != self.issuer:
                raise ValueError("Provider token mismatch")
            expiry = datetime.fromtimestamp(claims["exp"], UTC)
            return ProviderSession(uid, UUID(claims["session_id"]), token, expiry)
        except (ValueError, KeyError, TypeError, IndexError):
            raise _unavailable() from None

    async def sign_out(self, token: str) -> None:
        # Best effort: ends only the provider session created for a step-up check.
        try:
            await self._call(
                "POST", "/logout?scope=local", headers={"Authorization": f"Bearer {token}"}
            )
        except DomainError:
            pass

    async def sign_up(self, email: str, password: str) -> None:
        response = await self._call(
            "POST",
            "/signup",
            params={"redirect_to": self.redirect},
            json={"email": email, "password": password},
        )
        if response.status_code in (200, 201):
            return
        code = _error_code(response)
        if code == "weak_password":
            raise DomainError(422, "WEAK_PASSWORD", "Mật khẩu quá yếu. Hãy dùng ít nhất 8 ký tự khó đoán.")
        if code == "signup_disabled":
            raise DomainError(403, "SIGNUP_DISABLED", "Đăng ký tài khoản mới đang tạm đóng.")
        if code in ("email_address_invalid", "validation_failed"):
            raise DomainError(422, "EMAIL_INVALID", "Email chưa hợp lệ.")
        if code in ("user_already_exists", "email_exists"):
            # Same outcome as a new sign-up so the endpoint does not reveal registrations.
            return
        raise _unavailable()

    async def resend_confirmation(self, email: str) -> None:
        response = await self._call(
            "POST",
            "/resend",
            params={"redirect_to": self.redirect},
            json={"type": "signup", "email": email},
        )
        if response.status_code not in (200, 400, 422):
            raise _unavailable()

    async def request_recovery(self, email: str) -> None:
        response = await self._call(
            "POST", "/recover", params={"redirect_to": self.redirect}, json={"email": email}
        )
        # Unknown addresses look identical to known ones.
        if response.status_code not in (200, 400, 404, 422):
            raise _unavailable()

    async def update_password(self, token: str, password: str) -> UUID:
        session = await self.verify_token(token)
        response = await self._call(
            "PUT",
            "/user",
            headers={"Authorization": f"Bearer {token}"},
            json={"password": password},
        )
        if response.status_code == 200:
            return session.user_id
        code = _error_code(response)
        if code == "weak_password":
            raise DomainError(422, "WEAK_PASSWORD", "Mật khẩu quá yếu. Hãy dùng ít nhất 8 ký tự khó đoán.")
        if code == "same_password":
            raise DomainError(422, "SAME_PASSWORD", "Mật khẩu mới phải khác mật khẩu cũ.")
        raise DomainError(401, "RECOVERY_EXPIRED", "Liên kết đặt lại mật khẩu đã hết hạn.")

