import base64
import json
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.contracts import ConsentView, EligibilityInput, FeatureView, LoginInput, SessionView
from app.core.errors import DomainError
from app.core.security import (
    Actor,
    digest,
    idempotency_key,
    previous_receipt,
    require_actor,
    save_receipt,
    transaction,
)
from app.infrastructure.database.models import AgeDeclaration, AuthSession, Consent, User, now
from app.modules.auth.age import record_age

router = APIRouter()


async def session_view(request: Request, actor: Actor, csrf: str | None = None) -> SessionView:
    async with transaction(request, actor, eligible=False) as (db, user):
        consents = (await db.scalars(select(Consent).where(Consent.user_id == user.id))).all()
        declaration = await db.get(AgeDeclaration, user.id)
        return SessionView(
            user_id=user.id,
            alias=user.alias,
            age_band=user.age_band,
            eligible=user.age_band in ("teen", "adult"),
            consents={c.purpose: ConsentView.model_validate(c) for c in consents},
            csrf_token=csrf
            or request.cookies.get("moodprint_csrf")
            or request.headers.get("X-CSRF-Token", ""),
            server_time=now(),
            timezone=user.timezone,
            data_version=user.data_version,
            birth_year=declaration.birth_year if declaration else None,
            eligibility_version=declaration.version if declaration else 0,
            features=FeatureView(
                ai=request.app.state.ai.available_for(actor.user_id),
                matching=True,
                voice=request.app.state.transcriber is not None and (
                    not request.app.state.settings.ai_local_test_user_ids
                    or request.app.state.ai.available_for(actor.user_id)
                ),
            ),
        )


@router.get("/session", response_model=SessionView)
async def get_session(request: Request, actor: Actor = Depends(require_actor)):
    return await session_view(request, actor)


@router.put("/users/me/eligibility", response_model=SessionView)
async def declare_eligibility(
    body: EligibilityInput, request: Request, actor: Actor = Depends(require_actor)
):
    key, payload = idempotency_key(request), body.model_dump(mode="json")
    changed = False
    async with transaction(request, actor, eligible=False) as (db, user):
        previous = await previous_receipt(db, user, "eligibility:declare", key, payload)
        if not previous:
            declaration, changed = await record_age(db, user, body)
            save_receipt(
                db,
                user,
                "eligibility:declare",
                key,
                payload,
                {"resourceId": str(user.id), "resourceVersion": declaration.version},
            )
    if changed:
        request.app.state.ai.invalidate(str(actor.user_id))
    return await session_view(request, actor)


@router.post("/auth/login", response_model=SessionView)
async def login(body: LoginInput, request: Request, response: Response):
    settings = request.app.state.settings
    if not settings.supabase_url or not settings.supabase_publishable_key.get_secret_value():
        raise DomainError(503, "AUTH_UNAVAILABLE", "Đăng nhập chưa sẵn sàng.", True)
    request.app.state.database.require()
    origin = request.headers.get("Origin")
    if origin and origin.rstrip("/") != settings.frontend_origin.rstrip("/"):
        raise DomainError(403, "ORIGIN_DENIED", "Nguồn yêu cầu không hợp lệ.")
    headers = {"apikey": settings.supabase_publishable_key.get_secret_value()}
    # Password verification, hashing and account recovery remain Supabase's responsibility.
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=False) as provider:
            auth = await provider.post(
                f"{settings.supabase_url}/auth/v1/token?grant_type=password",
                json=body.model_dump(),
                headers=headers,
            )
            if auth.status_code != 200:
                raise DomainError(401, "LOGIN_FAILED", "Email hoặc mật khẩu chưa đúng.")
            data = auth.json()
            token = data["access_token"]
            verified = await provider.get(
                f"{settings.supabase_url}/auth/v1/user",
                headers={**headers, "Authorization": f"Bearer {token}"},
            )
            if verified.status_code != 200:
                raise DomainError(401, "LOGIN_FAILED", "Không xác minh được phiên đăng nhập.")
            uid = UUID(verified.json()["id"])
            # This JWT comes only from the trusted server-to-provider token exchange above;
            # no endpoint accepts arbitrary client JWTs or trusts editable user_metadata.
            encoded = token.split(".")[1]
            claims = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
            if UUID(claims["sub"]) != uid or claims["iss"] != f"{settings.supabase_url}/auth/v1":
                raise ValueError("Provider token mismatch")
            provider_id = UUID(claims["session_id"])
            expiry = min(datetime.fromtimestamp(claims["exp"], UTC), now() + timedelta(hours=1))
            if expiry <= now():
                raise ValueError("Expired provider token")
    except DomainError:
        raise
    except (httpx.HTTPError, KeyError, ValueError, TypeError, IndexError) as exc:
        raise DomainError(
            503, "AUTH_UNAVAILABLE", "Chưa kết nối được dịch vụ đăng nhập.", True
        ) from exc
    opaque, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    async with request.app.state.database.require()() as db, db.begin():
        await db.execute(
            insert(User)
            .values(id=uuid4(), auth_subject=uid, age_band="unknown")
            .on_conflict_do_nothing(index_elements=[User.auth_subject])
        )
        user = await db.scalar(select(User).where(User.auth_subject == uid).with_for_update())
        if user is None or user.status != "active":
            raise DomainError(403, "ACCOUNT_UNAVAILABLE", "Tài khoản không khả dụng.")
        for purpose in ("AI", "MEM", "MATCH", "VOICE"):
            await db.execute(
                insert(Consent)
                .values(user_id=user.id, purpose=purpose, enabled=False)
                .on_conflict_do_nothing()
            )
        session = AuthSession(
            user_id=user.id,
            token_hash=digest(opaque),
            csrf_hash=digest(csrf),
            provider_session_id=provider_id,
            expires_at=expiry,
            auth_version=user.auth_version,
        )
        db.add(session)
        await db.flush()
        actor = Actor(user.id, session.id, user.auth_version)
    for name, value, http_only in (
        ("moodprint_session", opaque, True),
        ("moodprint_csrf", csrf, False),
    ):
        response.set_cookie(
            name,
            value,
            httponly=http_only,
            secure=settings.cookie_secure or settings.app_env == "production",
            samesite="strict",
            max_age=max(0, int((expiry - now()).total_seconds())),
            path="/",
        )
    return await session_view(request, actor, csrf)


@router.post("/auth/logout", status_code=204)
async def logout(request: Request, actor: Actor = Depends(require_actor)):
    async with transaction(request, actor, eligible=False) as (db, user):
        session = await db.get(AuthSession, actor.session_id)
        session.revoked = True
    request.app.state.ai.invalidate(str(actor.user_id), str(actor.session_id))
    result = Response(status_code=204)
    result.delete_cookie("moodprint_session", path="/")
    result.delete_cookie("moodprint_csrf", path="/")
    return result
