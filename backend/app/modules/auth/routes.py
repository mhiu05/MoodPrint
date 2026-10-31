import secrets
from datetime import timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert

from app.contracts import (
    AuthNotice,
    ConsentView,
    EligibilityInput,
    EmailInput,
    FeatureView,
    GuestQuota,
    LoginInput,
    NoticeView,
    PasswordResetInput,
    SessionView,
    SignupInput,
)
from app.core.errors import DomainError
from app.core.limits import AttemptLimiter
from app.core.security import (
    Actor,
    digest,
    idempotency_key,
    load_actor,
    previous_receipt,
    require_actor,
    require_registered_actor,
    save_receipt,
    transaction,
)
from app.infrastructure.database.models import AgeDeclaration, AuthSession, Consent, User, now
from app.modules.auth.age import AGE_REQUIRED_MESSAGE, adult_eligible, age_band, record_age
from app.modules.auth.provider import SupabaseAuth
from app.modules.consent.policy import consent_enabled
from app.modules.feedback.policy import feedback_open

router = APIRouter()


async def _session_view(request: Request, db, user, user_id, csrf: str | None = None) -> SessionView:
    settings = request.app.state.settings
    consents = (await db.scalars(select(Consent).where(Consent.user_id == user.id))).all()
    declaration = await db.get(AgeDeclaration, user.id)
    eligible = adult_eligible(user, declaration)
    guest = user.account_kind == "guest"
    staff = None
    notices = []
    if not guest:
        # Guests never read staff, moderation or social rows, even if a forged row exists.
        from app.modules.moderation.models import ModerationAction, StaffRole

        staff = await db.get(StaffRole, user.id)
        if user.social_restricted_until and user.social_restricted_until > now():
            notices.append(NoticeView(kind="restricted", until=user.social_restricted_until))
        warned = await db.scalar(
            select(ModerationAction.created_at)
            .where(
                ModerationAction.subject_id == user.id,
                ModerationAction.action == "warn",
                ModerationAction.created_at > now() - timedelta(days=30),
            )
            .limit(1)
        )
        if warned:
            notices.append(NoticeView(kind="warning"))
    ai_available = eligible and request.app.state.ai.available_for(user_id)
    ai_status = request.app.state.ai.status_for(user_id)
    voice = eligible and request.app.state.transcriber is not None and (
        not settings.ai_local_test_user_ids or ai_available
    )
    remaining = None
    guest_quota = None
    server_time = now()
    if guest:
        from app.modules.guests.models import GuestUsage
        from app.modules.guests.policy import guest_paid_available

        # The database clock, not this process, anchors every guest deadline and display.
        server_time = await db.scalar(select(func.clock_timestamp()))
        usage = await db.get(GuestUsage, user.id)
        ai_turns, clips, millis = (
            (usage.ai_turns, usage.voice_clips, usage.voice_milliseconds) if usage else (0, 0, 0)
        )
        guest_quota = GuestQuota(
            ai_turns_remaining=max(0, settings.guest_ai_turns - ai_turns),
            voice_clips_remaining=max(0, settings.guest_voice_clips - clips),
            voice_seconds_remaining=max(0, settings.guest_voice_seconds * 1000 - millis) / 1000,
        )
        voice = voice and guest_paid_available(settings, "voice")
        if not guest_paid_available(settings, "ai"):
            # Paid guest work fails closed until the owner-approved budget and prices exist.
            ai_status = "disabled" if not settings.guest_paid_enabled else "configuration_missing"
            ai_available = False
        remaining = guest_quota.ai_turns_remaining if ai_available else None
    elif ai_available:
        from app.ai.persistence import daily_turns

        used = await daily_turns(db, user.id, now())
        remaining = max(0, settings.ai_daily_turns_per_user - used)
    return SessionView(
        staff=staff.role if staff else None,  # type: ignore[arg-type]
        notices=notices,
        user_id=user.id,
        alias=user.alias,
        age_band=user.age_band,
        eligible=eligible,
        consents={
            c.purpose: ConsentView.model_validate(c).model_copy(
                update={"enabled": consent_enabled(c.purpose, c.enabled)}
            )
            for c in consents
        },
        csrf_token=csrf
        or request.cookies.get("moodprint_csrf")
        or request.headers.get("X-CSRF-Token", ""),
        server_time=server_time,
        timezone=user.timezone,
        data_version=user.data_version,
        birth_year=declaration.birth_year if declaration else None,
        eligibility_version=declaration.version if declaration else 0,
        features=FeatureView(
            ai=ai_available,
            ai_status=ai_status,
            ai_quota_remaining=remaining,
            matching=eligible and not guest,
            voice=voice,
            feedback=eligible and feedback_open(settings),
        ),
        account_kind=user.account_kind,  # type: ignore[arg-type]
        guest_started_at=user.guest_started_at,
        guest_expires_at=user.guest_expires_at,
        guest_quota=guest_quota,
    )


async def session_view(request: Request, actor: Actor, csrf: str | None = None) -> SessionView:
    async with transaction(request, actor, eligible=False) as (db, user):
        return await _session_view(request, db, user, actor.user_id, csrf)


@router.get("/session", response_model=SessionView)
async def get_session(request: Request):
    # One checkout covers authentication and the view. Two checkouts queue on the
    # production pool when every client reads its session together.
    if not request.cookies.get("moodprint_session"):
        raise DomainError(401, "AUTH_REQUIRED", "Vui lòng đăng nhập.")
    async with request.app.state.database.require()() as db:
        actor, user = await load_actor(request, db)
        return await _session_view(request, db, user, actor.user_id)


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


def _check_origin(request: Request) -> None:
    origin = request.headers.get("Origin")
    if origin and origin.rstrip("/") != request.app.state.settings.frontend_origin.rstrip("/"):
        raise DomainError(403, "ORIGIN_DENIED", "Nguồn yêu cầu không hợp lệ.")


def _client_key(request: Request) -> str:
    # With uvicorn --proxy-headers behind a trusted proxy this is the real client address.
    return "ip:" + (request.client.host if request.client else "unknown")


AUTH_LIMITED = ("AUTH_RATE_LIMITED", "Bạn đã thử quá nhiều lần. Vui lòng đợi vài phút.")
LOGIN_LIMIT = AttemptLimiter(10, 900, *AUTH_LIMITED)
IP_LIMIT = AttemptLimiter(40, 900, *AUTH_LIMITED)
EMAIL_LIMIT = AttemptLimiter(3, 3600, *AUTH_LIMITED)


@router.post("/auth/login", response_model=SessionView)
async def login(body: LoginInput, request: Request, response: Response):
    settings = request.app.state.settings
    request.app.state.database.require()
    _check_origin(request)
    email = body.email.strip().lower()
    IP_LIMIT.check(_client_key(request))
    LOGIN_LIMIT.check("email:" + email)
    # Password verification, hashing and account recovery remain Supabase's responsibility.
    provider = await SupabaseAuth(request).password_session(email, body.password)
    if provider.expires_at <= now():
        raise DomainError(503, "AUTH_UNAVAILABLE", "Chưa kết nối được dịch vụ đăng nhập.", True)
    if provider.is_anonymous:
        raise DomainError(403, "REGISTERED_REQUIRED", "Tính năng này cần tài khoản đã đăng ký.")
    uid, provider_id = provider.user_id, provider.session_id
    # Every request re-checks the live Supabase session row, so the app session can outlive
    # the 1-hour access token without storing provider tokens. Activity slides the expiry.
    expiry = now() + timedelta(hours=settings.session_idle_hours)
    opaque, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    async with request.app.state.database.require()() as db, db.begin():
        await db.execute(
            insert(User)
            .values(id=uuid4(), auth_subject=uid, age_band="unknown")
            .on_conflict_do_nothing(index_elements=[User.auth_subject])
        )
        user = await db.scalar(select(User).where(User.auth_subject == uid).with_for_update())
        if user is None or user.status != "active" or user.account_kind != "registered":
            # A guest identity can never be reached through the permanent login path.
            raise DomainError(403, "ACCOUNT_UNAVAILABLE", "Tài khoản không khả dụng.")
        if user.suspended_until and user.suspended_until > now():
            raise DomainError(
                403, "ACCOUNT_SUSPENDED", "Tài khoản đang bị tạm khóa theo quy tắc cộng đồng."
            )
        for purpose in ("AI", "MEM", "MATCH", "VOICE"):
            await db.execute(
                insert(Consent)
                .values(user_id=user.id, purpose=purpose, enabled=consent_enabled(purpose, False))
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
            # Browser-side absolute cap; the server enforces the sliding idle expiry.
            max_age=int(timedelta(days=settings.session_max_days).total_seconds()),
            path="/",
        )
    return await session_view(request, actor, csrf)


@router.post("/auth/signup", response_model=AuthNotice, status_code=202)
async def signup(body: SignupInput, request: Request):
    _check_origin(request)
    from zoneinfo import ZoneInfo

    if age_band(
        body.eligibility.birth_year,
        body.eligibility.confirmed_adult_age,
        current_year=now().astimezone(ZoneInfo("Asia/Bangkok")).year,
    ) != "adult":
        raise DomainError(403, "ADULT_REQUIRED", AGE_REQUIRED_MESSAGE)
    email = body.email.strip().lower()
    IP_LIMIT.check(_client_key(request))
    EMAIL_LIMIT.check("signup:" + email)
    await SupabaseAuth(request).sign_up(email, body.password)
    return AuthNotice(status="sent")


@router.post("/auth/confirmation", response_model=AuthNotice, status_code=202)
async def resend_confirmation(body: EmailInput, request: Request):
    _check_origin(request)
    email = body.email.strip().lower()
    IP_LIMIT.check(_client_key(request))
    EMAIL_LIMIT.check("confirm:" + email)
    await SupabaseAuth(request).resend_confirmation(email)
    return AuthNotice(status="sent")


@router.post("/auth/password-recovery", response_model=AuthNotice, status_code=202)
async def request_password_recovery(body: EmailInput, request: Request):
    _check_origin(request)
    email = body.email.strip().lower()
    IP_LIMIT.check(_client_key(request))
    EMAIL_LIMIT.check("recover:" + email)
    await SupabaseAuth(request).request_recovery(email)
    return AuthNotice(status="sent")


@router.post("/auth/password-reset", response_model=AuthNotice)
async def reset_password(body: PasswordResetInput, request: Request):
    _check_origin(request)
    IP_LIMIT.check(_client_key(request))
    provider = SupabaseAuth(request)
    subject = await provider.update_password(body.access_token, body.password)
    await provider.sign_out(body.access_token)
    async with request.app.state.database.require()() as db, db.begin():
        # A password reset ends every existing MoodPrint session for the account.
        user_id = await db.scalar(
            update(User)
            .where(User.auth_subject == subject)
            .values(auth_version=User.auth_version + 1)
            .returning(User.id)
        )
    if user_id:
        request.app.state.ai.invalidate(str(user_id))
    return AuthNotice(status="updated")


@router.post("/auth/reauthenticate", response_model=AuthNotice)
async def reauthenticate(
    body: LoginInput, request: Request, actor: Actor = Depends(require_registered_actor)
):
    LOGIN_LIMIT.check("reauth:" + str(actor.user_id))
    provider = SupabaseAuth(request)
    checked = await provider.password_session(body.email.strip().lower(), body.password)
    await provider.sign_out(checked.access_token)
    async with transaction(request, actor, eligible=False) as (db, user):
        if checked.user_id != user.auth_subject:
            raise DomainError(403, "REAUTH_MISMATCH", "Thông tin không khớp với tài khoản đang dùng.")
        session = await db.get(AuthSession, actor.session_id)
        session.reauthenticated_at = now()
    return AuthNotice(status="confirmed")


@router.post("/auth/logout", status_code=204)
async def logout(request: Request, actor: Actor = Depends(require_actor)):
    if actor.account_kind == "guest":
        # A guest has no password: logging out ends the whole trial and queues its purge now.
        from app.modules.guests.service import cleared_response, end_guest

        await end_guest(request, actor)
        return cleared_response()
    async with transaction(request, actor, eligible=False) as (db, user):
        session = await db.get(AuthSession, actor.session_id)
        session.revoked = True
    request.app.state.ai.invalidate(str(actor.user_id), str(actor.session_id))
    result = Response(status_code=204)
    result.delete_cookie("moodprint_session", path="/")
    result.delete_cookie("moodprint_csrf", path="/")
    return result
