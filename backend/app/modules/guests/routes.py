from fastapi import APIRouter, Depends, Request, Response

from app.contracts import EmptyInput, SessionView
from app.core.errors import DomainError
from app.core.security import Actor, idempotency_key, require_actor
from app.modules.guests.availability import experience_view
from app.modules.guests.intents import create_guest_intent
from app.modules.guests.schemas import GuestInput, PublicExperience
from app.modules.guests.service import cleared_response, create_guest, end_guest

router = APIRouter()


@router.get("/public/experience", response_model=PublicExperience)
async def public_experience(request: Request) -> PublicExperience:
    return experience_view(request)


@router.post("/auth/guest-intents", status_code=204)
async def guest_intents(body: EmptyInput, request: Request) -> Response:
    # Coordination cookie only: no provider call and no application identity is created here.
    result = Response(status_code=204)
    await create_guest_intent(request, result)
    return result


@router.post("/auth/guest", response_model=SessionView, status_code=201)
async def guest_create(body: GuestInput, request: Request, response: Response) -> SessionView:
    # 201 for a first grant; 200 for a recovered grant or an already live guest cookie.
    return await create_guest(request, body, response)


async def guest_actor(request: Request) -> Actor:
    """Like require_actor, but a dead or missing session also tells the browser to drop cookies."""
    try:
        return await require_actor(request)
    except DomainError as error:
        if error.status == 401:
            error.clear_session = True
        raise


@router.post("/auth/guest/end", status_code=204)
async def guest_end(
    body: EmptyInput, request: Request, actor: Actor = Depends(guest_actor)
) -> Response:
    idempotency_key(request)
    if actor.account_kind != "guest":
        raise DomainError(403, "GUEST_REQUIRED", "Chỉ lượt dùng thử mới có thể kết thúc bằng thao tác này.")
    await end_guest(request, actor)
    return cleared_response()
