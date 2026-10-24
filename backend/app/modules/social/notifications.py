"""ID-only durable watermarks. Message text is fetched through live-policy HTTP reads."""

import asyncio
import json
import time
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

from app.core.errors import DomainError
from app.core.security import Actor, require_actor
from app.core.streams import StreamSlots
from app.modules.social import service as svc

router = APIRouter()


STREAM_SLOTS = StreamSlots(4)
STREAM_LIFETIME_SECONDS = 1800


async def event_stream(request: Request, actor: Actor, connection_id: UUID, after_seq: int = 0):
    previous = None
    heartbeat = 0
    deadline = time.monotonic() + STREAM_LIFETIME_SECONDS
    # EventSource reconnects with Last-Event-ID semantics handled by the HTTP cursor.
    while time.monotonic() < deadline:
        try:
            peer_id = await svc.room_peer(request, actor, connection_id)
            async with svc.pair_transaction(request, actor, peer_id, lock=False) as (
                db,
                user,
                peer,
            ):
                room = await svc.live_room(db, user, peer, connection_id, lock=False)
                if after_seq > room.next_seq:
                    raise DomainError(409, "CURSOR_GAP", "Hãy tải lại cuộc trò chuyện.")
                snapshot = (room.next_seq, room.version)
                envelope = {
                    "version": "social-events-v1",
                    "eventId": f"{room.id}:{room.next_seq}:{room.version}",
                    "connectionId": str(room.id),
                    "highWaterSeq": str(room.next_seq),
                    "roomVersion": room.version,
                    "type": "messages_available",
                }
        except DomainError:
            yield "event: access_revoked\ndata: {}\n\n"
            return
        if snapshot != previous:
            previous = snapshot
            yield f"id: {envelope['eventId']}\nevent: messages_available\ndata: {json.dumps(envelope)}\n\n"
        elif heartbeat >= 10:
            heartbeat = 0
            yield ": heartbeat\n\n"
        heartbeat += 1
        await asyncio.sleep(1)


@router.get("/connections/{connection_id}/events", response_class=StreamingResponse)
async def events(
    connection_id: UUID,
    request: Request,
    after_seq: str = Query("0", alias="afterSeq", pattern=r"^\d{1,19}$"),
    actor: Actor = Depends(require_actor),
):
    release = STREAM_SLOTS.reserve(actor.user_id)
    try:
        peer_id = await svc.room_peer(request, actor, connection_id)
        async with svc.pair_transaction(request, actor, peer_id, lock=False) as (db, user, peer):
            room = await svc.live_room(db, user, peer, connection_id, lock=False)
            if int(after_seq) > room.next_seq:
                raise DomainError(409, "CURSOR_GAP", "Hãy tải lại cuộc trò chuyện.")
    except BaseException:
        release()
        raise

    async def stream():
        try:
            async for chunk in event_stream(request, actor, connection_id, int(after_seq)):
                yield chunk
        finally:
            release()

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        background=BackgroundTask(release),
    )
