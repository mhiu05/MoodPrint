"""Social policies share the same sorted user → pair → resource lock order."""

import secrets
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import NoReturn
from uuid import UUID, uuid4

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts import ActionReceipt
from app.core.errors import DomainError
from app.core.security import Actor, digest, lock_actor
from app.infrastructure.database.models import Consent, User, now
from app.modules.matching import scoring
from app.modules.social.models import (
    Block,
    CandidateReference,
    Connection,
    ConnectionRequest,
    HumanMessage,
    Pair,
    PublishedProfile,
)
from app.modules.social.schemas import ConnectionView, MessageView, PublicProfile, RequestView


def deny(code="CONNECTION_UNAVAILABLE") -> NoReturn:
    raise DomainError(403, code, "Kết nối không còn khả dụng. Vui lòng tải lại.")


def missing() -> NoReturn:
    raise DomainError(404, "NOT_FOUND", "Không tìm thấy nội dung.")


def receipt(resource_id: UUID, version=1):
    return ActionReceipt(action_id=uuid4(), resource_id=str(resource_id), resource_version=version)


def validate_publishable(profile: dict):
    if not scoring._valid_profile({**profile, "sources": []}):
        raise DomainError(
            422, "PROFILE_INCOMPLETE", "Hãy chọn ít nhất 3 sở thích, 2 giá trị và 1 ngôn ngữ."
        )


def public_payload(body):
    return PublicProfile.model_validate(body.model_dump(exclude={"expected_version"})).model_dump()


async def match_consent(db: AsyncSession, user: User) -> Consent:
    consent = await db.get(Consent, (user.id, "MATCH"))
    if (
        user.status != "active"
        or user.deletion_pending
        or user.age_band != "adult"
        or not consent
        or not consent.enabled
    ):
        deny("MATCH_UNAVAILABLE")
    return consent


async def current_profile(db: AsyncSession, user: User):
    consent = await match_consent(db, user)
    profile = await db.scalar(
        select(PublishedProfile).where(PublishedProfile.user_id == user.id, PublishedProfile.valid)
    )
    if (
        not profile
        or profile.version != user.profile_version
        or profile.consent_version != consent.version
    ):
        deny("PROFILE_REQUIRED")
    return profile, consent


async def is_blocked(db: AsyncSession, a: UUID, b: UUID):
    return (
        await db.scalar(
            select(Block.blocker_id).where(
                or_(
                    and_(Block.blocker_id == a, Block.blocked_id == b),
                    and_(Block.blocker_id == b, Block.blocked_id == a),
                )
            )
        )
        is not None
    )


async def base_eligibility(db: AsyncSession, a: User, b: User, *, own_snapshot=None):
    if a.id == b.id or await is_blocked(db, a.id, b.id):
        deny()
    ap, ac = own_snapshot if own_snapshot is not None else await current_profile(db, a)
    bp, bc = await current_profile(db, b)
    if ap.payload["goal"] != bp.payload["goal"] or not set(ap.payload["languages"]) & set(
        bp.payload["languages"]
    ):
        deny("PAIR_INELIGIBLE")
    snapshots = {
        str(a.id): {"profile": ap.version, "consent": ac.version},
        str(b.id): {"profile": bp.version, "consent": bc.version},
    }
    return ap, bp, snapshots


async def room_gate(db: AsyncSession, a: User, b: User) -> dict[str, dict[str, int]]:
    """Room/request validity (DR-03): no block and both MATCH-consented adults.

    Published profiles decide discovery only, so editing or withdrawing one never
    closes a friendship; consent versions remain the room's identity.
    """
    if a.id == b.id or await is_blocked(db, a.id, b.id):
        deny()
    ac, bc = await match_consent(db, a), await match_consent(db, b)
    return {str(a.id): {"consent": ac.version}, str(b.id): {"consent": bc.version}}


def consent_view(snapshots: dict) -> dict[str, int]:
    return {uid: value["consent"] for uid, value in snapshots.items()}


async def canonical_pair(db: AsyncSession, a: UUID, b: UUID, create=True, lock=True):
    low, high = sorted((a, b))
    statement = select(Pair).where(Pair.low_user_id == low, Pair.high_user_id == high)
    pair = await db.scalar(statement.with_for_update() if lock else statement)
    if not pair and create:
        pair = Pair(low_user_id=low, high_user_id=high)
        db.add(pair)
        await db.flush()
    return pair


@asynccontextmanager
async def pair_transaction(request, actor: Actor, peer_id: UUID, lock: bool = True):
    # Never lock the actor first: reciprocal operations must take identical order.
    # lock=False is only for read-only polling, which must not contend with writers.
    async with request.app.state.database.require()() as db, db.begin():
        statement = select(User).where(User.id.in_([actor.user_id, peer_id])).order_by(User.id)
        users = (await db.scalars(statement.with_for_update() if lock else statement)).all()
        mapping = {user.id: user for user in users}
        if len(mapping) != 2:
            missing()
        user = await lock_actor(db, actor, lock=lock)
        yield db, user, mapping[peer_id]


async def resolve_reference(request, actor, ref_id: UUID):
    async with request.app.state.database.require()() as db:
        ref = await db.get(CandidateReference, ref_id)
        if not ref or ref.user_id != actor.user_id:
            missing()
        if ref.expires_at <= now():
            raise DomainError(410, "CANDIDATE_EXPIRED", "Gợi ý đã hết hạn. Vui lòng tải lại.")
        return ref


def check_reference(ref, a, b, snapshots):
    if ref.expires_at <= now():
        raise DomainError(410, "CANDIDATE_EXPIRED", "Gợi ý đã hết hạn.")
    if snapshots[str(a.id)] != {
        "profile": ref.profile_version,
        "consent": ref.consent_version,
    } or snapshots[str(b.id)] != {
        "profile": ref.peer_profile_version,
        "consent": ref.peer_consent_version,
    }:
        raise DomainError(409, "CANDIDATE_CHANGED", "Gợi ý đã thay đổi. Vui lòng tải lại.")


async def interaction(db, pair: Pair, snapshots):
    pending = await db.scalar(
        select(ConnectionRequest)
        .where(ConnectionRequest.pair_id == pair.id, ConnectionRequest.status == "pending")
        .with_for_update()
    )
    room = await db.scalar(
        select(Connection)
        .where(Connection.pair_id == pair.id, Connection.status == "open")
        .with_for_update()
    )
    deadlines = []
    gate = consent_view(snapshots)
    if pending and (pending.expires_at <= now() or consent_view(pending.snapshots) != gate):
        expired = pending.expires_at <= now()
        pending.status = "expired" if expired else "invalidated"
        # Expiry has a durable timestamp. Rechecking must never move its cooldown.
        deadlines.append((pending.expires_at if expired else now()) + timedelta(days=30))
        pending.version += 1
        pending = None
    if room and consent_view(room.snapshots) != gate:
        room.status = "closed"
        room.version += 1
        room = None
        deadlines.append(now() + timedelta(days=30))
    if deadlines:
        if pair.cooldown_until:
            deadlines.append(pair.cooldown_until)
        pair.cooldown_until = max(deadlines)
        pair.version += 1
        await db.flush()
    return pending, room


async def invalidate_user_social(db: AsyncSession, user_id: UUID):
    """Materialize invalidation in the transaction changing the account gate.

    The caller holds this user's gate. Never acquire another user's gate here;
    pair operations already need this gate before they can hold these pairs.
    Sorting pairs also orders simultaneous invalidations from different users.
    """
    pending_pairs = select(ConnectionRequest.pair_id).where(
        or_(ConnectionRequest.sender_id == user_id, ConnectionRequest.recipient_id == user_id),
        ConnectionRequest.status == "pending",
    )
    open_pairs = select(Connection.pair_id).where(
        or_(Connection.low_user_id == user_id, Connection.high_user_id == user_id),
        Connection.status == "open",
    )
    pairs = (
        await db.scalars(
            select(Pair)
            .where(Pair.id.in_(pending_pairs.union(open_pairs)))
            .order_by(Pair.id)
            .with_for_update()
        )
    ).all()
    for pair in pairs:
        await interaction(db, pair, {})


def request_view(row, actor_id):
    return RequestView(
        id=row.id,
        status=row.status,
        version=row.version,
        direction="outgoing" if row.sender_id == actor_id else "incoming",
        expires_at=row.expires_at,
        connection_id=row.connection_id,
    )


def pair_alias(a: UUID, b: UUID) -> tuple[str, str]:
    """One pseudonym per pair (DR-06): the same name on cards, requests, rooms and export."""
    seed = digest(":".join(sorted((str(a), str(b)))))[:8]
    return f"Bạn đồng hành {seed[:6]}", seed


def connection_view(room):
    return ConnectionView(
        id=room.id,
        alias=pair_alias(room.low_user_id, room.high_user_id)[0],
        status=room.status,
        version=room.version,
        high_water_seq=str(room.next_seq),
    )


async def room_peer(request, actor, room_id):
    async with request.app.state.database.require()() as db:
        room = await db.get(Connection, room_id)
        if not room or actor.user_id not in (room.low_user_id, room.high_user_id):
            missing()
        return room.high_user_id if room.low_user_id == actor.user_id else room.low_user_id


async def live_room(db, a, b, room_id, lock: bool = True):
    gate = consent_view(await room_gate(db, a, b))
    pair = await canonical_pair(db, a.id, b.id, False, lock=lock)
    statement = select(Connection).where(Connection.id == room_id)
    room = await db.scalar(statement.with_for_update() if lock else statement)
    if (
        not pair
        or not room
        or room.pair_id != pair.id
        or room.status != "open"
        or consent_view(room.snapshots) != gate
    ):
        deny()
    return room


async def open_mutual_room(db, pair, pending, snapshots):
    room = Connection(
        pair_id=pair.id,
        low_user_id=pair.low_user_id,
        high_user_id=pair.high_user_id,
        snapshots=snapshots,
    )
    db.add(room)
    await db.flush()
    pending.status = "accepted"
    pending.version += 1
    pending.connection_id = room.id
    return room


def message_view(row, actor_id):
    return MessageView(
        id=row.id,
        connection_id=row.connection_id,
        client_message_id=row.client_message_id,
        sender="self" if row.sender_id == actor_id else "peer",
        text=row.text,
        seq=str(row.seq),
        accepted_at=row.created_at,
    )


async def message_quota(db, user_id):
    count = await db.scalar(
        select(func.count())
        .select_from(HumanMessage)
        .where(
            HumanMessage.sender_id == user_id,
            HumanMessage.created_at > now() - timedelta(minutes=1),
        )
    )
    if count >= 20:
        raise DomainError(429, "MESSAGE_QUOTA", "Bạn đã gửi nhiều tin nhắn. Hãy thử lại sau.", True)


async def invitation_quota(db, user_id):
    count = await db.scalar(
        select(func.count())
        .select_from(ConnectionRequest)
        .where(
            ConnectionRequest.sender_id == user_id,
            ConnectionRequest.created_at > now() - timedelta(hours=24),
        )
    )
    pending = await db.scalar(
        select(func.count())
        .select_from(ConnectionRequest)
        .where(
            ConnectionRequest.sender_id == user_id,
            ConnectionRequest.status == "pending",
            ConnectionRequest.expires_at > now(),
        )
    )
    if count >= 10 or pending >= 10:
        raise DomainError(
            429, "INVITATION_QUOTA", "Bạn đã đạt giới hạn lời mời. Hãy thử lại sau.", True
        )


def reasons(a, b):
    labels = [
        f"Cùng thích {label.lower()}"
        for tag, label in scoring._INTERESTS.items()
        if tag in a["interests"] and tag in b["interests"]
    ]
    labels += [
        f"Cùng coi trọng {label.lower()}"
        for tag, label in scoring._VALUES.items()
        if tag in a["values"] and tag in b["values"]
    ]
    if a["style"] == b["style"]:
        labels.append("Cùng cách trò chuyện")
    return labels[:3]


def new_preview():
    return secrets.token_hex(32)
