"""The producer owns a run; disconnecting its SSE observer never cancels it."""

import asyncio
from collections.abc import AsyncIterator
from uuid import uuid4

from moodprint_shared.contracts.conversations import RunUsage, TurnResult
from moodprint_shared.contracts.streaming import StreamEvent, make_event

from app.agent_gateway.wiring import build_context
from app.modules.conversations.approvals import ApprovalService
from app.modules.roleplay.service import RoleplayService


class RunStream:
    def __init__(self):
        self.queue: asyncio.Queue[StreamEvent | None] = asyncio.Queue(maxsize=256)
        self.attached = True

    def publish(self, event: StreamEvent | None):
        if not self.attached:
            return
        if self.queue.full():
            # A slow observer can recover the persisted transcript through GET messages.
            self.attached = False
            while not self.queue.empty():
                self.queue.get_nowait()
            self.queue.put_nowait(None)
            return
        self.queue.put_nowait(event)

    async def bytes(self) -> AsyncIterator[str]:
        try:
            while True:
                event = await self.queue.get()
                if event is None:
                    break
                yield f"event: {event.event}\nid: {event.seq}\ndata: {event.model_dump_json(by_alias=True)}\n\n"
        finally:
            self.attached = False


async def drop_unanswered_duplicate(session, content: str) -> None:
    """A failed or cancelled attempt leaves its user message as the last item of the model's history.
    Re-running the same text must not show the model the same message twice. Best effort only."""
    try:
        items = await session.get_items(limit=1)
        last = items[-1] if items else None
        if isinstance(last, dict) and last.get("role") == "user":
            body = last.get("content")
            text = (
                body
                if isinstance(body, str)
                else " ".join(str(part.get("text", "")) for part in body if isinstance(part, dict))
                if isinstance(body, list)
                else ""
            )
            if text.strip() == content.strip():
                await session.pop_item()
    except Exception:  # never let history hygiene break a turn
        return


async def produce(
    *,
    stream: RunStream,
    runtime,
    service,
    auth,
    turn,
    request_id: str,
    content: str,
    resume=None,
    knowledge=None,
    storage=None,
    analysis=None,
):
    usage = RunUsage()
    answer, answer_id, status, error_code, seq = "", uuid4(), "failed", "internal_error", 0
    citations, structured = [], None
    buffered = []
    try:
        conversation = await service.get(auth, turn.conversation_id)
        ctx = await build_context(
            service.engine,
            service.cfg,
            auth,
            conversation,
            turn.run_id,
            request_id,
            content,
            knowledge,
            storage,
            analysis,
        )
        prior = [] if resume else await service.recent_user_messages(auth, turn.conversation_id)
        session = await service.open_session(
            auth, turn.conversation_id, client=getattr(runtime, "openai_client", None)
        )
        if not resume:
            await drop_unanswered_duplicate(session, content)
        events = (
            runtime.resume_after_approval(
                ctx=ctx,
                serialized_state=resume["run_state"],
                approved=resume["approved"],
                tool_call_id=resume["tool_call_id"],
                session=session,
            )
            if resume
            else runtime.stream_turn(
                ctx=ctx,
                user_input=content,
                session=session,
                message_id=answer_id,
                prior_user_messages=prior,
            )
        )
        async for event in events:
            seq = event.seq
            if event.event == "message.completed":
                answer, answer_id = event.data.content, event.data.message_id
                citations, structured = event.data.citations, event.data.structured
                if (
                    ctx.mode == "roleplay"
                    and structured is not None
                    and structured.urgency == "immediate"
                ):
                    # The role ended because of a danger signal: keep the session out of role.
                    await RoleplayService(service.engine, service.cfg).lock_for_safety(
                        auth, turn.conversation_id
                    )
            elif event.event == "message.delta":
                answer += event.data.text
            elif event.event == "run.usage":
                usage = event.data
                if buffered:
                    await ApprovalService(service.engine).save(
                        auth, runtime.pending_approvals(turn.run_id)
                    )
                    for waiting in buffered:
                        stream.publish(waiting)
                    buffered.clear()
            elif event.event == "approval.required":
                buffered.append(event)
                continue
            elif event.event == "heartbeat":
                await service.heartbeat(auth, turn.run_id)
            elif event.event == "run.failed":
                error_code = event.data.code
                await service.finish_turn(
                    auth, turn, TurnResult(status="failed", usage=usage, error_code=error_code)
                )
            elif event.event == "run.completed":
                status, error_code = event.data.status, None
                await service.finish_turn(
                    auth,
                    turn,
                    TurnResult(
                        status=status,
                        content=answer,
                        message_id=answer_id,
                        citations=citations,
                        structured=structured,
                        usage=usage,
                    ),
                )
            stream.publish(event)
    except asyncio.CancelledError:
        await service.finish_turn(
            auth, turn, TurnResult(status="interrupted", usage=usage, error_code="internal_error")
        )
        raise
    except Exception:
        await service.finish_turn(
            auth, turn, TurnResult(status="failed", usage=usage, error_code="internal_error")
        )
        stream.publish(
            make_event(
                "run.failed",
                seq=seq + 1,
                run_id=turn.run_id,
                data={
                    "code": "internal_error",
                    "message": "Chưa thể hoàn tất lượt trò chuyện. Vui lòng thử lại.",
                    "retryable": True,
                },
            )
        )
    finally:
        stream.publish(None)
