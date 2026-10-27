"""Grant exactly one trial per attempt, recover lost responses and never repeat an upstream signup.

Sequence: persist the owned intent -> commit ``signup_started`` (one fenced compare-and-set) ->
one provider signup outside any transaction -> verify -> one short grant transaction that takes
T0 from the database clock at the user INSERT. Provider tokens are used once and never stored.
A rejected signup refunds the creation count; an ambiguous one never repeats and is reconciled
(GE-06.2); a provider success whose grant fails becomes ``orphan_pending``.
"""

import logging
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi import Request, Response
from sqlalchemy import func, literal, literal_column, select, update
from sqlalchemy.dialects.postgresql import insert

from app.contracts import SessionView
from app.core.errors import DomainError
from app.core.security import Actor, digest, idempotency_key, transaction, verify_session
from app.infrastructure.database.models import AuthSession, Consent, User
from app.modules.auth.age import age_band, record_age
from app.modules.auth.provider import AnonymousSignupError, ProviderSession, SupabaseAuth
from app.modules.guests import limits
from app.modules.guests.availability import experience_view
from app.modules.guests.intents import (
    COOKIE,
    claim_guest_attempt,
    hash_token,
    invalid_intent,
    require_public_write,
)
from app.modules.guests.models import (
    GuestCleanupJob,
    GuestProvisioningAttempt,
    GuestUsage,
)
from app.modules.guests.policy import GUEST_LIFETIME_SECONDS, assert_guest_active, database_time
from app.modules.guests.schemas import GuestEligibility, GuestInput

SESSION_COOKIE, CSRF_COOKIE = "moodprint_session", "moodprint_csrf"
EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
log = logging.getLogger("moodprint")


def pending() -> DomainError:
    return DomainError(
        409,
        "GUEST_ATTEMPT_PENDING",
        "Đang xử lý lượt dùng thử của bạn. Vui lòng đợi vài giây rồi thử lại.",
        True,
        retry_after=2,
    )


def entry_closed() -> DomainError:
    return DomainError(503, "GUEST_DISABLED", "Dùng thử tạm thời chưa mở. Vui lòng quay lại sau.")


def payload_digest(body: GuestInput) -> str:
    """Stable digest of what the visitor attested; the one-shot CAPTCHA token is excluded."""
    import json

    canonical = json.dumps(
        {
            "eligibility": body.eligibility.model_dump(mode="json"),
            "disclosureVersion": body.disclosure_version,
        },
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return digest(canonical)


def set_session_cookies(
    request: Request, response: Response, opaque: str, csrf: str, max_age: int
) -> None:
    settings = request.app.state.settings
    for name, value, http_only in ((SESSION_COOKIE, opaque, True), (CSRF_COOKIE, csrf, False)):
        response.set_cookie(
            name,
            value,
            httponly=http_only,
            secure=settings.cookie_secure or settings.app_env == "production",
            samesite="strict",
            max_age=max_age,
            path="/",
        )


async def remaining_seconds(request: Request, expires_at: datetime) -> int:
    async with request.app.state.database.require()() as db:
        return max(0, int((expires_at - await database_time(db)).total_seconds()))


async def current_cookie_identity(request: Request) -> Actor | None:
    """The live app identity behind the presented cookie (no CSRF needed for a public entry)."""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    async with request.app.state.database.require()() as db:
        found = (
            await db.execute(
                select(AuthSession, User)
                .join(User, User.id == AuthSession.user_id)
                .where(AuthSession.token_hash == digest(token))
            )
        ).one_or_none()
        if found is None:
            return None
        session, user = found
        try:
            await verify_session(db, session, user)
        except DomainError:
            return None
        return Actor(user.id, session.id, user.auth_version, user.account_kind)


async def create_guest(request: Request, body: GuestInput, response: Response) -> SessionView:
    from app.modules.auth.routes import session_view

    require_public_write(request)
    key = idempotency_key(request)
    sessions = request.app.state.database.require()

    current = await current_cookie_identity(request)
    if current is not None:
        if current.account_kind == "registered":
            # The trial CTA can never overwrite or downgrade a permanent session.
            raise DomainError(
                409,
                "REGISTERED_SESSION_PRESENT",
                "Bạn đang đăng nhập bằng tài khoản. Hãy đăng xuất trước khi dùng thử.",
            )
        response.status_code = 200
        return await session_view(request, current)

    token = request.cookies.get(COOKIE)
    if not token:
        raise invalid_intent()
    eligibility: GuestEligibility = body.eligibility
    # Age first: nothing upstream is called for an ineligible visitor.
    if not eligibility.confirmed_minimum_age:
        raise _ineligible()
    now = await _database_time(sessions)
    if age_band(eligibility.birth_year, eligibility.confirmed_adult_age, current_year=_year(now)) == "under16":
        raise _ineligible()
    # Constructing the client cannot send anything; a missing configuration fails before any state.
    provider_client = SupabaseAuth(request)
    digest_ = payload_digest(body)
    fence = uuid4()

    # Mapped recovery reads the mapping without a lock, locks the owner, then the attempt.
    async with sessions() as db:
        mapped = await db.scalar(
            select(GuestProvisioningAttempt.user_id).where(
                GuestProvisioningAttempt.intent_hash == hash_token(token)
            )
        )
    async with sessions() as db, db.begin():
        if mapped is not None:
            await db.scalar(select(User.id).where(User.id == mapped).with_for_update())
        attempt = await claim_guest_attempt(db, intent_token=token, key=key, payload_digest=digest_)
        attempt_id, state = attempt.id, attempt.state
        if state == "granted":
            action = "recover"
        elif state == "intent":
            if not experience_view(request).guest_available:
                raise entry_closed()
            await limits.assert_failed_signups_allowed(db, request)
            await limits.reserve_guest_creation(db, request, attempt.id)
            started = await database_time(db)
            await db.execute(
                update(GuestProvisioningAttempt)
                .where(
                    GuestProvisioningAttempt.id == attempt.id,
                    GuestProvisioningAttempt.state == "intent",
                )
                .values(
                    state="signup_started",
                    signup_started_at=started,
                    reconcile_until=started + timedelta(hours=24),
                    lease_token=fence,
                    lease_until=started + timedelta(seconds=60),
                    attempts=GuestProvisioningAttempt.attempts + 1,
                )
            )
            action = "signup"
        else:
            # signup_started / ambiguous: the outcome is unknown. Never send another signup.
            raise pending()

    if action == "recover":
        return await recover_guest_credentials(request, attempt_id, response)

    try:
        provider = await provider_client.anonymous_session(
            body.captcha_token, correlation_id=await _correlation(sessions, attempt_id)
        )
    except AnonymousSignupError as error:
        await _record_signup_failure(request, attempt_id, fence, error)
        if error.outcome == "ambiguous":
            raise pending() from None
        raise

    opaque, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    try:
        if not experience_view(request).guest_available:
            # Entry was switched off after the provider succeeded: clean the orphan instead.
            raise RuntimeError("guest entry closed")
        async with sessions() as db, db.begin():
            actor, expires_at = await grant_guest(
                db, attempt_id, fence, provider, eligibility, opaque=opaque, csrf=csrf
            )
    except Exception as failure:
        await _record_orphan(request, attempt_id, fence, provider)
        log.warning("metric=guest_grant_failed error_type=%s", type(failure).__name__)
        raise DomainError(
            503, "AUTH_UNAVAILABLE", "Chưa kết nối được dịch vụ đăng nhập.", True
        ) from None
    finally:
        del provider  # the access token was used once and is never stored or logged

    set_session_cookies(request, response, opaque, csrf, await remaining_seconds(request, expires_at))
    response.status_code = 201
    return await session_view(request, actor, csrf)


async def grant_guest(
    db,
    attempt_id: UUID,
    fence: UUID,
    provider: ProviderSession,
    eligibility: GuestEligibility,
    *,
    opaque: str,
    csrf: str,
) -> tuple[Actor, datetime]:
    """One short transaction: the user, age, disabled consents, session, usage and cleanup job.

    T0 is the database ``clock_timestamp()`` evaluated by the user INSERT itself; T = T0 + 7200s.
    """
    attempt = await db.scalar(
        select(GuestProvisioningAttempt)
        .where(GuestProvisioningAttempt.id == attempt_id)
        .with_for_update()
    )
    if attempt is None or attempt.state != "signup_started" or attempt.lease_token != fence:
        # A reconciler took over this attempt; it also owns cleaning the provider identity.
        raise DomainError(409, "GUEST_ATTEMPT_PENDING", "Lần bắt đầu này đã thay đổi.", True)
    if await db.scalar(select(User.id).where(User.auth_subject == provider.user_id)):
        raise RuntimeError("provider identity already mapped")

    user_id = uuid4()
    started = select(func.clock_timestamp().label("t0")).cte("grant_time")
    created = (
        await db.execute(
            insert(User)
            .from_select(
                [
                    "id",
                    "auth_subject",
                    "alias",
                    "age_band",
                    "status",
                    "timezone",
                    "auth_version",
                    "data_version",
                    "profile_version",
                    "deletion_pending",
                    "account_kind",
                    "guest_started_at",
                    "guest_expires_at",
                ],
                select(
                    literal(user_id),
                    literal(provider.user_id),
                    literal("Khách"),
                    literal("unknown"),
                    literal("active"),
                    literal("Asia/Bangkok"),
                    literal(1),
                    literal(1),
                    literal(0),
                    literal(False),
                    literal("guest"),
                    started.c.t0,
                    started.c.t0 + literal_column(f"interval '{GUEST_LIFETIME_SECONDS} seconds'"),
                ).select_from(started),
            )
            .returning(User.id, User.guest_expires_at)
        )
    ).one()
    expires_at: datetime = created.guest_expires_at
    user = await db.get(User, user_id)
    await record_age(db, user, eligibility)
    for purpose in ("AI", "MEM", "MATCH", "VOICE"):
        db.add(Consent(user_id=user_id, purpose=purpose, enabled=False, version=1))
    session = AuthSession(
        user_id=user_id,
        token_hash=digest(opaque),
        csrf_hash=digest(csrf),
        provider_session_id=provider.session_id,
        expires_at=expires_at,
        auth_version=user.auth_version,
        reauthenticated_at=EPOCH,
    )
    db.add(session)
    db.add(GuestUsage(user_id=user_id))
    db.add(GuestCleanupJob(user_id=user_id, due_at=expires_at))
    attempt.user_id = user_id
    attempt.provider_subject = provider.user_id
    attempt.provider_session_id = provider.session_id
    attempt.state, attempt.lease_token, attempt.lease_until = "granted", None, None
    await db.flush()
    return Actor(user_id, session.id, user.auth_version, "guest"), expires_at


async def recover_guest_credentials(
    request: Request, attempt_id: UUID, response: Response
) -> SessionView:
    """Rotate opaque credentials for a committed grant: same user, same T, no new signup."""
    from app.modules.auth.routes import session_view

    sessions = request.app.state.database.require()
    opaque, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    async with sessions() as db, db.begin():
        mapped = await db.scalar(
            select(GuestProvisioningAttempt.user_id).where(GuestProvisioningAttempt.id == attempt_id)
        )
        user = (
            await db.scalar(select(User).where(User.id == mapped).with_for_update())
            if mapped
            else None
        )
        attempt = await db.scalar(
            select(GuestProvisioningAttempt)
            .where(GuestProvisioningAttempt.id == attempt_id)
            .with_for_update()
        )
        if (
            user is None
            or attempt is None
            or attempt.user_id != user.id
            or user.account_kind != "guest"
            or user.status != "active"
            or attempt.provider_session_id is None
        ):
            raise DomainError(
                409,
                "GUEST_INTENT_TERMINAL",
                "Lần bắt đầu này đã kết thúc. Hãy bắt đầu lượt dùng thử mới.",
            )
        await assert_guest_active(db, user)
        # Latest valid credential only: every earlier app credential of this trial is revoked.
        await db.execute(
            update(AuthSession)
            .where(AuthSession.user_id == user.id, AuthSession.revoked.is_(False))
            .values(revoked=True)
        )
        session = AuthSession(
            user_id=user.id,
            token_hash=digest(opaque),
            csrf_hash=digest(csrf),
            provider_session_id=attempt.provider_session_id,
            expires_at=user.guest_expires_at,
            auth_version=user.auth_version,
            reauthenticated_at=EPOCH,
        )
        db.add(session)
        await db.flush()
        actor = Actor(user.id, session.id, user.auth_version, "guest")
        expires_at = user.guest_expires_at
    set_session_cookies(request, response, opaque, csrf, await remaining_seconds(request, expires_at))
    response.status_code = 200
    try:
        return await session_view(request, actor, csrf)
    except DomainError as error:
        if error.status == 401:
            # A concurrent recovery already superseded this credential: ask the caller to retry.
            raise pending() from None
        raise


async def _record_signup_failure(
    request: Request, attempt_id: UUID, fence: UUID, error: AnonymousSignupError
) -> None:
    """Persist the classified outcome. Only an explicit rejection refunds the creation count."""
    sessions = request.app.state.database.require()
    async with sessions() as db, db.begin():
        now = await database_time(db)
        rejected = error.outcome == "rejected"
        await db.execute(
            update(GuestProvisioningAttempt)
            .where(
                GuestProvisioningAttempt.id == attempt_id,
                GuestProvisioningAttempt.state == "signup_started",
                GuestProvisioningAttempt.lease_token == fence,
            )
            .values(
                state="rejected" if rejected else "ambiguous",
                last_error=error.code[:40],
                lease_token=None,
                lease_until=None,
                next_attempt_at=now + timedelta(seconds=30),
            )
        )
        if rejected:
            await limits.record_failed_signup(db, request)
            await limits.release_guest_creation(db, request)


async def _record_orphan(
    request: Request, attempt_id: UUID, fence: UUID, provider: ProviderSession
) -> None:
    """A provider success whose grant failed: keep the target identifiers for guarded cleanup."""
    try:
        async with request.app.state.database.require()() as db, db.begin():
            await db.execute(
                update(GuestProvisioningAttempt)
                .where(
                    GuestProvisioningAttempt.id == attempt_id,
                    GuestProvisioningAttempt.state == "signup_started",
                )
                .values(
                    state="orphan_pending",
                    provider_subject=provider.user_id,
                    provider_session_id=provider.session_id,
                    last_error="grant_failed",
                    lease_token=None,
                    lease_until=None,
                    next_attempt_at=func.clock_timestamp(),
                )
            )
    except Exception as failure:  # the marker lookup (GE-06.2) still finds the orphan
        log.warning("metric=guest_orphan_unrecorded error_type=%s", type(failure).__name__)


async def _correlation(sessions, attempt_id: UUID) -> str:
    async with sessions() as db:
        return await db.scalar(
            select(GuestProvisioningAttempt.provider_correlation).where(
                GuestProvisioningAttempt.id == attempt_id
            )
        )


async def _database_time(sessions) -> datetime:
    async with sessions() as db:
        return await database_time(db)


def _year(moment: datetime) -> int:
    from zoneinfo import ZoneInfo

    return moment.astimezone(ZoneInfo("Asia/Bangkok")).year


def _ineligible() -> DomainError:
    return DomainError(
        422,
        "GUEST_INELIGIBLE",
        "Dùng thử dành cho người từ 16 tuổi. Hãy xác nhận độ tuổi của bạn để tiếp tục.",
    )


def cleared_response() -> Response:
    """204 that drops every cookie of the trial (session, CSRF and the creation intent)."""
    result = Response(status_code=204)
    for name, path in ((SESSION_COOKIE, "/"), (CSRF_COOKIE, "/"), (COOKIE, "/api/v1/auth")):
        result.delete_cookie(name, path=path)
    return result


async def end_guest(request: Request, actor: Actor) -> None:
    """Permanently end the trial now: revoke every credential and queue the purge immediately.

    The deadline T is untouched; ending only moves cleanup earlier. No password or step-up: it
    affects just the authenticated disposable identity.
    """
    async with transaction(request, actor, eligible=False) as (db, user):
        if user.account_kind != "guest":
            raise DomainError(403, "GUEST_REQUIRED", "Chỉ lượt dùng thử mới có thể kết thúc bằng thao tác này.")
        now = await database_time(db)
        user.status = "deleting"
        user.auth_version += 1
        await db.execute(
            update(AuthSession).where(AuthSession.user_id == user.id).values(revoked=True)
        )
        await db.execute(
            update(GuestCleanupJob)
            .where(GuestCleanupJob.user_id == user.id)
            .values(due_at=func.least(GuestCleanupJob.due_at, now), next_attempt_at=now)
        )
    # After commit: drop every in-memory copy (context, runs, proposals, pending exports).
    request.app.state.ai.expire_guest(actor.user_id)
    request.app.state.exports = {
        key: value
        for key, value in request.app.state.exports.items()
        if value["owner"] != actor.user_id
    }
