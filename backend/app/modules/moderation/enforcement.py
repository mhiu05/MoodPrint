"""Applying moderation outcomes to an account (I-03).

Callers hold the subject's user row lock (taken before any pair lock), so
invalidate_user_social keeps its documented lock order.
"""

from datetime import datetime

from sqlalchemy import update

from app.infrastructure.database.models import AuthSession, User, now


async def restrict(db, subject: User, until: datetime) -> None:
    """Leave discovery, requests, messaging and activities; close rooms and stop activities."""
    from app.modules.activities import hooks
    from app.modules.social.service import invalidate_user_social

    subject.social_restricted_until = until
    await hooks.abort_for_user(db, subject.id, "account_restricted")
    await invalidate_user_social(db, subject.id)


async def suspend(db, subject: User, until: datetime) -> None:
    """End every session now and refuse sign-in until `until`; social state as restrict."""
    subject.suspended_until = until
    subject.auth_version += 1
    await db.execute(
        update(AuthSession).where(AuthSession.user_id == subject.id).values(revoked=True)
    )
    await restrict(db, subject, until)


def lift(subject: User) -> None:
    subject.social_restricted_until = None
    subject.suspended_until = None


def is_suspended(user: User) -> bool:
    return bool(user.suspended_until and user.suspended_until > now())


def is_restricted(user: User) -> bool:
    return bool(user.social_restricted_until and user.social_restricted_until > now())
