"""ID-only durable watermarks. Message text is fetched through live-policy HTTP reads."""

import asyncio
import json
import time
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from starlette.background import BackgroundTask

from app.core.errors import DomainError
from app.core.security import Actor, require_registered_actor
from app.core.streams import StreamSlots
from app.modules.social import service as svc
from app.modules.social.models import Connection

router = APIRouter()


STREAM_SLOTS = StreamSlots(4)
STREAM_LIFETIME_SECONDS = 1800
FULL_CHECK_SECONDS = 5


def activity_event(room) -> str:
    envelope = {
        "version": "social-events-v2",
        "eventId": f"{room.id}:a{room.activity_seq}",
        "connectionId": str(room.id),
        "activitySeq": room.activity_seq,
    }
    return f"id: {envelope['eventId']}\nevent: activity_changed\ndata: {json.dumps(envelope)}\n\n"


async def event_stream(request: Request, actor: Actor, connection_id: UUID, after_seq: int = 0):
    previous = None
    previous_activity: int | None = None
    activity = 0
    activity_room = None
    heartbeat = 0
    last_full = 0.0
    deadline = time.monotonic() + STREAM_LIFETIME_SECONDS
    # EventSource reconnects with Last-Event-ID semantics handled by the HTTP cursor.
    while time.monotonic() < deadline:
        try:
            # Cheap per-second watermark. Every room-ending change (end, block, consent
            # withdrawal, account deletion) bumps the room version or status, so it is
            # seen here at once; the full live-policy check runs on any change, before
            # anything is announced, and at least every FULL_CHECK_SECONDS for
            # session/eligibility changes that do not touch the room.
            async with request.app.state.database.require()() as db:
                row = (
                    await db.execute(
                        select(
                            Connection.next_seq,
                            Connection.version,
                            Connection.status,
                            Connection.activity_seq,
                        ).where(Connection.id == connection_id)
                    )
                ).one_or_none()
            if row is None or row.status != "open":
                raise DomainError(403, "CONNECTION_UNAVAILABLE", "Kết nối không còn khả dụng.")
            watermark = (row.next_seq, row.version)
            changed = watermark != previous or row.activity_seq != previous_activity
            if changed or time.monotonic() - last_full >= FULL_CHECK_SECONDS:
                peer_id = await svc.room_peer(request, actor, connection_id)
                async with svc.pair_transaction(request, actor, peer_id, lock=False) as (
                    db,
                    user,
                    peer,
                ):
                    room = await svc.live_room(db, user, peer, connection_id, lock=False)
                    if after_seq > room.next_seq:
                        raise DomainError(409, "CURSOR_GAP", "Hãy tải lại cuộc trò chuyện.")
                    watermark = (room.next_seq, room.version)
                    activity, activity_room = room.activity_seq, room
                    envelope = {
                        "version": "social-events-v1",
                        "eventId": f"{room.id}:{room.next_seq}:{room.version}",
                        "connectionId": str(room.id),
                        "highWaterSeq": str(room.next_seq),
                        "roomVersion": room.version,
                        "type": "messages_available",
                    }
                last_full = time.monotonic()
        except DomainError:
            yield "event: access_revoked\ndata: {}\n\n"
            return
        chunks = []
        if watermark != previous:
            previous = watermark
            chunks.append(
                f"id: {envelope['eventId']}\nevent: messages_available\ndata: {json.dumps(envelope)}\n\n"
            )
        # Announce on connect too: a change between the client's own first fetch and this
        # first poll would otherwise become the baseline and never be announced.
        if (previous_activity is None or activity != previous_activity) and activity_room:
            previous_activity = activity
            chunks.append(activity_event(activity_room))
        if chunks:
            heartbeat = 0
            yield "".join(chunks)
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
    actor: Actor = Depends(require_registered_actor),
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
