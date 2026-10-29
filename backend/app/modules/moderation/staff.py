"""Staff authorization for the moderation queue (DR-11).

The role is re-read on every request (revocation is immediate), staff must have
re-authenticated within 12 hours, and the routes do not exist while
MODERATION_ADMIN_ENABLED is off.
"""

from dataclasses import dataclass
from datetime import timedelta
from typing import Literal
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DomainError
from app.core.security import Actor, lock_actor, require_registered_actor
from app.infrastructure.database.models import AuthSession, now
from app.modules.guests.policy import database_time, require_registered_user
from app.modules.moderation.models import StaffRole

REAUTH_WINDOW = timedelta(hours=12)
RANK = {"moderator": 1, "admin": 2}


@dataclass(frozen=True)
class Staff:
    actor: Actor
    role: str

    @property
    def user_id(self) -> UUID:
        return self.actor.user_id


async def staff_role(db, user_id: UUID) -> str | None:
    row = await db.get(StaffRole, user_id)
    return row.role if row else None


async def assert_feedback_admin(db: AsyncSession, actor: Actor, *, lock: bool = False) -> Staff:
    """Revalidate owner → current role → resource; callers lock before a review mutation.

    A role revoked while the owner gate is queued must never authorize the later write. Refresh
    the session and role even if this Session was used by a prior read; client role hints are not
    authorization. Role deletion/update serializes on the same StaffRole row.
    """
    await db.get(AuthSession, actor.session_id, populate_existing=True)
    user = await lock_actor(db, actor, lock=lock)
    require_registered_user(user)
    query = select(StaffRole).where(StaffRole.user_id == user.id).execution_options(populate_existing=True)
    granted = await db.scalar(query.with_for_update() if lock else query)
    if granted is None or granted.role != "admin":
        raise DomainError(403, "STAFF_REQUIRED", "Bạn không có quyền xem góp ý.")
    session = await db.get(AuthSession, actor.session_id, populate_existing=True)
    if session is None or session.reauthenticated_at < await database_time(db) - REAUTH_WINDOW:
        raise DomainError(403, "REAUTH_REQUIRED", "Vui lòng xác nhận lại mật khẩu để xem góp ý.")
    return Staff(actor, granted.role)


def require_staff(role: str = "moderator", *, feature: Literal["moderation", "feedback"] = "moderation"):
    async def dependency(request: Request, actor: Actor = Depends(require_registered_actor)) -> Staff:
        enabled = (
            request.app.state.settings.feedback_admin_enabled if feature == "feedback"
            else request.app.state.settings.moderation_admin_enabled
        )
        if not enabled:
            raise DomainError(404, "NOT_FOUND", "Không tìm thấy nội dung.")
        async with request.app.state.database.require()() as db:
            if feature == "feedback":
                return await assert_feedback_admin(db, actor)
            granted = await staff_role(db, actor.user_id)
            session = await db.get(AuthSession, actor.session_id)
        if granted is None or RANK[granted] < RANK[role]:
            raise DomainError(403, "STAFF_REQUIRED", "Bạn không có quyền kiểm duyệt.")
        if session is None or session.reauthenticated_at < now() - REAUTH_WINDOW:
            raise DomainError(
                403, "REAUTH_REQUIRED", "Vui lòng xác nhận lại mật khẩu để tiếp tục kiểm duyệt."
            )
        return Staff(actor, granted)

    return dependency
