"""Server-to-Supabase Auth calls. Errors never carry provider bodies, tokens or passwords."""

import base64
import json
import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

import httpx
from fastapi import Request

from app.core.errors import DomainError


@dataclass(frozen=True)
class ProviderSession:
    user_id: UUID
    session_id: UUID
    access_token: str = field(repr=False)
    expires_at: datetime
    # Verified against both the signed claims and the provider's own user record.
    is_anonymous: bool


class AnonymousSignupError(DomainError):
    """The single anonymous signup was rejected (nothing created) or is ambiguous (maybe created)."""

    def __init__(
        self,
        outcome: Literal["rejected", "ambiguous"],
        status: int,
        code: str,
        message: str,
        retryable: bool = False,
    ):
        super().__init__(status, code, message, retryable)
        self.outcome = outcome


def _unavailable() -> DomainError:
    return DomainError(503, "AUTH_UNAVAILABLE", "Chưa kết nối được dịch vụ đăng nhập.", True)


def _rate_limited() -> DomainError:
    return DomainError(
        429, "AUTH_RATE_LIMITED", "Bạn đã thử quá nhiều lần. Vui lòng đợi vài phút.", True
    )


def _registered_required() -> DomainError:
    return DomainError(403, "REGISTERED_REQUIRED", "Tính năng này cần tài khoản đã đăng ký.")


def _signup_ambiguous() -> AnonymousSignupError:
    return AnonymousSignupError(
        "ambiguous", 503, "AUTH_UNAVAILABLE", "Chưa kết nối được dịch vụ đăng nhập.", True
    )


def _signup_rejected(response: httpx.Response) -> AnonymousSignupError:
    code = _error_code(response)
    if response.status_code == 429:
        return AnonymousSignupError(
            "rejected",
            429,
            "AUTH_RATE_LIMITED",
            "Bạn đã thử quá nhiều lần. Vui lòng đợi vài phút.",
            True,
        )
    if code == "captcha_failed":
        return AnonymousSignupError(
            "rejected",
            422,
            "CAPTCHA_FAILED",
            "Chưa xác minh được bước kiểm tra an toàn. Vui lòng thử lại.",
            True,
        )
    if code in ("anonymous_provider_disabled", "signup_disabled"):
        return AnonymousSignupError(
            "rejected", 503, "GUEST_DISABLED", "Dùng thử tạm thời chưa mở. Vui lòng quay lại sau."
        )
    return AnonymousSignupError(
        "rejected", 503, "AUTH_UNAVAILABLE", "Chưa kết nối được dịch vụ đăng nhập."
    )


def _error_code(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return ""
    if not isinstance(body, dict):
        return ""
    return str(body.get("error_code") or body.get("code") or body.get("error") or "")


def _audience_ok(audience: object) -> bool:
    return audience == "authenticated" or (
        isinstance(audience, list) and "authenticated" in audience
    )


def _strict_bool(value: object) -> bool:
    # A missing, string or numeric flag must fail closed rather than read as "permanent".
    if not isinstance(value, bool):
        raise ValueError("Provider anonymous flag must be an explicit boolean")
    return value


def _future_expiry(value: object) -> datetime:
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        raise ValueError("Provider expiry must be a finite number")
    expiry = datetime.fromtimestamp(value, UTC)
    if expiry <= datetime.now(UTC):
        raise ValueError("Provider token already expired")
    return expiry


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

    async def _send(self, method: str, path: str, **kwargs) -> httpx.Response:
        """One raw provider exchange; transport failures propagate for callers that classify them."""
        async with self.client() as provider:
            return await provider.request(
                method, self.base + path, headers={**self.headers, **kwargs.pop("headers", {})}, **kwargs
            )

    async def _call(self, method: str, path: str, **kwargs) -> httpx.Response:
        try:
            response = await self._send(method, path, **kwargs)
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
        session = await self.verify_token(token)
        if session.is_anonymous:
            # A password exchange can only ever yield a permanent identity.
            raise _registered_required()
        return session

    async def verify_token(self, token: str) -> ProviderSession:
        verified = await self._call("GET", "/user", headers={"Authorization": f"Bearer {token}"})
        if verified.status_code != 200:
            raise DomainError(401, "LOGIN_FAILED", "Không xác minh được phiên đăng nhập.")
        try:
            profile = verified.json()
            uid = UUID(profile["id"])
            # Claims are read only after the provider itself accepted this token above.
            encoded = token.split(".")[1]
            claims = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
            if UUID(claims["sub"]) != uid or claims["iss"] != self.issuer:
                raise ValueError("Provider token mismatch")
            if not _audience_ok(claims.get("aud")):
                raise ValueError("Provider token audience mismatch")
            expiry = _future_expiry(claims["exp"])
            anonymous = _strict_bool(claims.get("is_anonymous"))
            if anonymous != _strict_bool(profile.get("is_anonymous")):
                raise ValueError("Provider anonymous classification disagrees")
            return ProviderSession(uid, UUID(claims["session_id"]), token, expiry, anonymous)
        except (ValueError, KeyError, TypeError, IndexError, AttributeError, OverflowError, OSError):
            raise _unavailable() from None

    async def anonymous_session(self, captcha_token: str, *, correlation_id: str) -> ProviderSession:
        """Create exactly one anonymous identity and return it only once fully verified.

        Never retried here. After the request is on the wire every unverifiable outcome is
        ``ambiguous`` (the provider may have created an identity); only an explicit 4xx is a
        ``rejected`` outcome that proves nothing was created.
        """
        try:
            response = await self._send(
                "POST",
                "/signup",
                json={
                    "data": {"moodprint_guest_attempt": correlation_id},
                    "gotrue_meta_security": {"captcha_token": captcha_token},
                },
            )
        except httpx.HTTPError:
            raise _signup_ambiguous() from None
        if 400 <= response.status_code < 500:
            raise _signup_rejected(response)
        if response.status_code not in (200, 201):
            raise _signup_ambiguous()
        try:
            token = response.json()["access_token"]
            if not isinstance(token, str) or not token:
                raise ValueError("Missing provider access token")
        except (ValueError, KeyError, TypeError):
            raise _signup_ambiguous() from None
        try:
            provider = await self.verify_token(token)
        except DomainError:
            raise _signup_ambiguous() from None
        if not provider.is_anonymous:
            raise _signup_ambiguous()
        return provider

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
        if session.is_anonymous:
            # A bearer token must never become an implicit guest-to-permanent conversion route.
            raise _registered_required()
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
