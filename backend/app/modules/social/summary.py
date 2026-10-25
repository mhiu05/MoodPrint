"""Inbox signals from private read markers (DR-13): unread counts, previews, nav badges.

Read markers are never exposed to the peer; there are no read receipts.
"""

from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy import and_, func, or_, select

from app.core.errors import DomainError
from app.core.security import Actor, require_actor, transaction
from app.infrastructure.database.models import Consent, User, now
from app.modules.social import service as svc
from app.modules.social.models import Connection, ConnectionRead, ConnectionRequest, HumanMessage
from app.modules.social.schemas import SocialSummaryView

router = APIRouter()

PREVIEW_CHARS = 80


async def visible_rooms(db, user: User) -> list[Connection]:
    """Open rooms this user may still use (same policy as live_room), newest first."""
    rows = (
        await db.scalars(
            select(Connection)
            .where(
                or_(Connection.low_user_id == user.id, Connection.high_user_id == user.id),
                Connection.status == "open",
            )
            .order_by(Connection.created_at.desc())
            .limit(100)
        )
    ).all()
    result = []
    for room in rows:
        peer_id = room.high_user_id if room.low_user_id == user.id else room.low_user_id
        peer = await db.get(User, peer_id)
        try:
            gate = await svc.room_gate(db, user, peer)
        except DomainError:
            continue
        if svc.consent_view(room.snapshots) == svc.consent_view(gate):
            result.append(room)
    return result


async def unread_by_room(db, user_id: UUID, room_ids: list[UUID]) -> dict[UUID, int]:
    """Peer messages after this user's marker, within message retention; one grouped query."""
    if not room_ids:
        return {}
    rows = await db.execute(
        select(HumanMessage.connection_id, func.count())
        .outerjoin(
            ConnectionRead,
            and_(
                ConnectionRead.connection_id == HumanMessage.connection_id,
                ConnectionRead.user_id == user_id,
            ),
        )
        .where(
            HumanMessage.connection_id.in_(room_ids),
            HumanMessage.sender_id != user_id,
            HumanMessage.seq > func.coalesce(ConnectionRead.last_read_seq, 0),
            HumanMessage.created_at > now() - timedelta(days=90),
        )
        .group_by(HumanMessage.connection_id)
    )
    return {room_id: count for room_id, count in rows.all()}


async def last_messages(db, room_ids: list[UUID]) -> dict[UUID, HumanMessage]:
    if not room_ids:
        return {}
    rows = await db.scalars(
        select(HumanMessage)
        .where(
            HumanMessage.connection_id.in_(room_ids),
            HumanMessage.created_at > now() - timedelta(days=90),
        )
        .distinct(HumanMessage.connection_id)
        .order_by(HumanMessage.connection_id, HumanMessage.seq.desc())
    )
    return {row.connection_id: row for row in rows.all()}


@router.get("/social/summary", response_model=SocialSummaryView)
async def social_summary(request: Request, actor: Actor = Depends(require_actor)):
    # Polled for navigation badges: no row locks, and zeros (not 403) without MATCH.
    async with transaction(request, actor, lock=False) as (db, user):
        consent = await db.get(Consent, (user.id, "MATCH"))
        if user.age_band != "adult" or not consent or not consent.enabled:
            return SocialSummaryView()
        pending = await db.scalar(
            select(func.count())
            .select_from(ConnectionRequest)
            .where(
                ConnectionRequest.recipient_id == user.id,
                ConnectionRequest.status == "pending",
                ConnectionRequest.expires_at > now(),
            )
        )
        rooms = await visible_rooms(db, user)
        ids = [room.id for room in rooms]
        unread = await unread_by_room(db, user.id, ids)
        from app.modules.activities import hooks

        return SocialSummaryView(
            pending_incoming_requests=pending or 0,
            unread_connections=sum(1 for count in unread.values() if count),
            activity_invites=await hooks.pending_invites(db, user.id, ids),
        )
