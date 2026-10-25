"""Eligible-peer retrieval in one SQL query, then deterministic scoring and fair ranking.

Only current, consented published profiles and social counters are inputs; private
content is never read here (DR-04, T-MATCH-06). The route's locked recheck remains
the authority before any candidate reference is minted.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import String, and_, exists, func, or_, select
from sqlalchemy.dialects.postgresql import array
from sqlalchemy.orm import aliased

from app.infrastructure.database.models import Consent, User, now
from app.modules.matching import ranking, scoring_compat, scoring_v2
from app.modules.social.models import Block, Connection, ConnectionRequest, Pair, PublishedProfile

log = logging.getLogger(__name__)

# Bounded discovery: the eligible scan and the recheck shortlist both have hard caps.
SCAN_LIMIT = 1000
SHORTLIST = 10
INACTIVE_AFTER = timedelta(days=30)
STALE_PROFILE_AFTER = timedelta(days=180)
# Accounts not seen since last_seen_at was introduced (NULL) count as active until
# this instant (about 30 days after release R1); adjust at deploy time if needed.
LAST_SEEN_ENFORCED_FROM = datetime(2026, 12, 31, tzinfo=UTC)


@dataclass(frozen=True)
class PeerRow:
    id: UUID
    version: int
    payload: dict[str, Any]
    consent_version: int
    pending_incoming: int
    first_published_at: datetime | None


async def eligible_peers(
    db, user: User, own: PublishedProfile, at: datetime, *, peer_ids: list[UUID] | None = None
) -> list[PeerRow]:
    """Every exclusion rule in SQL (05 section 9): consent, age, activity, staleness,
    shared language, strict goals, blocks, cooldowns, open rooms and live requests."""
    me = user.id
    goal = own.payload["goal"]
    first = aliased(PublishedProfile)
    pending_incoming = (
        select(func.count())
        .select_from(ConnectionRequest)
        .where(
            ConnectionRequest.recipient_id == User.id,
            ConnectionRequest.status == "pending",
            ConnectionRequest.expires_at > at,
        )
        .scalar_subquery()
    )
    first_published = (
        select(func.min(first.created_at)).where(first.user_id == User.id).scalar_subquery()
    )
    blocked = exists().where(
        or_(
            and_(Block.blocker_id == me, Block.blocked_id == User.id),
            and_(Block.blocker_id == User.id, Block.blocked_id == me),
        )
    )
    unavailable_pair = exists().where(
        Pair.low_user_id == func.least(me, User.id),
        Pair.high_user_id == func.greatest(me, User.id),
        or_(
            Pair.cooldown_until > at,
            exists().where(Connection.pair_id == Pair.id, Connection.status == "open"),
            # A live (or recently lapsed, not yet materialized) request still hides the pair.
            exists().where(
                ConnectionRequest.pair_id == Pair.id,
                ConnectionRequest.status == "pending",
                ConnectionRequest.expires_at > at - timedelta(days=30),
            ),
        ),
    )
    recently_seen = User.last_seen_at > at - INACTIVE_AFTER
    statement = (
        select(
            User.id,
            PublishedProfile.version,
            PublishedProfile.payload,
            Consent.version.label("consent_version"),
            pending_incoming.label("pending_incoming"),
            first_published.label("first_published_at"),
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
            User.id != me,
            User.status == "active",
            User.age_band == "adult",
            ~User.deletion_pending,
            or_(User.social_restricted_until.is_(None), User.social_restricted_until <= at),
            recently_seen | User.last_seen_at.is_(None)
            if at < LAST_SEEN_ENFORCED_FROM
            else recently_seen,
            PublishedProfile.created_at > at - STALE_PROFILE_AFTER,
            PublishedProfile.payload["languages"].has_any(
                array(own.payload["languages"], type_=String)
            ),
            or_(
                func.coalesce(PublishedProfile.payload["strict_goal"].as_boolean(), False).is_(
                    False
                ),
                PublishedProfile.payload["goal"].astext == goal,
            ),
            ~blocked,
            ~unavailable_pair,
        )
        .order_by(User.id)
        .limit(SCAN_LIMIT)
    )
    if own.payload.get("strict_goal"):
        statement = statement.where(PublishedProfile.payload["goal"].astext == goal)
    if peer_ids is not None:
        statement = statement.where(User.id.in_(peer_ids))
    return [PeerRow(*row) for row in (await db.execute(statement)).all()]


def rank_v1(own: PublishedProfile, peers: list[PeerRow]) -> list[UUID]:
    """The original order: hard goal equality, v1 points >= 30, ties by peer UUID."""
    ranked = []
    for peer in peers:
        if peer.payload["goal"] != own.payload["goal"]:
            continue
        points = scoring_compat.score(own.payload, peer.payload)
        if points >= 30:
            ranked.append((points, str(peer.id), peer.id))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [item[2] for item in ranked]


def rank_v2(
    viewer_id: UUID, own: PublishedProfile, peers: list[PeerRow], local_date: date, at: datetime
) -> list[UUID]:
    candidates = []
    for peer in peers:
        breakdown = scoring_v2.score(own.payload, peer.payload)
        if scoring_v2.goal_allowed(own.payload, peer.payload) and scoring_v2.eligible(breakdown):
            candidates.append(
                ranking.Candidate(
                    peer.id,
                    breakdown.score,
                    peer.payload,
                    peer.first_published_at,
                    peer.pending_incoming,
                )
            )
    return ranking.rank(viewer_id, candidates, local_date, at, SHORTLIST)


async def ranked_candidates(db, user, own, own_consent, scorer: str = "v1", at=None):
    """Shortlist of peer ids for the locked recheck, using the configured scorer."""
    at = at or now()
    peers = await eligible_peers(db, user, own, at)
    if scorer == "v2":
        local_date = at.astimezone(ZoneInfo(user.timezone)).date()
        return rank_v2(user.id, own, peers, local_date, at)[:SHORTLIST]
    v1 = rank_v1(own, peers)
    if scorer == "shadow":
        local_date = at.astimezone(ZoneInfo(user.timezone)).date()
        v2 = rank_v2(user.id, own, peers, local_date, at)
        top1, top2 = set(v1[:5]), set(v2[:5])
        overlap = len(top1 & top2) / max(1, len(top1), len(top2))
        # Aggregates only: never ids, tags or scores (privacy, 05 section 11).
        log.info(
            "matching_shadow overlap_at5=%.2f v1_count=%d v2_count=%d", overlap, len(v1), len(v2)
        )
    return v1[:SHORTLIST]
