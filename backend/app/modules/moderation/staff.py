"""Staff authorization for the moderation queue (DR-11).

The role is re-read on every request (revocation is immediate), staff must have
re-authenticated within 12 hours, and the routes do not exist while
MODERATION_ADMIN_ENABLED is off.
"""

from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from fastapi import Depends, Request

from app.core.errors import DomainError
from app.core.security import Actor, require_registered_actor
from app.infrastructure.database.models import AuthSession, now
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


def require_staff(role: str = "moderator"):
    async def dependency(request: Request, actor: Actor = Depends(require_registered_actor)) -> Staff:
        if not request.app.state.settings.moderation_admin_enabled:
            raise DomainError(404, "NOT_FOUND", "Không tìm thấy nội dung.")
        async with request.app.state.database.require()() as db:
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
