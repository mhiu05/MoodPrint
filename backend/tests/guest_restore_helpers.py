"""Only disposable restore rehearsals import this quarantine gate, never the production router."""

from sqlalchemy import func, select, text

from app.infrastructure.database.models import User
from app.jobs.retention import purge_expired
from app.modules.guests.jobs import (
    ensure_cleanup_jobs,
    process_guest_cleanup,
    reconcile_guest_provisioning,
)


async def enforce_quarantine(app):
    await ensure_cleanup_jobs(app)
    await reconcile_guest_provisioning(app)  # lookup/delete only; no signup/replay
    for _ in range(100):
        if not await process_guest_cleanup(app):
            break
    await purge_expired(app)
    async with app.state.database.sessions() as db:
        expired = await db.scalar(select(func.count()).select_from(User).where(
            User.account_kind == "guest", User.guest_expires_at <= func.clock_timestamp()))
        anonymous = await db.scalar(text("select count(*) from auth.users where is_anonymous"))
    calls = len(getattr(app.state.ai.model_override, "calls", []))
    if expired or anonymous or calls:
        raise RuntimeError("Restore stays quarantined: expired/anonymous rows or replay remain")
    return {"expiredRemaining": expired, "anonymousRemaining": anonymous, "providerCallsReplayed": calls}
