import asyncio
from contextlib import ExitStack
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.ai.runtime import LiveRun
from app.ai.schemas import (
    AIRunAccepted,
    ConversationHeader,
    ConversationInput,
    ConversationView,
    MemoryDTO,
    MemoryEdit,
    ProposalConfirm,
    StartRunInput,
)
from app.contracts import ActionReceipt, BotPublicDTO, VersionInput
from app.core.errors import DomainError
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
from app.infrastructure.database.models import AiRun, Memory, PrivateItem

router = APIRouter()


def header(c):
    return ConversationHeader(
        conversation_id=c.id, bot_id=c.bot_id, version=c.version, expires_at=c.expires_at
    )


@router.get("/bots", response_model=list[BotPublicDTO])
async def bots():
    from app.ai.registry import BOTS

    return BOTS


@router.get("/ai/conversations", response_model=list[ConversationHeader])
async def conversations(request: Request, actor: Actor = Depends(require_actor)):
    async with transaction(request, actor) as (db, user):
        await assert_purpose(db, user, "AI")
    store = request.app.state.ai.store
    store.sweep()
    return [
        header(c)
        for c in store.conversations.values()
        if c.user_id == str(actor.user_id) and c.session_id == str(actor.session_id)
    ]


@router.post("/ai/conversations", response_model=ConversationHeader, status_code=201)
async def create_conversation(
    body: ConversationInput, request: Request, actor: Actor = Depends(require_actor)
):
    idempotency_key(request)
    runtime = request.app.state.ai
    runtime.sweep()
    async with transaction(request, actor) as (db, user):
        await assert_purpose(db, user, "AI")
        if not runtime.available:
            raise DomainError(503, "AI_UNAVAILABLE", "Trò chuyện AI chưa sẵn sàng.", True)
    c = runtime.store.create(str(actor.user_id), str(actor.session_id), body.bot_id)
    return header(c)


@router.get("/ai/conversations/{conversation_id}", response_model=ConversationView)
async def conversation(
    conversation_id: UUID, request: Request, actor: Actor = Depends(require_actor)
):
    runtime = request.app.state.ai
    c = runtime.store.get(conversation_id, str(actor.user_id), str(actor.session_id))
    async with transaction(request, actor) as (db, user):
        await assert_purpose(db, user, "AI")
    run = runtime.runs.get(c.active_run_id)
    return ConversationView(
        **header(c).model_dump(),
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
    runtime = request.app.state.ai
    with ExitStack() as input_buffer:
        async with transaction(request, actor) as (db, user):
            await assert_purpose(db, user, "AI")
            if not runtime.available:
                raise DomainError(503, "AI_UNAVAILABLE", "Trò chuyện AI chưa sẵn sàng.", True)
            c = runtime.store.get(conversation_id, str(actor.user_id), str(actor.session_id))
            message_digest = digest(body.model_dump_json(include={"text", "mood_scope"}))
            previous = c.client_runs.get(str(body.client_message_id))
            if previous:
                if previous[0] != message_digest:
                    raise DomainError(
                        409, "IDEMPOTENCY_CONFLICT", "Mã tin nhắn đã được dùng với nội dung khác."
                    )
                return AIRunAccepted(
                    run_id=previous[1],
                    conversation_id=c.id,
                    version=c.version,
                    events_url=f"/api/v1/ai/runs/{previous[1]}/events",
                )
            if body.mood_scope is not None:
                from app.modules.mood.service import validate_scope

                if c.bot_id != "nhip":
                    raise DomainError(422, "MOOD_SCOPE_BOT", "Khoảng ngày chỉ dùng với Nhịp.")
                validate_scope(user, body.mood_scope)
            if c.active_run_id:
                raise DomainError(409, "RUN_IN_PROGRESS", "Đang có một lượt trò chuyện chưa kết thúc.")
            if c.version != body.expected_conversation_version:
                raise DomainError(
                    409, "STALE_VERSION", "Cuộc trò chuyện đã thay đổi. Vui lòng tải lại."
                )
            if (
                sum(not r.terminal and r.actor.user_id == actor.user_id for r in runtime.runs.values())
                >= 2
            ):
                raise DomainError(429, "RUN_LIMIT", "Bạn đang có quá nhiều lượt trò chuyện.")
            run_id = uuid4()
            db.add(AiRun(id=run_id, user_id=user.id, conversation_id=c.id, bot_id=c.bot_id))
            await db.flush()
            data_version = user.data_version
            input_buffer.enter_context(runtime.reserve_input(c.id, len(body.text.encode()) + 1024))
        from app.ai.schemas import AIMessage

        c.messages.append(AIMessage(id=uuid4(), actor="self", text=body.text))
        c.version += 1
        c.active_run_id = run_id
        c.client_runs[str(body.client_message_id)] = (message_digest, run_id)
        run = LiveRun(actor, c.id, data_version, run_id, mood_scope=body.mood_scope)
        runtime.runs[run_id] = run
        runtime.event(run, "progress", {})
        run.task = asyncio.create_task(runtime.drive(run))
        return AIRunAccepted(
            run_id=run_id,
            conversation_id=c.id,
            version=c.version,
            events_url=f"/api/v1/ai/runs/{run_id}/events",
        )


async def authorized_run(request: Request, actor: Actor, run_id: UUID):
    runtime = request.app.state.ai
    run = runtime.runs.get(run_id)
    if (
        run is None
        or run.actor.user_id != actor.user_id
        or run.actor.session_id != actor.session_id
    ):
        raise DomainError(404, "NOT_FOUND", "Không tìm thấy lượt trò chuyện.")
    runtime.store.get(run.conversation_id, str(actor.user_id), str(actor.session_id))
    async with transaction(request, actor) as (db, user):
        await assert_purpose(db, user, "AI")
        if user.data_version != run.data_version:
            raise DomainError(410, "CONTEXT_CHANGED", "Quyền hoặc dữ liệu đã thay đổi.")
    return run


@router.get("/ai/runs/{run_id}/events", response_class=StreamingResponse)
async def events(
    run_id: UUID,
    request: Request,
    after_seq: int = Query(default=0, alias="afterSeq", ge=0),
    actor: Actor = Depends(require_actor),
):
    run = await authorized_run(request, actor, run_id)
    last = request.headers.get("Last-Event-ID")
    if last:
        try:
            after_seq = max(after_seq, int(last))
        except ValueError as exc:
            raise DomainError(422, "INVALID_CURSOR", "Mốc hội thoại chưa hợp lệ.") from exc
    if after_seq > len(run.events):
        raise DomainError(409, "CURSOR_GAP", "Hãy tải lại cuộc trò chuyện.")

    async def stream():
        cursor = after_seq
        while True:
            try:
                await require_actor(request)
                await authorized_run(request, actor, run_id)
            except DomainError:
                yield "event: revoked\ndata: {}\n\n"
                return
            while cursor < len(run.events):
                event = run.events[cursor]
                cursor += 1
                yield f"id: {event.seq}\nevent: {event.type}\ndata: {event.model_dump_json(by_alias=True)}\n\n"
            if run.terminal:
                return
            run.wake.clear()
            try:
                await asyncio.wait_for(run.wake.wait(), timeout=1)
            except TimeoutError:
                yield ": heartbeat\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@router.post("/ai/runs/{run_id}/cancel")
async def cancel(
    run_id: UUID, body: VersionInput, request: Request, actor: Actor = Depends(require_actor)
):
    run = await authorized_run(request, actor, run_id)
    if not run.terminal:
        if body.expected_version != run.version:
            raise DomainError(409, "STALE_VERSION", "Lượt trò chuyện đã thay đổi.")
    await request.app.state.ai.stop(run)
    return {"runId": str(run.id), "version": run.version, "status": "ended"}


@router.post("/ai/conversations/{conversation_id}/end", status_code=204)
async def end(conversation_id: UUID, request: Request, actor: Actor = Depends(require_actor)):
    runtime = request.app.state.ai
    c = runtime.store.get(conversation_id, str(actor.user_id), str(actor.session_id))
    if c.active_run_id:
        run = runtime.runs.get(c.active_run_id)
        if run:
            await runtime.stop(run)
    runtime.store.conversations.pop(c.id, None)


@router.get("/memories", response_model=list[MemoryDTO])
async def memories(request: Request, actor: Actor = Depends(require_actor)):
    async with transaction(request, actor) as (db, user):
        result = [
            MemoryDTO.model_validate(r)
            for r in (
                await db.scalars(
                    select(Memory).where(Memory.user_id == user.id, Memory.status == "active")
                )
            ).all()
        ]
    return result


@router.get("/proposals")
async def proposals(request: Request, actor: Actor = Depends(require_actor)):
    runtime = request.app.state.ai
    async with transaction(request, actor) as (db, user):
        await assert_purpose(db, user, "AI")
        version = user.data_version
    return [
        {
            "id": str(p.id),
            "text": p.text,
            "botId": p.bot_id,
            "purpose": p.purpose,
            "version": p.version,
        }
        for p in runtime.proposals.values()
        if p.user_id == actor.user_id
        and p.session_id == actor.session_id
        and p.expires_at > __import__("time").monotonic()
        and p.data_version == version
    ]


@router.post("/proposals/{proposal_id}/confirm", response_model=ActionReceipt)
async def confirm(
    proposal_id: UUID,
    body: ProposalConfirm,
    request: Request,
    actor: Actor = Depends(require_actor),
):
    import time

    key, payload = idempotency_key(request), body.model_dump(mode="json")
    runtime = request.app.state.ai
    async with transaction(request, actor) as (db, user):
        await assert_purpose(db, user, "AI")
        old = await previous_receipt(db, user, f"proposal:{proposal_id}", key, payload)
        if old:
            return ActionReceipt.model_validate(old)
        p = runtime.proposals.get(proposal_id)
        if not p or p.user_id != actor.user_id or p.session_id != actor.session_id:
            raise DomainError(404, "NOT_FOUND", "Không tìm thấy đề xuất.")
        if p.expires_at <= time.monotonic():
            raise DomainError(410, "PROPOSAL_EXPIRED", "Đề xuất đã hết hạn.")
        if p.version != body.expected_version or p.data_version != user.data_version:
            raise DomainError(409, "STALE_VERSION", "Đề xuất hoặc quyền đã thay đổi.")
        text = body.edited_text or p.text
        record: Memory | PrivateItem
        if p.purpose == "memory":
            await assert_purpose(db, user, "MEM")
            record = Memory(user_id=user.id, bot_id=p.bot_id, text=text, proposal_id=p.id)
        else:
            record = PrivateItem(user_id=user.id, text=text, origin="ai")
        db.add(record)
        await db.flush()
        receipt = ActionReceipt(
            action_id=uuid4(), resource_id=str(record.id), resource_version=record.version
        )
        save_receipt(
            db,
            user,
            f"proposal:{proposal_id}",
            key,
            payload,
            receipt.model_dump(mode="json", by_alias=True),
        )
        user.data_version += 1
    runtime.invalidate(str(actor.user_id))
    return receipt


@router.patch("/memories/{memory_id}", response_model=MemoryDTO)
async def edit_memory(
    memory_id: UUID, body: MemoryEdit, request: Request, actor: Actor = Depends(require_actor)
):
    key, payload = idempotency_key(request), body.model_dump(mode="json")
    async with transaction(request, actor) as (db, user):
        item = await db.scalar(
            select(Memory).where(
                Memory.id == memory_id, Memory.user_id == user.id, Memory.status == "active"
            )
        )
        if item is None:
            raise DomainError(404, "NOT_FOUND", "Không tìm thấy mục ghi nhớ.")
        old = await previous_receipt(db, user, f"memory:{memory_id}", key, payload)
        if not old:
            if item.version != body.expected_version:
                raise DomainError(409, "STALE_VERSION", "Mục ghi nhớ đã thay đổi.")
            item.text, item.version = body.text, item.version + 1
            user.data_version += 1
            save_receipt(
                db,
                user,
                f"memory:{memory_id}",
                key,
                payload,
                {"resourceId": str(item.id), "version": item.version},
            )
        result = MemoryDTO.model_validate(item)
    request.app.state.ai.invalidate(str(actor.user_id))
    return result


@router.post("/proposals/{proposal_id}/reject", response_model=ActionReceipt)
async def reject_proposal(
    proposal_id: UUID, body: VersionInput, request: Request, actor: Actor = Depends(require_actor)
):
    key, payload = idempotency_key(request), body.model_dump(mode="json")
    runtime = request.app.state.ai
    async with transaction(request, actor) as (db, user):
        old = await previous_receipt(db, user, f"proposal:reject:{proposal_id}", key, payload)
        if old:
            return ActionReceipt.model_validate(old)
        proposal = runtime.proposals.get(proposal_id)
        if not proposal or proposal.user_id != user.id or proposal.session_id != actor.session_id:
            raise DomainError(404, "NOT_FOUND", "Không tìm thấy đề xuất.")
        if proposal.version != body.expected_version:
            raise DomainError(409, "STALE_VERSION", "Đề xuất đã thay đổi.")
        result = ActionReceipt(
            action_id=uuid4(), resource_id=str(proposal_id), resource_version=proposal.version + 1
        )
        save_receipt(
            db,
            user,
            f"proposal:reject:{proposal_id}",
            key,
            payload,
            result.model_dump(mode="json", by_alias=True),
        )
    runtime.proposals.pop(proposal_id, None)
    return result


@router.delete("/memories/{memory_id}", response_model=ActionReceipt)
async def delete_memory(
    memory_id: UUID, body: VersionInput, request: Request, actor: Actor = Depends(require_actor)
):
    key, payload = idempotency_key(request), body.model_dump(mode="json")
    async with transaction(request, actor) as (db, user):
        item = await db.scalar(
            select(Memory).where(Memory.id == memory_id, Memory.user_id == user.id)
        )
        if item is None:
            raise DomainError(404, "NOT_FOUND", "Không tìm thấy mục ghi nhớ.")
        old = await previous_receipt(db, user, f"memory:delete:{memory_id}", key, payload)
        if old:
            return ActionReceipt.model_validate(old)
        if item.version != body.expected_version:
            raise DomainError(409, "STALE_VERSION", "Mục ghi nhớ đã thay đổi.")
        item.text, item.status, item.version = "", "deleted", item.version + 1
        user.data_version += 1
        receipt = ActionReceipt(
            action_id=uuid4(), resource_id=str(item.id), resource_version=item.version
        )
        save_receipt(
            db,
            user,
            f"memory:delete:{memory_id}",
            key,
            payload,
            receipt.model_dump(mode="json", by_alias=True),
        )
    request.app.state.ai.invalidate(str(actor.user_id))
    return receipt
