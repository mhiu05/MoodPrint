"""Owner-only export sections for consent history and the social/matching footprint.

Only data the user authored or that describes their own choices is included.
Peers appear as pseudonymous room aliases; peer message text, peer identity and
report evidence (which quotes the peer) are never exported to the other party.
"""

from datetime import timedelta

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DomainError
from app.infrastructure.database.models import Consent, ConsentEvent, User, now
from app.modules.moderation.models import IdentityField, Report, RevealAccess
from app.modules.social.models import (
    Block,
    Connection,
    ConnectionRequest,
    HumanMessage,
    MatchingDraft,
    PublishedProfile,
)
from app.modules.social.service import pair_alias

ROW_LIMIT = 1000


async def _rows(db: AsyncSession, statement):
    rows = (await db.scalars(statement.limit(ROW_LIMIT + 1))).all()
    if len(rows) > ROW_LIMIT:
        raise DomainError(
            503, "EXPORT_TOO_LARGE", "Phạm vi xuất quá lớn. Hãy yêu cầu hỗ trợ xuất dữ liệu."
        )
    return rows


async def consent_section(db: AsyncSession, user: User) -> dict:
    current = await _rows(db, select(Consent).where(Consent.user_id == user.id))
    events = await _rows(
        db,
        select(ConsentEvent)
        .where(ConsentEvent.user_id == user.id)
        .order_by(ConsentEvent.created_at),
    )
    return {
        "current": [
            {
                "purpose": row.purpose,
                "enabled": row.enabled,
                "version": row.version,
                "policyVersion": row.policy_version,
            }
            for row in current
        ],
        "history": [
            {
                "purpose": row.purpose,
                "enabled": row.enabled,
                "version": row.version,
                "policyVersion": row.policy_version,
                "changedAt": row.created_at.isoformat(),
            }
            for row in events
        ],
    }


async def social_section(db: AsyncSession, user: User) -> dict:
    draft = await db.get(MatchingDraft, user.id)
    profiles = await _rows(
        db,
        select(PublishedProfile)
        .where(PublishedProfile.user_id == user.id)
        .order_by(PublishedProfile.version),
    )
    identity = await _rows(db, select(IdentityField).where(IdentityField.user_id == user.id))
    requests = await _rows(
        db,
        select(ConnectionRequest)
        .where(
            or_(ConnectionRequest.sender_id == user.id, ConnectionRequest.recipient_id == user.id)
        )
        .order_by(ConnectionRequest.created_at),
    )
    rooms = await _rows(
        db,
        select(Connection)
        .where(or_(Connection.low_user_id == user.id, Connection.high_user_id == user.id))
        .order_by(Connection.created_at),
    )
    messages = await _rows(
        db,
        select(HumanMessage)
        .where(
            HumanMessage.sender_id == user.id,
            HumanMessage.created_at > now() - timedelta(days=90),
        )
        .order_by(HumanMessage.connection_id, HumanMessage.seq),
    )
    reports = await _rows(
        db, select(Report).where(Report.reporter_id == user.id).order_by(Report.created_at)
    )
    blocks = await _rows(db, select(Block).where(Block.blocker_id == user.id))
    shared = await _rows(db, select(RevealAccess).where(RevealAccess.owner_id == user.id))
    alias = {room.id: pair_alias(room.low_user_id, room.high_user_id)[0] for room in rooms}
    return {
        "matchingDraft": {"profile": draft.payload, "version": draft.version} if draft else None,
        "publishedProfiles": [
            {
                "profile": row.payload,
                "version": row.version,
                "current": row.valid and row.version == user.profile_version,
                "publishedAt": row.created_at.isoformat(),
            }
            for row in profiles
        ],
        "identity": [
            {"field": row.field, "value": row.value, "version": row.version} for row in identity
        ],
        "connectionRequests": [
            {
                "direction": "outgoing" if row.sender_id == user.id else "incoming",
                "status": row.status,
                "createdAt": row.created_at.isoformat(),
                "expiresAt": row.expires_at.isoformat(),
            }
            for row in requests
        ],
        "connections": [
            {
                "id": str(row.id),
                "peer": alias[row.id],
                "status": row.status,
                "createdAt": row.created_at.isoformat(),
            }
            for row in rooms
        ],
        "sentMessages": [
            {
                "connection": alias.get(row.connection_id),
                "text": row.text,
                "sentAt": row.created_at.isoformat(),
            }
            for row in messages
        ],
        "identitySharing": [
            {"field": row.field, "status": row.status, "connection": alias.get(row.connection_id)}
            for row in shared
        ],
        "reportsFiled": [
            {
                "reason": row.reason,
                "status": row.status,
                "evidenceMessages": len(row.evidence or []),
                "createdAt": row.created_at.isoformat(),
            }
            for row in reports
        ],
        "blocksMade": [{"createdAt": row.created_at.isoformat()} for row in blocks],
        "activities": await activity_section(db, user),
    }


async def activity_section(db: AsyncSession, user: User) -> dict:
    """Own sessions, own answers and own feedback; peer answers are never exported."""
    from app.modules.activities.models import (
        ActivityParticipant,
        ActivityResponse,
        ActivitySession,
    )

    participants = await _rows(
        db, select(ActivityParticipant).where(ActivityParticipant.user_id == user.id)
    )
    sessions = {
        row.id: row
        for row in (
            await db.scalars(
                select(ActivitySession).where(
                    ActivitySession.id.in_([p.session_id for p in participants])
                )
            )
        ).all()
    }
    mine = sorted(
        ((sessions[p.session_id], p) for p in participants), key=lambda pair: pair[0].created_at
    )
    answers = await _rows(
        db,
        select(ActivityResponse)
        .where(ActivityResponse.user_id == user.id)
        .order_by(ActivityResponse.submitted_at),
    )
    return {
        "sessions": [
            {
                "id": str(session.id),
                "kind": session.kind,
                "role": participant.role,
                "state": session.state,
                "createdAt": session.created_at.isoformat(),
                "endedAt": session.ended_at.isoformat() if session.ended_at else None,
                "feedback": participant.feedback,
            }
            for session, participant in mine
        ],
        "responses": [
            {
                "session": str(row.session_id),
                "round": row.round,
                "choice": row.choice,
                "text": row.text,
                "skipped": row.skipped,
                "submittedAt": row.submitted_at.isoformat(),
            }
            for row in answers
        ],
    }
