import asyncio
from contextlib import ExitStack
from datetime import timedelta
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import delete, select, tuple_, update
from starlette.background import BackgroundTask

from app.ai.context import MOOD_TURN_POLICY, TEXT_POLICY, ContextStamp
from app.ai.models import AiConversation, AiMessageRecord, AiPreference, AiTurn
from app.ai.persistence import (
    admission,
    conversation_header,
    conversation_view,
    load_runtime_conversation,
    owned_conversation,
    preference_view,
    recover_turns,
)
from app.ai.runtime import LiveRun
from app.ai.schemas import (
    AIMessage,
    AiPreferenceInput,
    AiPreferenceView,
    AIRunAccepted,
    ConversationHeader,
    ConversationInput,
    ConversationRename,
    ConversationView,
    StartRunInput,
)
from app.contracts import BotId, BotPublicDTO, VersionInput
from app.core.errors import DomainError
from app.core.limits import AttemptLimiter
from app.core.security import (
    Actor,
    assert_purpose,
    digest,
    idempotency_key,
    previous_receipt,
    require_actor,
    save_receipt,
    transaction,
)
from app.infrastructure.database.models import AiRun, Consent, Memory, now
from app.modules.guests.accounting import reserve_guest_operation
from app.modules.guests.accounting import unavailable as guest_paid_unavailable
from app.modules.guests.limits import reserve_guest_quota
from app.modules.guests.output import REVOKED_EVENT
from app.modules.guests.policy import guest_paid_available
from app.modules.guests.pricing import ai_upper, budget_nano

router = APIRouter()
DEFAULT_TITLE = "Cuộc trò chuyện mới"
# Per worker. Each stream polls PostgreSQL, so one account must not drain the pool.
MAX_STREAMS_PER_USER = 6  # Mirrors AiRuntime.streams; kept for tests and docs.
# Each export materializes up to the full saved thread in memory.
EXPORT_LIMIT = AttemptLimiter(
    20, 3600, "EXPORT_RATE_LIMITED", "Bạn đã xuất nhiều lần. Vui lòng thử lại sau."
)
MAX_SAVED_CONVERSATIONS = 500


async def _ephemeral_epoch(db, user_id):
    """Current AI consent version and latest private-data deletion request time."""
    from sqlalchemy import func

    from app.modules.users.models import DataJob

    ai_version = await db.scalar(
        select(Consent.version).where(Consent.user_id == user_id, Consent.purpose == "AI")
    )
    deleted_at = await db.scalar(
        select(func.max(DataJob.created_at)).where(
            DataJob.user_id == user_id, DataJob.kind == "deletion"
        )
    )
    return ai_version, deleted_at


def _stale(c, epoch) -> bool:
    ai_version, deleted_at = epoch
    return c.ai_consent_version != ai_version or bool(deleted_at and deleted_at >= c.created_wall)


async def live_ephemeral(db, runtime, user_id, conversation_id, session_id):
    # RAM invalidation reaches only the worker that handled the change; every
    # worker re-checks the durable consent/deletion state before using its copy.
    c = runtime.store.get(conversation_id, str(user_id), str(session_id))
    if not c.persistent and _stale(c, await _ephemeral_epoch(db, user_id)):
        runtime.store.conversations.pop(c.id, None)
        raise DomainError(410, "CONVERSATION_EXPIRED", "Phiên trò chuyện đã kết thúc.")
    return c


def ephemeral_header(c):
    return ConversationHeader(
        conversation_id=c.id, bot_id=c.bot_id, version=c.version, expires_at=c.expires_at
    )


@router.get("/bots", response_model=list[BotPublicDTO])
async def bots():
    from app.ai.registry import BOTS

    return BOTS


@router.get("/ai/preferences", response_model=AiPreferenceView)
async def preferences(request: Request, actor: Actor = Depends(require_actor)):
    async with transaction(request, actor) as (db, user):
        return preference_view(await db.get(AiPreference, user.id), request.app.state.settings)


@router.put("/ai/preferences", response_model=AiPreferenceView)
async def update_preferences(
    body: AiPreferenceInput, request: Request, actor: Actor = Depends(require_actor)
):
    settings = request.app.state.settings
    key, payload = idempotency_key(request), body.model_dump(mode="json")
    async with transaction(request, actor) as (db, user):
        old = await previous_receipt(db, user, "ai:preferences", key, payload)
        p = await db.get(AiPreference, user.id)
        if old:
            return preference_view(p, settings)
        if (p.version if p else 1) != body.expected_version:
            raise DomainError(409, "STALE_VERSION", "Tùy chọn đã thay đổi. Vui lòng tải lại.")
        if body.history_enabled and not settings.chat_history_enabled:
            raise DomainError(503, "HISTORY_UNAVAILABLE", "Lưu lịch sử chưa sẵn sàng.")
        if (
            body.semantic_memory_enabled
            and not preference_view(p, settings).semantic_memory_available
        ):
            raise DomainError(503, "SEMANTIC_UNAVAILABLE", "Tìm ghi nhớ liên quan chưa sẵn sàng.")
        if body.semantic_memory_enabled:
            await assert_purpose(db, user, "MEM")
        if p is None:
            p = AiPreference(
                user_id=user.id, history_enabled=False, semantic_memory_enabled=False, version=1
            )
            db.add(p)
        p.history_enabled, p.semantic_memory_enabled = (
            body.history_enabled,
            body.semantic_memory_enabled,
        )
        p.version += 1
        p.policy_version, p.updated_at = body.policy_version, now()
        user.data_version += 1
        await db.execute(
            update(AiRun)
            .where(AiRun.user_id == user.id, AiRun.status == "running")
            .values(status="cancelled", version=2)
        )
        await db.flush()
        if body.semantic_memory_enabled:
            from app.ai.embeddings import enqueue_memory

            for m in (
                await db.scalars(
                    select(Memory)
                    .where(Memory.user_id == user.id, Memory.status == "active")
                    .limit(1000)
                )
            ).all():
                await enqueue_memory(db, m, settings)
        else:
            from app.ai.embeddings import discard_user_index

            await discard_user_index(db, user.id)
        save_receipt(db, user, "ai:preferences", key, payload, {"version": p.version})
        result = preference_view(p, settings)
    request.app.state.ai.invalidate(str(actor.user_id))
    return result


@router.get("/ai/conversations", response_model=list[ConversationHeader])
async def conversations(
    request: Request,
    limit: int = Query(30, ge=1, le=100),
    before: UUID | None = None,
    bot_id: BotId | None = Query(None, alias="botId"),
    actor: Actor = Depends(require_actor),
):
    async with transaction(request, actor) as (db, user):
        statement = select(AiConversation).where(
            AiConversation.user_id == user.id, AiConversation.expires_at > now()
        )
        if bot_id:
            statement = statement.where(AiConversation.bot_id == bot_id)
        if before:
            cursor = await owned_conversation(db, before, user.id)
            if not cursor:
                raise DomainError(422, "INVALID_CURSOR", "Mốc lịch sử chưa hợp lệ.")
            statement = statement.where(
                tuple_(AiConversation.updated_at, AiConversation.id)
                < tuple_(cursor.updated_at, cursor.id)
            )
        result = [
            conversation_header(c)
            for c in (
                await db.scalars(
                    statement.order_by(
                        AiConversation.updated_at.desc(), AiConversation.id.desc()
                    ).limit(limit)
                )
            ).all()
        ]
        consents = await db.execute(select(Consent).where(Consent.user_id == user.id))
        ai_on = any(c.purpose == "AI" and c.enabled for c in consents.scalars())
        epoch = await _ephemeral_epoch(db, user.id)
    runtime = request.app.state.ai
    runtime.sweep()
    for identity, copy in list(runtime.store.conversations.items()):
        if copy.user_id == str(actor.user_id) and not copy.persistent and _stale(copy, epoch):
            del runtime.store.conversations[identity]
    if ai_on and before is None and len(result) < limit:
        result += [
            ephemeral_header(c)
            for c in runtime.store.conversations.values()
            if not c.persistent
            and c.user_id == str(actor.user_id)
            and c.session_id == str(actor.session_id)
            and (bot_id is None or c.bot_id == bot_id)
        ][: limit - len(result)]
    return result


@router.post("/ai/conversations", response_model=ConversationHeader, status_code=201)
async def create_conversation(
    body: ConversationInput, request: Request, actor: Actor = Depends(require_actor)
):
    key, payload = idempotency_key(request), body.model_dump(mode="json")
    runtime, settings = request.app.state.ai, request.app.state.settings
    runtime.sweep()
    async with transaction(request, actor) as (db, user):
        consents = await assert_purpose(db, user, "AI")
        old = await previous_receipt(db, user, "ai:create", key, payload)
        if old:
            c = await owned_conversation(db, UUID(old["conversationId"]), user.id)
            if c:
                return conversation_header(c)
            return ephemeral_header(
                await live_ephemeral(
                    db, runtime, user.id, UUID(old["conversationId"]), actor.session_id
                )
            )
        if not runtime.available_for(actor.user_id):
            raise DomainError(503, "AI_UNAVAILABLE", "Trò chuyện AI chưa sẵn sàng.", True)
        if user.account_kind == "guest" and not guest_paid_available(settings, "ai"):
            raise guest_paid_unavailable()
        p = await db.get(AiPreference, user.id)
        persistent = (
            body.persistent
            if body.persistent is not None
            else bool(p and p.history_enabled and settings.chat_history_enabled)
        )
        if persistent and not (p and p.history_enabled and settings.chat_history_enabled):
            raise DomainError(
                403,
                "HISTORY_CONSENT_REQUIRED",
                "Hãy bật lưu lịch sử trước khi tạo cuộc trò chuyện được lưu.",
            )
        if persistent:
            from sqlalchemy import func

            saved = await db.scalar(
                select(func.count())
                .select_from(AiConversation)
                .where(AiConversation.user_id == user.id, AiConversation.expires_at > now())
            )
            if saved >= MAX_SAVED_CONVERSATIONS:
                raise DomainError(
                    429, "CONVERSATION_LIMIT", "Hãy xóa bớt hội thoại đã lưu trước khi tạo thêm."
                )
            retention = now() + timedelta(days=min(settings.chat_retention_days, 30))
            c = AiConversation(
                user_id=user.id,
                bot_id=body.bot_id,
                expires_at=(
                    min(retention, user.guest_expires_at)
                    if user.account_kind == "guest" and user.guest_expires_at
                    else retention
                ),
            )
            db.add(c)
            await db.flush()
            result = conversation_header(c)
        else:
            bound = getattr(request.state, "guest_output", None)
            created = runtime.store.create(
                str(user.id),
                str(actor.session_id),
                body.bot_id,
                hard_deadline=bound.monotonic_deadline if bound else None,
                hard_expires_at=bound.expires_at if bound else None,
            )
            created.ai_consent_version = consents["AI"].version
            result = ephemeral_header(created)
        save_receipt(
            db, user, "ai:create", key, payload, {"conversationId": str(result.conversation_id)}
        )
    return result


@router.get("/ai/conversations/{conversation_id}", response_model=ConversationView)
async def conversation(
    conversation_id: UUID,
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    before: UUID | None = None,
    actor: Actor = Depends(require_actor),
):
    runtime = request.app.state.ai
    async with transaction(request, actor) as (db, user):
        await recover_turns(db)
        c = await owned_conversation(db, conversation_id, user.id)
        if c:
            return await conversation_view(db, c, limit, before)
        if await db.scalar(select(AiConversation.id).where(AiConversation.id == conversation_id)):
            raise DomainError(404, "NOT_FOUND", "Không tìm thấy cuộc trò chuyện.")
        c = await live_ephemeral(db, runtime, user.id, conversation_id, actor.session_id)
        await assert_purpose(db, user, "AI")
    run = runtime.runs.get(c.active_run_id)
    return ConversationView(
        **ephemeral_header(c).model_dump(),
        messages=c.messages,
        active_run_id=c.active_run_id,
        active_run_version=run.version if run else None,
    )


@router.post(
    "/ai/conversations/{conversation_id}/messages", response_model=AIRunAccepted, status_code=202
)
async def send(
    conversation_id: UUID,
    body: StartRunInput,
    request: Request,
    actor: Actor = Depends(require_actor),
):
    idempotency_key(request)
    runtime, settings = request.app.state.ai, request.app.state.settings
    with ExitStack() as input_buffer:
        async with transaction(request, actor) as (db, user):
            await assert_purpose(db, user, "AI")
            persistent = await owned_conversation(db, conversation_id, user.id, lock=True)
            c = (
                await load_runtime_conversation(db, persistent, actor.session_id)
                if persistent
                else await live_ephemeral(db, runtime, user.id, conversation_id, actor.session_id)
            )
            raw_input = body.model_dump_json(include={"text", "mood_scope"})
            # Saved text is stored anyway; a temporary chat's digest is salted in RAM.
            message_digest = digest(raw_input if persistent else c.salt + raw_input)
            previous = await db.scalar(
                select(AiTurn).where(
                    AiTurn.scope_id == c.id,
                    AiTurn.client_message_id == body.client_message_id,
                    AiTurn.user_id == user.id,
                )
            )
            if previous:
                if previous.input_digest != message_digest:
                    raise DomainError(
                        409, "IDEMPOTENCY_CONFLICT", "Mã tin nhắn đã được dùng với nội dung khác."
                    )
                return AIRunAccepted(
                    run_id=previous.run_id,
                    conversation_id=c.id,
                    version=c.version,
                    events_url=f"/api/v1/ai/runs/{previous.run_id}/events",
                )
            if not runtime.available_for(actor.user_id):
                raise DomainError(503, "AI_UNAVAILABLE", "Trò chuyện AI chưa sẵn sàng.", True)
            if user.account_kind == "guest" and not guest_paid_available(settings, "ai"):
                raise guest_paid_unavailable()
            if persistent:
                p = await db.get(AiPreference, user.id)
                if not (p and p.history_enabled and settings.chat_history_enabled):
                    raise DomainError(
                        403,
                        "HISTORY_CONSENT_REQUIRED",
                        "Lưu lịch sử đang tắt. Hãy bật lại hoặc mở cuộc trò chuyện tạm mới.",
                    )
            if body.mood_scope is not None:
                from app.modules.mood.service import validate_scope

                if c.bot_id != "nhip":
                    raise DomainError(422, "MOOD_SCOPE_BOT", "Khoảng ngày chỉ dùng với Nhịp.")
                validate_scope(user, body.mood_scope)
            active = await db.scalar(
                select(AiRun.id).where(AiRun.conversation_id == c.id, AiRun.status == "running")
            )
            if active or c.active_run_id:
                raise DomainError(
                    409, "RUN_IN_PROGRESS", "Đang có một lượt trò chuyện chưa kết thúc."
                )
            if c.version != body.expected_conversation_version:
                raise DomainError(
                    409, "STALE_VERSION", "Cuộc trò chuyện đã thay đổi. Vui lòng tải lại."
                )
            await admission(db, user, settings)
            quota = reservation = None
            if user.account_kind == "guest":
                # One transaction: quota claim + worst-case reservation, rolled back together.
                key = str(body.client_message_id)
                quota = await reserve_guest_quota(
                    db, user, kind="ai", operation_key=key, payload_digest=message_digest, settings=settings
                )
                _version, upper = ai_upper(settings.guest_pricing_json)  # type: ignore[misc]
                reservation = await reserve_guest_operation(
                    db,
                    user,
                    "ai",
                    upper,
                    operation_key=key,
                    payload_digest=message_digest,
                    limit_nano_usd=budget_nano(settings.guest_daily_budget_usd) or 0,
                )
            run_id, message_id = uuid4(), uuid4()
            db.add(AiRun(id=run_id, user_id=user.id, conversation_id=c.id, bot_id=c.bot_id))
            await db.flush()
            db.add(
                AiTurn(
                    run_id=run_id,
                    user_id=user.id,
                    scope_id=c.id,
                    conversation_id=c.id if persistent else None,
                    session_id=actor.session_id,
                    client_message_id=body.client_message_id,
                    input_digest=message_digest,
                    data_version=user.data_version,
                    context_policy=MOOD_TURN_POLICY if body.mood_scope else TEXT_POLICY,
                    worker_id=runtime.worker_id,
                    lease_until=now() + timedelta(seconds=settings.ai_timeout_seconds + 15),
                )
            )
            await runtime.reserve_usage(db, run_id, user.id, c.bot_id)
            data_version = user.data_version
            if persistent:
                persistent.version += 1
                persistent.updated_at = now()
                if persistent.version == 2 and persistent.title == DEFAULT_TITLE:
                    persistent.title = " ".join(body.text.split())[:80] or DEFAULT_TITLE
                db.add(
                    AiMessageRecord(
                        id=message_id,
                        conversation_id=c.id,
                        sequence=persistent.version,
                        actor="self",
                        text=body.text,
                        cards=[],
                        run_id=run_id,
                    )
                )
                # At most one idle saved copy per account; drive() drops it when done.
                for identity, copy in list(runtime.store.conversations.items()):
                    if (
                        copy.persistent
                        and copy.user_id == str(user.id)
                        and copy.active_run_id is None
                        and identity != c.id
                    ):
                        del runtime.store.conversations[identity]
                runtime.store.conversations[c.id] = c
                runtime.store.touch(c)
            input_buffer.enter_context(runtime.reserve_input(c.id, len(body.text.encode()) + 1024))
        c.context_stamps[run_id] = ContextStamp(
            data_version, MOOD_TURN_POLICY if body.mood_scope else TEXT_POLICY
        )
        c.messages.append(
            AIMessage(
                id=message_id,
                actor="self",
                text=body.text,
                created_at=now(),
                run_id=run_id,
                status="running",
            )
        )
        c.version += 1
        c.active_run_id = run_id
        c.client_runs[str(body.client_message_id)] = (message_digest, run_id)
        run = LiveRun(
            actor,
            c.id,
            data_version,
            run_id,
            mood_scope=body.mood_scope,
            persistent=bool(persistent),
            deadline=getattr(request.state, "guest_output", None),
            quota=quota,
            reservation=reservation,
        )
        if reservation is not None:
            run.before_dispatch = runtime.guest_dispatch_guard(run)
        runtime.runs[run_id] = run
        runtime.event(run, "progress", {})
        run.task = asyncio.create_task(runtime.drive(run))
    return AIRunAccepted(
        run_id=run_id,
        conversation_id=c.id,
        version=c.version,
        events_url=f"/api/v1/ai/runs/{run_id}/events",
    )


async def durable_run(request, actor, run_id, *, poll=False, recover=True):
    # Polling reads never take the account row lock; lease recovery runs only on
    # every few ticks rather than on each 0.25 s read.
    async with transaction(request, actor, lock=not poll) as (db, user):
        await assert_purpose(db, user, "AI")
        if recover:
            await recover_turns(db)
        row = await db.scalar(select(AiRun).where(AiRun.id == run_id, AiRun.user_id == user.id))
        turn = await db.get(AiTurn, run_id)
        if row is None or turn is None or turn.conversation_id is None:
            raise DomainError(404, "NOT_FOUND", "Không tìm thấy lượt trò chuyện.")
        c = await owned_conversation(db, turn.conversation_id, user.id)
        if not c:
            raise DomainError(404, "NOT_FOUND", "Không tìm thấy cuộc trò chuyện.")
        if user.data_version != turn.data_version:
            raise DomainError(410, "CONTEXT_CHANGED", "Quyền hoặc dữ liệu đã thay đổi.")
        answer = await db.scalar(
            select(AiMessageRecord).where(
                AiMessageRecord.run_id == run_id, AiMessageRecord.actor == "bot"
            )
        )
        return row, turn, answer


async def authorized_run(request, actor, run_id, *, poll=False):
    runtime = request.app.state.ai
    run = runtime.runs.get(run_id)
    if run and run.persistent:
        await durable_run(request, actor, run_id, poll=poll)
        return run
    if (
        run is None
        or run.actor.user_id != actor.user_id
        or run.actor.session_id != actor.session_id
    ):
        raise DomainError(404, "NOT_FOUND", "Không tìm thấy lượt trò chuyện.")
    async with transaction(request, actor, lock=not poll) as (db, user):
        await assert_purpose(db, user, "AI")
        await live_ephemeral(db, runtime, user.id, run.conversation_id, actor.session_id)
        if user.data_version != run.data_version:
            raise DomainError(410, "CONTEXT_CHANGED", "Quyền hoặc dữ liệu đã thay đổi.")
    return run


@router.get("/ai/runs/{run_id}/events", response_class=StreamingResponse)
async def events(
    run_id: UUID,
    request: Request,
    after_seq: int = Query(0, alias="afterSeq", ge=0),
    actor: Actor = Depends(require_actor),
):
    from app.ai.schemas import AIEvent

    runtime = request.app.state.ai
    release = runtime.streams.reserve(actor.user_id)
    try:
        local = runtime.runs.get(run_id)
        persistent = local.persistent if local else True
        if persistent:
            await durable_run(request, actor, run_id)
        else:
            await authorized_run(request, actor, run_id)
        last = request.headers.get("Last-Event-ID")
        if last:
            try:
                after_seq = max(after_seq, int(last))
            except ValueError as exc:
                raise DomainError(422, "INVALID_CURSOR", "Mốc hội thoại chưa hợp lệ.") from exc
        if (
            after_seq < 0
            or (not persistent and after_seq > len(local.events))
            or (persistent and after_seq > 3)
        ):
            raise DomainError(409, "CURSOR_GAP", "Hãy tải lại cuộc trò chuyện.")
    except BaseException:
        release()
        raise

    async def stream():
        cursor, tick = after_seq, 0
        try:
            async for chunk in poll(cursor, tick):
                yield chunk
        finally:
            release()

    deadline = getattr(request.state, "guest_output", None)

    def past_deadline() -> bool:
        return deadline is not None and deadline.remaining() <= 0

    async def poll(cursor, tick):
        while not await request.is_disconnected():
            tick += 1
            if past_deadline():
                yield REVOKED_EVENT.decode()
                return
            try:
                # lock_actor in the polling read re-verifies the session each tick.
                if persistent:
                    row, turn, answer = await durable_run(
                        request, actor, run_id, poll=True, recover=tick % 8 == 1
                    )
                    data = [AIEvent(seq="1", type="progress", data={})]
                    if row.status == "completed" and answer is not None:
                        data += [
                            AIEvent(
                                seq="2",
                                type="final",
                                data={"text": answer.text, "cards": answer.cards},
                            ),
                            AIEvent(seq="3", type="completed", data={}),
                        ]
                    elif row.status != "running":
                        data += [
                            AIEvent(
                                seq="2",
                                type="cancelled" if row.status == "cancelled" else "failed",
                                data={
                                    "code": "AI_INTERRUPTED"
                                    if row.status == "interrupted"
                                    else "AI_RUN_FAILED",
                                    "message": "Phản hồi chưa hoàn tất. Bạn có thể gửi một lượt mới.",
                                },
                            )
                        ]
                    terminal = row.status != "running"
                else:
                    run = await authorized_run(request, actor, run_id, poll=True)
                    data, terminal = run.events, run.terminal
            except DomainError:
                yield REVOKED_EVENT.decode()
                return
            while cursor < len(data):
                if past_deadline():
                    # Each event (buffered or replayed, including the final) is judged on its own.
                    yield REVOKED_EVENT.decode()
                    return
                event = data[cursor]
                cursor += 1
                yield f"id: {event.seq}\nevent: {event.type}\ndata: {event.model_dump_json(by_alias=True)}\n\n"
            if terminal:
                return
            await asyncio.sleep(0.25 if persistent else 0.1)
            if past_deadline():
                yield REVOKED_EVENT.decode()
                return
            yield ": heartbeat\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        # Also releases the slot if the client leaves before the body starts.
        background=BackgroundTask(release),
    )


@router.post("/ai/runs/{run_id}/cancel")
async def cancel(
    run_id: UUID, body: VersionInput, request: Request, actor: Actor = Depends(require_actor)
):
    runtime = request.app.state.ai
    local = runtime.runs.get(run_id)
    if local and not local.persistent:
        run = await authorized_run(request, actor, run_id)
        if not run.terminal and body.expected_version != run.version:
            raise DomainError(409, "STALE_VERSION", "Lượt trò chuyện đã thay đổi.")
        await runtime.stop(run)
        return {"runId": str(run.id), "version": run.version, "status": "ended"}
    await durable_run(request, actor, run_id)
    async with transaction(request, actor) as (db, user):
        row = await db.scalar(
            select(AiRun).where(AiRun.id == run_id, AiRun.user_id == user.id).with_for_update()
        )
        if row.status == "running":
            if body.expected_version != row.version:
                raise DomainError(409, "STALE_VERSION", "Lượt trò chuyện đã thay đổi.")
            row.status, row.version = "cancelled", 2
    if local:
        await runtime.stop(local)
    return {"runId": str(run_id), "version": 2, "status": "ended"}


@router.patch("/ai/conversations/{conversation_id}", response_model=ConversationHeader)
async def rename_conversation(
    conversation_id: UUID,
    body: ConversationRename,
    request: Request,
    actor: Actor = Depends(require_actor),
):
    # History management stays available with AI off; the title never reaches a model.
    key, payload = idempotency_key(request), body.model_dump(mode="json")
    async with transaction(request, actor) as (db, user):
        c = await owned_conversation(db, conversation_id, user.id, lock=True)
        if c is None:
            raise DomainError(404, "NOT_FOUND", "Không tìm thấy cuộc trò chuyện.")
        if not await previous_receipt(db, user, f"ai:rename:{c.id}", key, payload):
            # The message version is a send precondition, so a rename leaves it unchanged.
            c.title = body.title
            save_receipt(db, user, f"ai:rename:{c.id}", key, payload, {"resourceId": str(c.id)})
        return conversation_header(c)


@router.get("/ai/conversations/{conversation_id}/export")
async def export_conversation(
    conversation_id: UUID, request: Request, actor: Actor = Depends(require_actor)
):
    EXPORT_LIMIT.check(str(actor.user_id))
    async with transaction(request, actor) as (db, user):
        c = await owned_conversation(db, conversation_id, user.id)
        if c is None:
            raise DomainError(404, "NOT_FOUND", "Không tìm thấy cuộc trò chuyện.")
        rows = (
            await db.scalars(
                select(AiMessageRecord)
                .where(AiMessageRecord.conversation_id == c.id)
                .order_by(AiMessageRecord.sequence)
                .limit(10001)
            )
        ).all()
        if len(rows) > 10000:
            raise DomainError(503, "EXPORT_TOO_LARGE", "Cuộc trò chuyện quá dài để tải xuống một lần. Ứng dụng chưa hỗ trợ tải xuống từng phần.")
        result = conversation_header(c).model_dump(mode="json", by_alias=True)
        result["messages"] = [
            AIMessage(
                id=m.id, actor=m.actor, text=m.text, cards=m.cards, created_at=m.created_at
            ).model_dump(mode="json", by_alias=True)
            for m in rows
        ]
    return JSONResponse(
        result,
        headers={"Content-Disposition": 'attachment; filename="moodprint-conversation.json"'},
    )


@router.delete("/ai/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: UUID, request: Request, actor: Actor = Depends(require_actor)
):
    await _end(conversation_id, request, actor, erase=True)


@router.post("/ai/conversations/{conversation_id}/end", status_code=204)
async def end(conversation_id: UUID, request: Request, actor: Actor = Depends(require_actor)):
    # Legacy "end session": stops the turn and frees this worker's copy. Only an
    # explicit DELETE removes a saved transcript.
    await _end(conversation_id, request, actor, erase=False)


async def _end(conversation_id: UUID, request: Request, actor: Actor, *, erase: bool):
    runtime = request.app.state.ai
    async with transaction(request, actor) as (db, user):
        c = await owned_conversation(db, conversation_id, user.id, lock=True)
        if c:
            await db.execute(
                update(AiRun)
                .where(AiRun.conversation_id == c.id, AiRun.status == "running")
                .values(status="cancelled", version=2)
            )
            if erase:
                await db.execute(delete(AiConversation).where(AiConversation.id == c.id))
        else:
            runtime.store.get(conversation_id, str(user.id), str(actor.session_id))
    for run in list(runtime.runs.values()):
        if run.conversation_id == conversation_id and not run.terminal:
            await runtime.stop(run)
    runtime.store.conversations.pop(conversation_id, None)
