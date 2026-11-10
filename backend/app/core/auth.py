"""Async JWKS verification, with bounded unknown-key refresh and no JWT logging."""

import asyncio
import json
import time
from typing import Annotated, Any
from uuid import UUID

import httpx
import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from moodprint_shared.config import AppConfig
from moodprint_shared.contracts.auth import AuthContext
from moodprint_shared.contracts.errors import DomainError
from moodprint_shared.env import EnvSettings

from app.core.errors import ApiError


def unauthenticated() -> DomainError:
    return ApiError("unauthenticated", "Phiên đăng nhập không hợp lệ hoặc đã hết hạn.", 401)


class JwtVerifier:
    def __init__(self, settings: EnvSettings, cfg: AppConfig, http: httpx.AsyncClient):
        self.settings, self.cfg, self.http = settings, cfg, http
        self.keys: dict[str, Any] = {}
        self.fetched_at = 0.0
        self.unknown_refreshed_at = float("-inf")
        self.lock = asyncio.Lock()

    async def refresh(self) -> None:
        try:
            response = await self.http.get(
                self.settings.supabase_url.rstrip("/") + "/auth/v1/.well-known/jwks.json",
                timeout=10,
            )
            response.raise_for_status()
            raw_keys = response.json()["keys"]
            keys = {
                item["kid"]: jwt.PyJWK.from_dict(item, algorithm="ES256").key
                for item in raw_keys
                if item.get("alg") == "ES256" and item.get("kty") == "EC"
            }
            if not keys:
                raise ValueError("empty JWKS")
        except (httpx.HTTPError, ValueError, KeyError, jwt.PyJWTError) as from_error:
            raise ApiError(
                "not_ready", "Dịch vụ xác thực tạm thời chưa sẵn sàng.", 503
            ) from from_error
        self.keys = keys
        self.fetched_at = time.monotonic()

    async def verify(self, token: str) -> AuthContext:
        try:
            header = jwt.get_unverified_header(token)
            alg, kid = header.get("alg"), header.get("kid")
            test_secret = self.settings.auth_test_jwt_secret
            if alg == "HS256" and self.settings.app_env == "test" and test_secret:
                key = test_secret.get_secret_value()
            elif alg == "ES256" and isinstance(kid, str):
                async with self.lock:
                    now = time.monotonic()
                    if not self.keys or now - self.fetched_at >= self.cfg.api.jwks_cache_ttl_s:
                        await self.refresh()
                    if (
                        kid not in self.keys
                        and now - self.unknown_refreshed_at
                        >= self.cfg.api.jwks_unknown_kid_refresh_s
                    ):
                        self.unknown_refreshed_at = now
                        await self.refresh()
                    key = self.keys.get(kid)
                if key is None:
                    raise unauthenticated()
            else:
                raise unauthenticated()
            claims = jwt.decode(
                token,
                key,
                algorithms=[alg],
                audience="authenticated",
                issuer=self.settings.supabase_url.rstrip("/") + "/auth/v1",
                # Hosted issuer clocks may lead this machine slightly. Check only
                # iat with bounded skew below; exp and nbf retain strict validation.
                options={"require": ["exp", "sub", "aud", "iss", "role"], "verify_iat": False},
            )
            if "iat" in claims:
                issued_at = claims["iat"]
                if (
                    isinstance(issued_at, bool)
                    or not isinstance(issued_at, int)
                    or issued_at > time.time() + self.cfg.api.jwt_iat_clock_skew_s
                ):
                    raise unauthenticated()
            if claims.get("role") != "authenticated" or claims.get("is_anonymous") is True:
                raise unauthenticated()
            user_id = UUID(claims["sub"])
            verified = {
                name: claims[name]
                for name in ("sub", "role", "aud", "iss", "exp", "session_id", "aal")
                if name in claims
            }
            return AuthContext(
                user_id=user_id,
                session_id=claims.get("session_id"),
                aal=claims.get("aal"),
                claims_json=json.dumps(verified, ensure_ascii=False),
            )
        except (jwt.PyJWTError, ValueError, TypeError, KeyError) as error:
            raise unauthenticated() from error


def bearer_token(request: Request) -> str:
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise unauthenticated()
    return token


async def get_auth(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(HTTPBearer(auto_error=False))
    ],
) -> AuthContext:
    token = bearer_token(request)
    verifier: JwtVerifier | None = getattr(request.app.state, "verifier", None)
    if verifier is None:
        raise ApiError("not_ready", "Dịch vụ xác thực chưa sẵn sàng.", 503)
    return await verifier.verify(token)
