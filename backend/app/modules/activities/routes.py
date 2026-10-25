"""Activity lifecycle API (06 section 8). Every write: CSRF via require_actor, an
Idempotency-Key receipt, live-room authorization and the canonical lock order."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.contracts import ActionReceipt, VersionInput
from app.core.errors import DomainError
from app.core.security import (
    Actor,
    idempotency_key,
    previous_receipt,
    require_actor,
    save_receipt,
)
from app.infrastructure.database.models import now
from app.modules.activities import machine
from app.modules.activities import service as act
from app.modules.activities.definitions import DEFINITIONS, FOCUS_MAX_CYCLES, FOCUS_PLANS
from app.modules.activities.machine import Command, MachineError, NoChange
from app.modules.activities.models import ActivityParticipant, ActivitySession
from app.modules.activities.projection import project
from app.modules.activities.schemas import (
    ActivityDefinitionDTO,
    ActivitySessionView,
    FeedbackInput,
    InviteInput,
    ReadyInput,
    ResponseInput,
)
from app.modules.social import service as svc

router = APIRouter()
LIFECYCLE = ("accept", "decline", "cancel", "end")
FOCUS = ("pause", "resume", "leave", "join")


@router.get("/activities/catalog", response_model=list[ActivityDefinitionDTO])
async def catalog(request: Request, actor: Actor = Depends(require_actor)):
    settings = request.app.state.settings
    if not settings.activities_enabled:
        return []
    return [
        ActivityDefinitionDTO(
            kind=definition.kind,
            definition_version=definition.version,
            title=definition.title,
            description=definition.description,
            estimated_minutes=definition.estimated_minutes,
            rounds=definition.rounds,
            focus_plans=[list(plan) for plan in FOCUS_PLANS]
            if definition.kind == "focus"
            else None,
            max_cycles=FOCUS_MAX_CYCLES if definition.kind == "focus" else None,
        )
        for kind, definition in DEFINITIONS.items()
        if kind in settings.activity_kinds
    ]


@router.post(
    "/connections/{connection_id}/activities",
    response_model=ActivitySessionView,
    status_code=201,
)
async def invite(
    connection_id: UUID, body: InviteInput, request: Request, actor: Actor = Depends(require_actor)
):
    act.require_enabled(request, body.kind)
    key, payload = idempotency_key(request), body.model_dump(mode="json")
    peer_id = await svc.room_peer(request, actor, connection_id)
    async with svc.pair_transaction(request, actor, peer_id) as (db, user, peer):
        room = await svc.live_room(db, user, peer, connection_id)
        operation = f"activity:invite:{room.id}"
        old = await previous_receipt(db, user, operation, key, payload)
        if old:
            row = await db.get(ActivitySession, UUID(old["resourceId"]))
        else:
            at = now()
            current = await act.open_session(db, room.id, lock=True)
            if current is not None:
                raise DomainError(
                    409,
                    "ACTIVITY_IN_PROGRESS",
                    "Hai bạn đang có một hoạt động khác.",
                    current_session_id=str(current.id),
                )
            await act.check_invite_limits(db, user.id, room.id, body.kind, at)
            options: dict[str, Any] = {}
            if body.kind == "focus":
                from app.modules.activities.focus import validate_options

                try:
                    options = validate_options(
                        body.options.model_dump() if body.options else {}
                    )
                except MachineError as error:
                    raise act.refuse(error) from None
            content: dict[str, Any] = {"options": options} if options else {}
            settings = request.app.state.settings
            if (
                body.kind == "focus"
                and settings.app_env == "test"
                and settings.focus_test_plan_seconds
            ):
                content["testSeconds"] = settings.focus_test_plan_seconds
            definition = DEFINITIONS[body.kind]
            row = ActivitySession(
                connection_id=room.id,
                pair_id=room.pair_id,
                kind=body.kind,
                definition_version=definition.version,
                inviter_id=user.id,
                invitee_id=peer.id,
                state="invited",
                phase="invited",
                content=content,
                created_at=at,
                deadline_at=at + definition.invite_ttl,
            )
            db.add(row)
            try:
                await db.flush()
            except IntegrityError:
                raise DomainError(
                    409, "ACTIVITY_IN_PROGRESS", "Hai bạn đang có một hoạt động khác."
                ) from None
            db.add(
                ActivityParticipant(
                    session_id=row.id, user_id=user.id, role="inviter", accepted_at=at
                )
            )
            db.add(ActivityParticipant(session_id=row.id, user_id=peer.id, role="invitee"))
            room.activity_seq += 1
            await db.flush()
            save_receipt(db, user, operation, key, payload, {"resourceId": str(row.id)})
        state, _ = await act.load_state(db, row)
        return project(state, room.id, user.id, now())


@router.get(
    "/connections/{connection_id}/activities/current",
    response_model=ActivitySessionView | None,
)
async def current(connection_id: UUID, request: Request, actor: Actor = Depends(require_actor)):
    peer_id = await svc.room_peer(request, actor, connection_id)
    async with svc.pair_transaction(request, actor, peer_id, lock=False) as (db, user, peer):
        room = await svc.live_room(db, user, peer, connection_id, lock=False)
        at = now()
        row = await act.latest_session(db, room.id, at)
        if row is None:
            return None
        state, _ = await act.load_state(db, row)
        return project(state, room.id, user.id, at)


@router.get("/connections/{connection_id}/activities", response_model=list[ActivitySessionView])
async def history(
    connection_id: UUID,
    request: Request,
    limit: int = Query(10, ge=1, le=20),
    actor: Actor = Depends(require_actor),
):
    peer_id = await svc.room_peer(request, actor, connection_id)
    async with svc.pair_transaction(request, actor, peer_id, lock=False) as (db, user, peer):
        room = await svc.live_room(db, user, peer, connection_id, lock=False)
        rows = (
            await db.scalars(
                select(ActivitySession)
                .where(
                    ActivitySession.connection_id == room.id,
                    ActivitySession.state.in_(machine.TERMINAL),
                )
                .order_by(ActivitySession.created_at.desc())
                .limit(limit)
            )
        ).all()
        at = now()
        return [project((await act.load_state(db, row))[0], room.id, user.id, at) for row in rows]


@router.get("/activities/{session_id}", response_model=ActivitySessionView)
async def get_session(session_id: UUID, request: Request, actor: Actor = Depends(require_actor)):
    async with act.activity_transaction(request, actor, session_id, lock=False) as (
        db,
        user,
        peer,
        room,
        row,
    ):
        state, _ = await act.load_state(db, row)
        return project(state, room.id, user.id, now())


async def run(
    request: Request,
    actor: Actor,
    session_id: UUID,
    command: Command | None,
    operation: str,
    payload: dict[str, Any],
    expected_version: int | None,
    build=None,
):
    """Execute one command; replays and repeats return the current projection."""
    act.require_enabled(request)
    key = idempotency_key(request)
    async with act.activity_transaction(request, actor, session_id) as (db, user, peer, room, row):
        operation = f"activity:{operation}:{session_id}"
        old = await previous_receipt(db, user, operation, key, payload)
        state, rows = await act.load_state(db, row)
        if not old:
            cmd = command if command is not None else build(user.id)
            at = now()
            try:
                after = machine.apply(state, cmd, at)
            except NoChange:
                after = None
            except MachineError as error:
                raise act.refuse(error) from None
            if after is not None:
                # Lifecycle and timer controls compare versions; answers rely on the round.
                if expected_version is not None and row.version != expected_version:
                    raise DomainError(
                        409, "ACTIVITY_CHANGED", MachineError.MESSAGES["ACTIVITY_CHANGED"]
                    )
                state = await act.store(db, row, rows, state, after, room)
            save_receipt(db, user, operation, key, payload, {"resourceId": str(session_id)})
        return project(state, room.id, user.id, now())


def lifecycle_route(op: str):
    async def handler(
        session_id: UUID,
        body: VersionInput,
        request: Request,
        actor: Actor = Depends(require_actor),
    ) -> ActivitySessionView:
        return await run(
            request,
            actor,
            session_id,
            None,
            op,
            body.model_dump(mode="json"),
            body.expected_version,
            build=lambda uid: Command(op, uid),  # type: ignore[arg-type]
        )

    handler.__name__ = f"activity_{op}"
    return handler


for _op in LIFECYCLE:
    router.post(f"/activities/{{session_id}}/{_op}", response_model=ActivitySessionView)(
        lifecycle_route(_op)
    )
for _op in FOCUS:
    router.post(f"/activities/{{session_id}}/focus/{_op}", response_model=ActivitySessionView)(
        lifecycle_route(_op)
    )


@router.post("/activities/{session_id}/responses", response_model=ActivitySessionView)
async def respond(
    session_id: UUID, body: ResponseInput, request: Request, actor: Actor = Depends(require_actor)
):
    payload = body.model_dump(mode="json")
    answer = {"choice": body.choice, "text": body.text, "skipped": body.skipped}
    return await run(
        request,
        actor,
        session_id,
        None,
        f"respond:{body.round}",
        payload,
        None,
        build=lambda uid: Command("respond", uid, body.round, answer),
    )


@router.post("/activities/{session_id}/ready", response_model=ActivitySessionView)
async def ready(
    session_id: UUID, body: ReadyInput, request: Request, actor: Actor = Depends(require_actor)
):
    return await run(
        request,
        actor,
        session_id,
        None,
        f"ready:{body.round}",
        body.model_dump(mode="json"),
        None,
        build=lambda uid: Command("ready", uid, body.round),
    )


@router.post("/activities/{session_id}/feedback", response_model=ActionReceipt)
async def feedback(
    session_id: UUID, body: FeedbackInput, request: Request, actor: Actor = Depends(require_actor)
):
    view = await run(
        request,
        actor,
        session_id,
        None,
        "feedback",
        body.model_dump(mode="json"),
        None,
        build=lambda uid: Command("feedback", uid, payload={"rating": body.rating}),
    )
    return svc.receipt(UUID(view.id), view.version)
