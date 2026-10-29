from fastapi import APIRouter, Depends, Request
from sqlalchemy import select

from app.contracts import ConsentInput, Purpose, SessionView
from app.core.errors import DomainError
from app.core.security import (
    Actor,
    idempotency_key,
    previous_receipt,
    require_actor,
    save_receipt,
    transaction,
)
from app.infrastructure.database.models import Consent, ConsentEvent, now
from app.modules.auth.routes import session_view
from app.modules.guests.policy import require_registered_user
from app.modules.social.service import invalidate_user_social

router = APIRouter()


@router.put("/consents/{purpose}", response_model=SessionView)
async def update_consent(
    purpose: Purpose, body: ConsentInput, request: Request, actor: Actor = Depends(require_actor)
):
    key = idempotency_key(request)
    async with transaction(request, actor) as (db, user):
        if purpose == "MATCH" and body.enabled:
            # Fabricated adult/consent rows can never make a guest a social participant;
            # withdrawing MATCH stays possible and creates nothing.
            require_registered_user(user)
        if purpose == "MATCH" and body.enabled and user.age_band != "adult":
            raise DomainError(
                403,
                "ADULT_REQUIRED",
                "Tìm bạn và nhắn tin người thật dành cho người đã đủ 18 tuổi.",
            )
        old = await previous_receipt(
            db, user, f"consent:{purpose}", key, body.model_dump(mode="json")
        )
        consent = await db.scalar(
            select(Consent).where(Consent.user_id == user.id, Consent.purpose == purpose)
        )
        if not old:
            if consent is None or consent.version != body.expected_version:
                raise DomainError(409, "STALE_VERSION", "Quyền đã thay đổi. Vui lòng tải lại.")
            consent.enabled, consent.policy_version = body.enabled, body.policy_version
            consent.version += 1
            user.data_version += 1
            if purpose == "MATCH":
                await invalidate_user_social(db, user.id)
            if purpose in ("AI", "MEM"):
                from app.ai.embeddings import discard_user_index
                from app.ai.models import AiPreference

                # Old vectors are bound to the previous consent versions either way.
                await discard_user_index(db, user.id)
                if not body.enabled:
                    preference = await db.get(AiPreference, user.id)
                    if preference and preference.semantic_memory_enabled:
                        # A later contextual AI/MEM grant must not resume Voyage.
                        preference.semantic_memory_enabled = False
                        preference.version += 1
                        preference.updated_at = now()
                    from app.ai.memory import withdraw_proposals

                    await withdraw_proposals(db, user.id, purpose)
            db.add(
                ConsentEvent(
                    user_id=user.id,
                    purpose=purpose,
                    enabled=body.enabled,
                    version=consent.version,
                    policy_version=body.policy_version,
                )
            )
            save_receipt(
                db,
                user,
                f"consent:{purpose}",
                key,
                body.model_dump(mode="json"),
                {"version": consent.version},
            )
    request.app.state.ai.invalidate(str(actor.user_id))
    return await session_view(request, actor)
