"""Batched public-profile retrieval; private content is never a ranking input."""

from datetime import timedelta

from sqlalchemy import or_, select

from app.infrastructure.database.models import Consent, User, now
from app.modules.matching import scoring
from app.modules.social.models import Block, Connection, ConnectionRequest, Pair, PublishedProfile

# Bounded discovery: the eligible scan and the recheck shortlist both have hard caps.
SCAN_LIMIT = 1000
SHORTLIST = 10


async def ranked_candidates(db, user, own, own_consent):
    peers = (
        await db.execute(
            select(
                User.id,
                PublishedProfile.version,
                PublishedProfile.payload,
                Consent.version.label("consent_version"),
            )
            .join(
                PublishedProfile,
                (PublishedProfile.user_id == User.id)
                & PublishedProfile.valid
                & (PublishedProfile.version == User.profile_version),
            )
            .join(
                Consent,
                (Consent.user_id == User.id)
                & (Consent.purpose == "MATCH")
                & Consent.enabled
                & (Consent.version == PublishedProfile.consent_version),
            )
            .where(
                User.id != user.id,
                User.status == "active",
                User.age_band == "adult",
                ~User.deletion_pending,
                PublishedProfile.payload["goal"].astext == own.payload["goal"],
            )
            .order_by(User.id)
            .limit(SCAN_LIMIT)
        )
    ).all()
    blocks = (
        await db.scalars(
            select(Block).where(or_(Block.blocker_id == user.id, Block.blocked_id == user.id))
        )
    ).all()
    blocked = {
        item.blocked_id if item.blocker_id == user.id else item.blocker_id for item in blocks
    }
    pairs = (
        await db.scalars(
            select(Pair).where(or_(Pair.low_user_id == user.id, Pair.high_user_id == user.id))
        )
    ).all()
    by_peer = {
        pair.high_user_id if pair.low_user_id == user.id else pair.low_user_id: pair
        for pair in pairs
    }
    pair_ids = [pair.id for pair in pairs]
    pending = (
        (
            await db.scalars(
                select(ConnectionRequest).where(
                    ConnectionRequest.pair_id.in_(pair_ids), ConnectionRequest.status == "pending"
                )
            )
        ).all()
        if pairs
        else []
    )
    rooms = (
        (
            await db.scalars(
                select(Connection).where(
                    Connection.pair_id.in_(pair_ids), Connection.status == "open"
                )
            )
        ).all()
        if pairs
        else []
    )
    pending_by_pair = {row.pair_id: row for row in pending}
    rooms_by_pair = {row.pair_id: row for row in rooms}
    ranked = []
    for peer_id, version, payload, consent_version in peers:
        if (
            peer_id in blocked
            or payload["goal"] != own.payload["goal"]
            or not set(payload["languages"]) & set(own.payload["languages"])
        ):
            continue
        snapshots = {
            str(user.id): {"profile": own.version, "consent": own_consent.version},
            str(peer_id): {"profile": version, "consent": consent_version},
        }
        pair = by_peer.get(peer_id)
        if pair:
            if pair.cooldown_until and pair.cooldown_until > now():
                continue
            pending_row = pending_by_pair.get(pair.id)
            room = rooms_by_pair.get(pair.id)
            if pending_row and pending_row.snapshots == snapshots:
                if pending_row.expires_at + timedelta(days=30) > now():
                    continue
            if room and room.snapshots == snapshots:
                continue
        points = scoring.score({**own.payload, "sources": []}, {**payload, "sources": []})
        if points >= 30:
            ranked.append((points, str(peer_id), peer_id))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    # Extra ranked peers replace any that fail the locked recheck in the route.
    return [item[2] for item in ranked[:SHORTLIST]]
