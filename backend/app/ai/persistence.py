"""Short transactions for transcript persistence and worker-fenced AI turns."""

import logging
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, select, update

from app.ai.models import AiConversation, AiMessageRecord, AiTurn
from app.ai.schemas import AIMessage, AiPreferenceView, ConversationHeader, ConversationView
from app.ai.store import Conversation
from app.core.errors import DomainError
from app.infrastructure.database.models import AiRun, now

log = logging.getLogger("moodprint")


def preference_view(p, settings):
    return AiPreferenceView(
        history_enabled=bool(p and p.history_enabled),
        semantic_memory_enabled=bool(p and p.semantic_memory_enabled),
        version=p.version if p else 1,
        policy_version=p.policy_version if p else "ai-data-v1",
        retention_days=settings.chat_retention_days,
        history_available=settings.chat_history_enabled,
        semantic_memory_available=bool(
            getattr(settings, "semantic_memory_enabled", False)
            and getattr(settings, "voyage_api_key", None)
            and settings.voyage_api_key.get_secret_value()
        ),
    )


def conversation_header(c):
    return ConversationHeader(
        conversation_id=c.id,
        bot_id=c.bot_id,
        version=c.version,
        expires_at=c.expires_at,
        persistent=True,
        title=c.title,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


async def owned_conversation(db, identity, user_id, *, lock=False):
    statement = select(AiConversation).where(
        AiConversation.id == identity,
        AiConversation.user_id == user_id,
        AiConversation.expires_at > now(),
    )
    if lock:
        statement = statement.with_for_update()
    return await db.scalar(statement)


async def conversation_view(db, c, limit=50, before=None):
    statement = (
        select(AiMessageRecord, AiRun.status)
        .join(AiRun, AiRun.id == AiMessageRecord.run_id)
        .where(AiMessageRecord.conversation_id == c.id)
    )
    if before:
        sequence = await db.scalar(
            select(AiMessageRecord.sequence).where(
                AiMessageRecord.conversation_id == c.id, AiMessageRecord.id == before
            )
        )
        if sequence is None:
            raise DomainError(422, "INVALID_CURSOR", "Mốc tin nhắn không thuộc cuộc trò chuyện.")
        statement = statement.where(AiMessageRecord.sequence < sequence)
    records = (
        await db.execute(statement.order_by(AiMessageRecord.sequence.desc()).limit(limit + 1))
    ).all()
    messages = [
        AIMessage(
            id=m.id,
            actor=m.actor,
            text=m.text,
            cards=m.cards,
            created_at=m.created_at,
            run_id=m.run_id,
            status=status,
        )
        for m, status in reversed(records[:limit])
    ]
    active = (
        await db.execute(
            select(AiRun.id, AiRun.version).where(
                AiRun.conversation_id == c.id, AiRun.status == "running"
            )
        )
    ).first()
    return ConversationView(
        **conversation_header(c).model_dump(),
        messages=messages,
        active_run_id=active[0] if active else None,
        active_run_version=active[1] if active else None,
        has_more_messages=len(records) > limit,
    )


async def load_runtime_conversation(db, c, session_id):
    # Context is always the newest bounded page; old transcript remains pageable.
    view = await conversation_view(db, c, limit=40)
    return Conversation(
        str(c.user_id),
        str(session_id),
        c.bot_id,
        id=c.id,
        version=c.version,
        expires_at=c.expires_at,
        messages=view.messages,
        active_run_id=view.active_run_id,
        persistent=True,
    )


async def recover_turns(db):
    expired = (
        await db.scalars(
            select(AiTurn.run_id)
            .join(AiRun, AiRun.id == AiTurn.run_id)
            .where(AiRun.status == "running", AiTurn.lease_until <= now())
            .limit(1000)
            .with_for_update(of=AiTurn, skip_locked=True)
        )
    ).all()
    if expired:
        await db.execute(
            update(AiRun)
            .where(AiRun.id.in_(expired), AiRun.status == "running")
            .values(status="interrupted", version=2)
        )


async def current_turn(db, run, worker_id):
    turn = await db.scalar(select(AiTurn).where(AiTurn.run_id == run.id).with_for_update())
    # Legacy metadata exists in pre-migration tests; new requests always have a lease.
    if turn is not None and (turn.worker_id != worker_id or turn.lease_until <= now()):
        raise DomainError(410, "WORKER_FENCED", "Lượt trò chuyện đã kết thúc.")
    return turn


async def purge_chat(db):
    ids = (
        await db.scalars(
            select(AiConversation.id)
            .where(AiConversation.expires_at <= now())
            .limit(250)
            .with_for_update(skip_locked=True)
        )
    ).all()
    if ids:
        await db.execute(
            update(AiRun)
            .where(AiRun.conversation_id.in_(ids), AiRun.status == "running")
            .values(status="interrupted", version=2)
        )
        await db.execute(delete(AiConversation).where(AiConversation.id.in_(ids)))
    # Content-free ephemeral coordination does not need indefinite retention.
    await db.execute(
        delete(AiTurn).where(
            AiTurn.conversation_id.is_(None), AiTurn.lease_until < now() - timedelta(days=1)
        )
    )


QUOTA_ZONE = ZoneInfo("Asia/Bangkok")


def quota_day_start(at: datetime) -> datetime:
    """Midnight of the current day in Asia/Bangkok (the product's quota day), as an instant."""
    local = at.astimezone(QUOTA_ZONE)
    return local.replace(hour=0, minute=0, second=0, microsecond=0)


async def daily_turns(db, user_id, at: datetime) -> int:
    return (
        await db.scalar(
            select(func.count())
            .select_from(AiRun)
            .where(AiRun.user_id == user_id, AiRun.created_at >= quota_day_start(at))
        )
        or 0
    )


async def spent_today_nano(db, at: datetime) -> int:
    """Estimated spend since UTC midnight from content-free usage rows (0 if absent)."""
    from sqlalchemy import text

    if not await db.scalar(select(func.to_regclass("moodprint.ai_usage"))):
        return 0
    midnight = at.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    return int(
        await db.scalar(
            text(
                "select coalesce(sum(estimated_nano_usd), 0) from moodprint.ai_usage "
                "where created_at >= :since"
            ),
            {"since": midnight},
        )
        or 0
    )


async def admission(db, user, settings):
    # Shared across processes; keep this lock only around the short admission transaction.
    from sqlalchemy import text

    await db.execute(text("select pg_advisory_xact_lock(664201, 1)"))
    await recover_turns(db)
    active = await db.scalar(
        select(func.count()).select_from(AiRun).where(AiRun.status == "running")
    )
    own = await db.scalar(
        select(func.count())
        .select_from(AiRun)
        .where(AiRun.status == "running", AiRun.user_id == user.id)
    )
    recent = await db.scalar(
        select(func.count())
        .select_from(AiRun)
        .where(AiRun.user_id == user.id, AiRun.created_at > now() - timedelta(minutes=1))
    )
    if active >= settings.ai_global_concurrency or own >= settings.ai_user_concurrency:
        raise DomainError(
            429, "RUN_LIMIT", "Đang có nhiều lượt trò chuyện. Hãy thử lại sau ít giây.", True
        )
    if recent >= settings.ai_requests_per_minute:
        raise DomainError(
            429, "RATE_LIMIT", "Bạn đã gửi nhiều tin nhắn. Hãy nghỉ một chút rồi thử lại.", True
        )
    at = now()
    if await daily_turns(db, user.id, at) >= settings.ai_daily_turns_per_user:
        log.info("metric=ai_quota_denied")
        raise DomainError(
            429,
            "AI_DAILY_QUOTA",
            "Hôm nay bạn đã dùng hết lượt trò chuyện với trợ lý. Hẹn bạn ngày mai nhé.",
            True,
        )
    if settings.ai_daily_budget_usd > 0 and settings.ai_accounting_enabled:
        ceiling = int(settings.ai_daily_budget_usd * 1_000_000_000)
        spent = await spent_today_nano(db, at)
        if spent >= ceiling:
            log.warning("metric=ai_budget_denied")
            raise DomainError(
                503,
                "AI_BUDGET_EXHAUSTED",
                "Trợ lý tạm nghỉ vì đã đạt giới hạn sử dụng hôm nay. Vui lòng thử lại sau.",
                True,
            )
        if spent >= ceiling * 0.8:
            log.warning("metric=ai_budget_ratio value=%.2f", spent / ceiling)
