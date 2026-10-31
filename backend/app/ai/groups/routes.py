"""AI group API (06 §3): registered adults only, owner-scoped, behind AI_GROUP_CHAT_ENABLED."""

import asyncio
from datetime import timedelta
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, func, select, update
from starlette.background import BackgroundTask

from app.ai.collaboration.eligibility import collaboration_eligible
from app.ai.context import TEXT_POLICY, ContextStamp
from app.ai.groups.events import MAX_EVENTS, group_events
from app.ai.groups.mentions import resolve
from app.ai.groups.schemas import (
    AgentId,
    GroupCreate,
    GroupHeader,
    GroupJournalAccess,
    GroupMemberAdd,
    GroupMessageInput,
    GroupReadInput,
    GroupRename,
    GroupTurnAccepted,
    GroupView,
)
from app.ai.groups.service import (
    MAX_GROUPS,
    active,
    group_view,
    header,
    members_of,
    not_found,
    owned_group,
    unread,
)
from app.ai.models import AiConversation, AiMessageRecord, AiTurn
from app.ai.orchestration.models import AiGroupMember, AiOrchestrationStep
from app.ai.persistence import admission, load_runtime_conversation, recover_turns
from app.core.errors import DomainError
from app.core.security import (
    Actor,
    assert_purpose,
    digest,
    idempotency_key,
    previous_receipt,
    require_registered_actor,
    save_receipt,
    transaction,
)
from app.infrastructure.database.models import AiRun, now

router = APIRouter()
BASE = "/ai/groups"


async def group_actor(request: Request, actor: Actor = Depends(require_registered_actor)) -> Actor:
    # Hidden while the flag (or cohort) is off: nothing to discover.
    if not request.app.state.settings.groups_open_for(actor.user_id):
        raise not_found()
    return actor


async def _eligible(db, user) -> None:
    await assert_purpose(db, user, "AI")
    if not await collaboration_eligible(db, user):
        raise DomainError(403, "ADULT_REQUIRED", "Nhóm trợ lý chỉ dành cho tài khoản đủ 18 tuổi.")


def _stale() -> DomainError:
    return DomainError(409, "STALE_VERSION", "Nhóm vừa thay đổi. Mình đã tải lại để bạn xem.")


async def _stop_turns(request: Request, db, group_id: UUID) -> list[UUID]:
    """Cancel the group's running turn (membership/permission change, deletion)."""
    ids = (await db.scalars(select(AiRun.id).where(AiRun.conversation_id == group_id, AiRun.status == "running"))).all()
    if ids:
        await db.execute(update(AiRun).where(AiRun.id.in_(ids), AiRun.status == "running")
                         .values(status="cancelled", version=2))
        await db.execute(update(AiRun).where(AiRun.parent_run_id.in_(ids), AiRun.status == "running")
                         .values(status="cancelled", version=2))
    return list(ids)


async def _stop_local(request: Request, run_ids: list[UUID]) -> None:
    runtime = request.app.state.ai
    for run_id in run_ids:
        local = runtime.runs.get(run_id)
        if local is not None and not local.terminal:
            await runtime.stop(local)


@router.get(BASE, response_model=list[GroupHeader])
async def list_groups(request: Request, actor: Actor = Depends(group_actor)):
    async with transaction(request, actor, lock=False) as (db, user):
        groups = (await db.scalars(
            select(AiConversation).where(
                AiConversation.user_id == user.id, AiConversation.kind == "group", AiConversation.expires_at > now(),
            ).order_by(AiConversation.updated_at.desc(), AiConversation.id.desc()).limit(MAX_GROUPS)
        )).all()
        return [header(group, await members_of(db, group), await unread(db, group)) for group in groups]


@router.post(BASE, response_model=GroupView, status_code=201)
async def create_group(body: GroupCreate, request: Request, actor: Actor = Depends(group_actor)):
    settings = request.app.state.settings
    key, payload = idempotency_key(request), body.model_dump(mode="json")
    async with transaction(request, actor) as (db, user):
        await _eligible(db, user)
        old = await previous_receipt(db, user, "ai:group:create", key, payload)
        if old:
            return await group_view(db, await owned_group(db, UUID(old["resourceId"]), user.id))
        saved = await db.scalar(select(func.count()).select_from(AiConversation).where(
            AiConversation.user_id == user.id, AiConversation.expires_at > now()))
        if (saved or 0) >= 500:
            raise DomainError(429, "CONVERSATION_LIMIT", "Hãy xóa bớt hội thoại đã lưu trước khi tạo thêm.")
        group = AiConversation(user_id=user.id, bot_id="group", kind="group", title=body.name,
                               expires_at=now() + timedelta(days=min(settings.chat_retention_days, 30)))
        db.add(group)
        await db.flush()
        for bot in body.members:
            db.add(AiGroupMember(conversation_id=group.id, bot_id=bot, user_id=user.id))
        await db.flush()
        save_receipt(db, user, "ai:group:create", key, payload, {"resourceId": str(group.id)})
        return await group_view(db, group)


@router.get(BASE + "/{group_id}", response_model=GroupView)
async def read_group(group_id: UUID, request: Request, limit: int = Query(50, ge=1, le=100),
                     before: UUID | None = None, actor: Actor = Depends(group_actor)):
    async with transaction(request, actor) as (db, user):
        await recover_turns(db)
        return await group_view(db, await owned_group(db, group_id, user.id), limit, before)


@router.patch(BASE + "/{group_id}", response_model=GroupView)
async def rename_group(group_id: UUID, body: GroupRename, request: Request, actor: Actor = Depends(group_actor)):
    key, payload = idempotency_key(request), body.model_dump(mode="json")
    async with transaction(request, actor) as (db, user):
        group = await owned_group(db, group_id, user.id, lock=True)
        if not await previous_receipt(db, user, f"ai:group:rename:{group.id}", key, payload):
            if body.expected_version != group.version:
                raise _stale()
            group.title = body.name  # never sent to a model
            save_receipt(db, user, f"ai:group:rename:{group.id}", key, payload, {"resourceId": str(group.id)})
        return await group_view(db, group)


@router.post(BASE + "/{group_id}/members", response_model=GroupView)
async def add_member(group_id: UUID, body: GroupMemberAdd, request: Request, actor: Actor = Depends(group_actor)):
    key, payload = idempotency_key(request), body.model_dump(mode="json")
    async with transaction(request, actor) as (db, user):
        await _eligible(db, user)
        group = await owned_group(db, group_id, user.id, lock=True)
        if await previous_receipt(db, user, f"ai:group:add:{group.id}", key, payload):
            return await group_view(db, group)
        if body.expected_version != group.version:
            raise _stale()
        members = await members_of(db, group)
        if body.bot_id in active(members):
            raise DomainError(409, "ALREADY_MEMBER", "Trợ lý này đã ở trong nhóm.")
        if len(active(members)) >= 3:
            raise DomainError(409, "GROUP_FULL", "Nhóm đã đủ ba trợ lý.")
        # Default: the new member sees only what is said from now on (06 §6).
        start = 0 if body.share_history else group.version + 1
        row = next((m for m in members if m.bot_id == body.bot_id), None)
        if row is None:
            db.add(AiGroupMember(conversation_id=group.id, bot_id=body.bot_id, user_id=user.id,
                                 history_from_sequence=start))
        else:
            row.status, row.removed_at, row.journal_access = "active", None, False
            row.history_from_sequence, row.version, row.joined_at = start, row.version + 1, now()
        await db.flush()
        save_receipt(db, user, f"ai:group:add:{group.id}", key, payload, {"resourceId": str(group.id)})
        return await group_view(db, group)


@router.delete(BASE + "/{group_id}/members/{bot_id}", response_model=GroupView)
async def remove_member(group_id: UUID, bot_id: AgentId, request: Request,
                        expected_version: int = Query(alias="expectedVersion", ge=1),
                        actor: Actor = Depends(group_actor)):
    async with transaction(request, actor) as (db, user):
        group = await owned_group(db, group_id, user.id, lock=True)
        members = await members_of(db, group)
        row = next((m for m in members if m.bot_id == bot_id and m.status == "active"), None)
        if row is None:
            raise not_found()
        if expected_version != group.version:
            raise _stale()
        if len(active(members)) <= 2:
            raise DomainError(409, "GROUP_MIN_MEMBERS", "Nhóm cần ít nhất hai trợ lý.")
        row.status, row.removed_at, row.journal_access, row.version = "removed", now(), False, row.version + 1
        stopped = await _stop_turns(request, db, group.id)
        await db.flush()
        result = await group_view(db, group)
    await _stop_local(request, stopped)
    return result


@router.put(BASE + "/{group_id}/members/{bot_id}/journal-access", response_model=GroupView)
async def journal_access(group_id: UUID, bot_id: AgentId, body: GroupJournalAccess, request: Request,
                         actor: Actor = Depends(group_actor)):
    if bot_id != "nhatky":
        raise DomainError(422, "JOURNAL_MEMBER_ONLY", "Chỉ Nhật ký mới có thể dùng nhật ký của bạn.")
    key, payload = idempotency_key(request), body.model_dump(mode="json")
    stopped: list[UUID] = []
    async with transaction(request, actor) as (db, user):
        await _eligible(db, user)
        group = await owned_group(db, group_id, user.id, lock=True)
        if not await previous_receipt(db, user, f"ai:group:journal:{group.id}", key, payload):
            if body.expected_version != group.version:
                raise _stale()
            row = await db.get(AiGroupMember, (group.id, bot_id))
            if row is None or row.status != "active":
                raise not_found()
            if row.journal_access and not body.enabled:
                # Revocation reaches an in-flight turn at once.
                stopped = await _stop_turns(request, db, group.id)
            row.journal_access, row.version = body.enabled, row.version + 1
            save_receipt(db, user, f"ai:group:journal:{group.id}", key, payload, {"resourceId": str(group.id)})
        await db.flush()
        result = await group_view(db, group)
    await _stop_local(request, stopped)
    return result


@router.delete(BASE + "/{group_id}", status_code=204)
async def delete_group(group_id: UUID, request: Request, actor: Actor = Depends(group_actor)):
    async with transaction(request, actor) as (db, user):
        group = await owned_group(db, group_id, user.id, lock=True)
        stopped = await _stop_turns(request, db, group.id)
        await db.execute(delete(AiConversation).where(AiConversation.id == group.id))
    await _stop_local(request, stopped)
    request.app.state.ai.store.conversations.pop(group_id, None)


@router.post(BASE + "/{group_id}/read", status_code=204)
async def read_group_messages(group_id: UUID, body: GroupReadInput, request: Request,
                              actor: Actor = Depends(group_actor)):
    from sqlalchemy.dialects.postgresql import insert

    from app.ai.proactive.models import AiConversationRead

    async with transaction(request, actor) as (db, user):
        group = await owned_group(db, group_id, user.id)
        sequence = min(body.sequence, group.version)
        statement = insert(AiConversationRead).values(conversation_id=group.id, user_id=user.id,
                                                      last_read_sequence=sequence, updated_at=now())
        await db.execute(statement.on_conflict_do_update(
            index_elements=[AiConversationRead.conversation_id],
            set_={"last_read_sequence": func.greatest(AiConversationRead.last_read_sequence, sequence),
                  "updated_at": now()},
            where=AiConversationRead.user_id == user.id,
        ))


@router.post(BASE + "/{group_id}/messages", response_model=GroupTurnAccepted, status_code=202)
async def send_group_message(group_id: UUID, body: GroupMessageInput, request: Request,
                             actor: Actor = Depends(group_actor)):
    from app.ai.accounting import reserve_accounting
    from app.ai.groups.turn import GROUP_PROMPT_VERSION, GroupTurn
    from app.ai.runtime import LiveRun

    idempotency_key(request)
    runtime, settings = request.app.state.ai, request.app.state.settings
    async with transaction(request, actor) as (db, user):
        await _eligible(db, user)
        group = await owned_group(db, group_id, user.id, lock=True)
        message_digest = digest(body.model_dump_json(include={"text", "mentions"}))
        previous = await db.scalar(select(AiTurn).where(
            AiTurn.scope_id == group.id, AiTurn.client_message_id == body.client_message_id, AiTurn.user_id == user.id))
        if previous:
            if previous.input_digest != message_digest:
                raise DomainError(409, "IDEMPOTENCY_CONFLICT", "Mã tin nhắn đã được dùng với nội dung khác.")
            return GroupTurnAccepted(turn_id=previous.run_id, group_id=group.id, version=group.version,
                                     events_url=f"/api/v1/ai/groups/{group.id}/turns/{previous.run_id}/events")
        if not runtime.available_for(actor.user_id):
            raise DomainError(503, "AI_UNAVAILABLE", "Trò chuyện AI chưa sẵn sàng.", True)
        if not settings.chat_history_enabled:
            raise DomainError(403, "HISTORY_UNAVAILABLE", "Lưu lịch sử chưa sẵn sàng.")
        members = active(await members_of(db, group))
        picked = [agent for agent in body.mentions if agent != "all"]
        if any(agent not in members for agent in picked):
            raise DomainError(422, "MENTION_NOT_MEMBER", "Trợ lý bạn nhắc tên không ở trong nhóm này.")
        mentions, everyone = resolve(body.text, list(body.mentions))
        mentions = tuple(agent for agent in mentions if agent in members)  # text mentions of non-members: ignored
        if await db.scalar(select(AiRun.id).where(AiRun.conversation_id == group.id, AiRun.status == "running")):
            raise DomainError(409, "RUN_IN_PROGRESS", "Nhóm đang trả lời tin trước.")
        if group.version != body.expected_version:
            raise _stale()
        await admission(db, user, settings)
        run_id, message_id = uuid4(), uuid4()
        db.add(AiRun(id=run_id, user_id=user.id, conversation_id=group.id, bot_id="group"))
        await db.flush()
        db.add(AiTurn(
            run_id=run_id, user_id=user.id, scope_id=group.id, conversation_id=group.id,
            session_id=actor.session_id, client_message_id=body.client_message_id, input_digest=message_digest,
            data_version=user.data_version, context_policy=TEXT_POLICY, worker_id=runtime.worker_id,
            lease_until=now() + timedelta(seconds=2 * settings.ai_timeout_seconds + 15),
        ))
        if settings.ai_accounting_enabled:
            await reserve_accounting(db, run_id, user.id, runtime.worker_id, settings.openai_model,
                                     f"group-turn+{GROUP_PROMPT_VERSION}")
        group.version += 1
        group.updated_at = now()
        db.add(AiMessageRecord(id=message_id, conversation_id=group.id, sequence=group.version, actor="self",
                               text=body.text, cards=[], run_id=run_id,
                               mentions=[*mentions, *(["all"] if everyone else [])][:4]))
        await db.flush()
        conversation = await load_runtime_conversation(db, group, actor.session_id)
        data_version, version = user.data_version, group.version
    conversation.context_stamps[run_id] = ContextStamp(data_version, TEXT_POLICY)
    conversation.active_run_id = run_id
    runtime.store.conversations[group.id] = conversation
    runtime.store.touch(conversation)
    run = LiveRun(actor, group.id, data_version, run_id, persistent=True, kind="group")
    runtime.runs[run_id] = run
    turn = GroupTurn(runtime, run, mentions=mentions, everyone=everyone, text=body.text)
    run.task = asyncio.create_task(turn.drive())
    return GroupTurnAccepted(turn_id=run_id, group_id=group.id, version=version,
                             events_url=f"/api/v1/ai/groups/{group.id}/turns/{run_id}/events")


async def _turn_state(request: Request, actor: Actor, group_id: UUID, turn_id: UUID, *, poll: bool):
    async with transaction(request, actor, lock=not poll) as (db, user):
        await assert_purpose(db, user, "AI")
        group = await owned_group(db, group_id, user.id)
        turn = await db.scalar(select(AiRun).where(AiRun.id == turn_id, AiRun.user_id == user.id,
                                                   AiRun.conversation_id == group.id, AiRun.origin == "user"))
        if turn is None:
            raise DomainError(404, "NOT_FOUND", "Không tìm thấy lượt trò chuyện.")
        steps = (await db.scalars(select(AiOrchestrationStep).where(
            AiOrchestrationStep.workflow_run_id == turn.id, AiOrchestrationStep.user_id == user.id,
        ))).all()
        children = [step.child_run_id for step in steps if step.kind == "group_reply" and step.child_run_id]
        bubbles: dict = {}
        if children:
            for message in (await db.scalars(select(AiMessageRecord).where(
                AiMessageRecord.conversation_id == group.id, AiMessageRecord.run_id.in_(children),
            ).order_by(AiMessageRecord.sequence))).all():
                bubbles.setdefault(message.run_id, []).append(message)
        return group_events(turn, steps, bubbles)


@router.get(BASE + "/{group_id}/turns/{turn_id}/events", response_class=StreamingResponse)
async def group_turn_events(group_id: UUID, turn_id: UUID, request: Request,
                            after_seq: int = Query(0, alias="afterSeq", ge=0), actor: Actor = Depends(group_actor)):
    from app.modules.guests.output import REVOKED_EVENT

    runtime = request.app.state.ai
    release = runtime.streams.reserve(actor.user_id)
    try:
        await _turn_state(request, actor, group_id, turn_id, poll=False)
        last = request.headers.get("Last-Event-ID")
        if last:
            try:
                after_seq = max(after_seq, int(last))
            except ValueError as exc:
                raise DomainError(422, "INVALID_CURSOR", "Mốc hội thoại chưa hợp lệ.") from exc
        if after_seq > MAX_EVENTS:
            raise DomainError(409, "CURSOR_GAP", "Hãy tải lại nhóm.")
    except BaseException:
        release()
        raise

    async def stream():
        cursor = after_seq
        try:
            while not await request.is_disconnected():
                try:
                    events = await _turn_state(request, actor, group_id, turn_id, poll=True)
                except DomainError:
                    yield REVOKED_EVENT.decode()
                    return
                while cursor < len(events):
                    event = events[cursor]
                    cursor += 1
                    yield f"id: {event.seq}\nevent: {event.type}\ndata: {event.model_dump_json(by_alias=True)}\n\n"
                if events[-1].type in ("turn_completed", "turn_failed", "turn_cancelled"):
                    return
                await asyncio.sleep(0.25)
                yield ": heartbeat\n\n"
        finally:
            release()

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
                             background=BackgroundTask(release))


@router.post(BASE + "/{group_id}/turns/{turn_id}/cancel", status_code=204)
async def cancel_group_turn(group_id: UUID, turn_id: UUID, request: Request, actor: Actor = Depends(group_actor)):
    async with transaction(request, actor) as (db, user):
        group = await owned_group(db, group_id, user.id)
        turn = await db.scalar(select(AiRun).where(AiRun.id == turn_id, AiRun.conversation_id == group.id,
                                                   AiRun.user_id == user.id).with_for_update())
        if turn is None:
            raise DomainError(404, "NOT_FOUND", "Không tìm thấy lượt trò chuyện.")
        stopped = await _stop_turns(request, db, group.id) if turn.status == "running" else []
    await _stop_local(request, stopped)

