"""Voluntary feedback endpoints for eligible live visitors (guest or registered)."""

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeout

from app.core.errors import DomainError
from app.core.security import Actor, idempotency_key, lock_actor, require_actor, transaction
from app.modules.feedback.policy import feedback_open
from app.modules.feedback.schemas import FeedbackInput, FeedbackReceipt, FeedbackSubmissionState
from app.modules.feedback.service import reserve_attempt, submission_state, submit_feedback


async def collection_open(request: Request) -> None:
    """The endpoints do not exist while collection is off (or cannot be rate limited)."""
    if not feedback_open(request.app.state.settings):
        raise DomainError(404, "NOT_FOUND", "Không tìm thấy nội dung.")


router = APIRouter(dependencies=[Depends(collection_open)])


@router.post("/feedback", response_model=FeedbackReceipt, status_code=201)
async def create_feedback(
    body: FeedbackInput,
    request: Request,
    response: Response,
    actor: Actor = Depends(require_actor),
):
    key = idempotency_key(request)
    try:
        async with request.app.state.database.require()() as db, db.begin():
            await reserve_attempt(db, request, actor.user_id)
        async with transaction(request, actor) as (db, user):
            receipt, created = await submit_feedback(
                db,
                user,
                body,
                key,
                request=request,
                app_version=request.app.state.settings.release_version,
            )
    except (OperationalError, PoolTimeout):
        raise DomainError(
            503, "FEEDBACK_UNAVAILABLE", "Chưa thể gửi góp ý. Vui lòng thử lại.", True
        ) from None
    if not created:
        response.status_code = 200
    return receipt


@router.get("/feedback/submission-state", response_model=FeedbackSubmissionState)
async def get_submission_state(request: Request, actor: Actor = Depends(require_actor)):
    try:
        async with request.app.state.database.require()() as db:
            user = await lock_actor(db, actor, lock=False)
            return await submission_state(db, user)
    except (OperationalError, PoolTimeout):
        raise DomainError(
            503, "FEEDBACK_UNAVAILABLE", "Chưa thể tải góp ý. Vui lòng thử lại.", True
        ) from None
