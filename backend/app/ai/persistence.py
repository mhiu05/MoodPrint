"""Short transactions for transcript persistence and worker-fenced AI turns."""

import logging
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, select, update

from app.ai.context import ContextStamp
from app.ai.models import AiConversation, AiMessageRecord, AiTurn
from app.ai.schemas import AIMessage, AiPreferenceView, ConversationHeader, ConversationView
from app.ai.store import Conversation
from app.core.errors import DomainError
from app.infrastructure.database.models import AiRun, now

log = logging.getLogger("moodprint")


def preference_view(p, settings):
    return AiPreferenceView(
        history_enabled=settings.chat_history_enabled,
        semantic_memory_enabled=bool(p and p.semantic_memory_enabled),
        version=p.version if p else 1,
        policy_version=p.policy_version if p else "ai-data-v1",
        retention_days=min(settings.chat_retention_days, 30),
        history_available=settings.chat_history_enabled,
        semantic_memory_available=bool(
            getattr(settings, "semantic_memory_enabled", False)
            and getattr(settings, "voyage_api_key", None)
            and settings.voyage_api_key.get_secret_value()
        ),
    )


def conversation_header(c):
    from app.ai.agents import is_legacy

    return ConversationHeader(
        conversation_id=c.id,
        bot_id=c.bot_id,
        version=c.version,
        expires_at=c.expires_at,
        persistent=True,
        title=c.title,
        created_at=c.created_at,
        updated_at=c.updated_at,
        legacy=is_legacy(c.bot_id),
        active_agent=c.active_agent,
    )


async def owned_conversation(db, identity, user_id, *, lock=False, kind="direct"):
    # Direct-chat endpoints never accept a group id (V3); groups use app.ai.groups.
    statement = select(AiConversation).where(
        AiConversation.id == identity,
        AiConversation.user_id == user_id,
        AiConversation.expires_at > now(),
        AiConversation.kind == kind,
    )
    if lock:
        statement = statement.with_for_update()
    return await db.scalar(statement)


def collaboration_view(edge, rule_id):
    """Template line for a completed, used receipt; never model text (ADR-11)."""
    from app.ai.collaboration.contracts import CollaborationSummary
    from app.ai.collaboration.policy import EDGES, summary_for

    summary = summary_for(edge, rule_id) if edge else None
    if summary is None:
        return None
    spec = EDGES[edge]
    return CollaborationSummary(kind=edge, companions=[spec.specialist, spec.requester], summary=summary)


def message_view(m, run, collaboration=None, steps=None) -> AIMessage:
    from app.ai.agents import ALL_IDS

    speaker = getattr(run, "bot_id", None)
    return AIMessage(
        id=m.id,
        actor=m.actor,
        text=m.text,
        cards=m.cards,
        created_at=m.created_at,
        run_id=m.run_id,
        status=run.status,
        part_index=m.part_index,
        part_count=m.part_count,
        # A handoff/group child run (origin "agent") answers a user-initiated turn.
        origin=run.origin if run.origin == "proactive" else "user",
        proactive_slot=run.proactive_slot,
        collaboration=collaboration if m.actor == "bot" and m.part_index == 0 else None,
        speaker=speaker if m.actor == "bot" and speaker in ALL_IDS else None,
        steps=steps if m.actor == "bot" and m.part_index == 0 and steps else None,
    )


async def conversation_view(db, c, limit=50, before=None, *, collaboration=False):
    messages, has_more, active = await message_page(db, c, limit, before, collaboration=collaboration)
    return ConversationView(
        **conversation_header(c).model_dump(),
        messages=messages,
        active_run_id=active[0] if active else None,
        active_run_version=active[1] if active else None,
        has_more_messages=has_more,
    )


async def message_page(db, c, limit=50, before=None, *, collaboration=False):
    """(messages, has_more, (active run id, version) | None) of a direct chat or a group."""
    run_columns = (AiRun.status, AiRun.origin, AiRun.proactive_slot, AiRun.bot_id, AiRun.parent_run_id)
    statement = (
        select(AiMessageRecord, *run_columns)
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
    page = list(reversed(records[:limit]))
    has_more = len(records) > limit
    if page and page[0][0].part_index > 0:
        # Never cut a bubble group at the page edge: pull in its earlier parts.
        oldest = page[0][0]
        missing = (
            await db.execute(
                select(AiMessageRecord, *run_columns)
                .join(AiRun, AiRun.id == AiMessageRecord.run_id)
                .where(
                    AiMessageRecord.conversation_id == c.id,
                    AiMessageRecord.run_id == oldest.run_id,
                    AiMessageRecord.actor == oldest.actor,
                    AiMessageRecord.sequence < oldest.sequence,
                )
                .order_by(AiMessageRecord.sequence)
            )
        ).all()
        page = [*missing, *page]
        has_more = bool(
            await db.scalar(
                select(AiMessageRecord.id)
                .where(
                    AiMessageRecord.conversation_id == c.id,
                    AiMessageRecord.sequence < page[0][0].sequence,
                )
                .limit(1)
            )
        )
    lines: dict = {}
    if collaboration and page:
        from app.ai.collaboration.models import AiCollaboration

        lines = {
            run_id: collaboration_view(edge, rule_id)
            for run_id, edge, rule_id in (
                await db.execute(
                    select(AiCollaboration.primary_run_id, AiCollaboration.edge, AiCollaboration.rule_id).where(
                        AiCollaboration.user_id == c.user_id,
                        AiCollaboration.primary_run_id.in_({row[0].run_id for row in page if row[0].run_id}),
                        AiCollaboration.status == "completed",
                        AiCollaboration.used_in_reply.is_(True),
                    )
                )
            ).all()
        }
    steps: dict = {}
    if page:
        # V3: receipt-backed specialist steps of each turn; a handoff reply sits on a child run.
        from app.ai.orchestration.models import AiOrchestrationStep
        from app.ai.schemas import ReplyStep

        workflows = {row.parent_run_id or row[0].run_id for row in page if row[0].actor == "bot"}
        for workflow, kind, target in (
            await db.execute(
                select(AiOrchestrationStep.workflow_run_id, AiOrchestrationStep.kind, AiOrchestrationStep.target_bot)
                .where(
                    AiOrchestrationStep.user_id == c.user_id, AiOrchestrationStep.workflow_run_id.in_(workflows),
                    AiOrchestrationStep.kind.in_(("consult", "handoff")),
                    AiOrchestrationStep.status == "completed", AiOrchestrationStep.used_in_reply.is_(True),
                )
                .order_by(AiOrchestrationStep.started_at, AiOrchestrationStep.id)
            )
        ).all():
            steps.setdefault(workflow, []).append(ReplyStep(kind=kind, companion=target))
    messages = [
        message_view(row[0], row, lines.get(row[0].run_id), steps.get(row.parent_run_id or row[0].run_id))
        for row in page
    ]
    active = (
        await db.execute(
            select(AiRun.id, AiRun.version).where(
                AiRun.conversation_id == c.id, AiRun.status == "running"
            )
        )
    ).first()
    return messages, has_more, (active[0], active[1]) if active else None


async def load_runtime_conversation(db, c, session_id):
    # Context is always the newest bounded page; old transcript remains pageable.
    messages, _more, active = await message_page(db, c, limit=40)
    run_ids = [m.run_id for m in messages if m.run_id]
    # V3: bubbles of a handoff target live under a child run; they share the turn's stamp.
    parents = dict(
        (await db.execute(
            select(AiRun.id, AiRun.parent_run_id).where(
                AiRun.id.in_(run_ids), AiRun.user_id == c.user_id, AiRun.origin == "agent",
            )
        )).all()
    )
    turns = (
        await db.scalars(
            select(AiTurn).where(
                AiTurn.user_id == c.user_id,
                AiTurn.conversation_id == c.id,
                AiTurn.run_id.in_([parents.get(identity, identity) for identity in run_ids]),
            )
        )
    ).all()
    stamps = {t.run_id: ContextStamp(t.data_version, t.context_policy) for t in turns}
    for child, parent in parents.items():
        if parent in stamps:
            stamps[child] = stamps[parent]
    segment: frozenset = frozenset()
    if c.active_agent and c.active_agent_since is not None:
        segment = frozenset((await db.scalars(
            select(AiMessageRecord.id).where(
                AiMessageRecord.conversation_id == c.id, AiMessageRecord.sequence >= c.active_agent_since,
            )
        )).all())
    return Conversation(
        str(c.user_id),
        str(session_id),
        c.bot_id,
        id=c.id,
        version=c.version,
        expires_at=c.expires_at,
        messages=messages,
        context_stamps=stamps,
        active_run_id=active[0] if active else None,
        persistent=True,
        active_agent=c.active_agent,
        segment_ids=segment,
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
        await interrupt_consultations(db, expired)


async def close_orphaned_consultations(db) -> None:
    """Retention sweep: a consultation still open while its primary run already ended (a
    settle that failed, or a crash recovered by the usage lease first) is closed, never left
    'authorized'. Completed-but-unused receipts are legitimate and stay as they are."""
    from app.ai.collaboration.models import AiCollaboration

    ended = (
        await db.scalars(
            select(AiCollaboration.id)
            .join(AiRun, AiRun.id == AiCollaboration.primary_run_id)
            .where(AiCollaboration.status == "authorized", AiRun.status != "running")
            .limit(1000)
            .with_for_update(of=AiCollaboration, skip_locked=True)
        )
    ).all()
    if ended:
        await db.execute(
            update(AiCollaboration).where(AiCollaboration.id.in_(ended))
            .values(status="cancelled", failure_code="interrupted", finished_at=now())
        )
    parent = select(AiRun.id).where(AiRun.status == "running").scalar_subquery()
    await db.execute(
        update(AiRun)
        .where(AiRun.origin == "collaboration", AiRun.status == "running", AiRun.parent_run_id.not_in(parent))
        .values(status="interrupted", version=2)
    )


async def interrupt_consultations(db, primary_run_ids) -> None:
    """A consultation never outlives its primary run (crash recovery, Phase 2)."""
    from sqlalchemy import case

    from app.ai.collaboration.models import AiCollaboration

    await db.execute(
        update(AiRun)
        .where(AiRun.parent_run_id.in_(primary_run_ids), AiRun.status == "running")
        .values(status="interrupted", version=2)
    )
    await db.execute(
        update(AiCollaboration)
        .where(
            AiCollaboration.primary_run_id.in_(primary_run_ids),
            AiCollaboration.status.in_(("authorized", "completed")),
            AiCollaboration.used_in_reply.is_(False),
        )
        .values(
            status=case((AiCollaboration.status == "authorized", "cancelled"), else_="discarded"),
            failure_code="interrupted",
        )
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
            # Check-ins the user scheduled never consume their own chat turns.
            .where(
                AiRun.user_id == user_id,
                AiRun.origin == "user",
                AiRun.created_at >= quota_day_start(at),
            )
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
    # Global capacity counts every origin (chat and check-ins share the provider).
    active = await db.scalar(
        select(func.count()).select_from(AiRun).where(AiRun.status == "running")
    )
    own = await db.scalar(
        select(func.count())
        .select_from(AiRun)
        .where(AiRun.status == "running", AiRun.user_id == user.id, AiRun.origin == "user")
    )
    recent = await db.scalar(
        select(func.count())
        .select_from(AiRun)
        .where(
            AiRun.user_id == user.id,
            AiRun.origin == "user",
            AiRun.created_at > now() - timedelta(minutes=1),
        )
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
