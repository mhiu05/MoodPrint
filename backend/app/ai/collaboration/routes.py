"""Per-edge sharing opt-in (P2-02). Registered adults only; every write locks the account first.

Turning an edge off is always allowed (even with the feature flag off) and takes effect at
once: ``users.data_version`` increments, every running turn of the account is cancelled and
in-memory copies are invalidated, exactly like revoking AI preferences.
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select, update

from app.ai.collaboration.eligibility import collaboration_eligible
from app.ai.collaboration.models import SHARING_POLICY_VERSION, AiSharingPermission
from app.ai.collaboration.policy import EDGES
from app.ai.collaboration.schemas import SharingEdgeView, SharingInput, SharingReason, SharingView
from app.ai.proactive.models import AiProactiveSettings
from app.core.errors import DomainError
from app.core.security import (
    Actor,
    idempotency_key,
    previous_receipt,
    require_registered_actor,
    save_receipt,
    transaction,
)
from app.infrastructure.database.models import AiRun, now

router = APIRouter()


def _specs(settings, user_id):
    """(edge, requester, specialist, kind, reads_journal) of the edges this account manages.

    V3 accounts manage the four Điều phối edges; the Phase 2 edges belong to the legacy
    companions and are listed only while the three-agent experience is off for the account.
    """
    from app.ai.orchestration.policy import EDGES as V3
    from app.ai.orchestration.policy import READS_JOURNAL

    if settings.v3_open_for(user_id):
        return [(edge, "dieuphoi", target, kind, edge in READS_JOURNAL) for (kind, target), edge in V3.items()]
    return [(spec.edge, spec.requester, spec.specialist, "consult", spec.reads_journal) for spec in EDGES.values()]


def _feature_open(settings, user_id) -> bool:
    if settings.v3_open_for(user_id):
        return settings.orchestration_open_for(user_id) and settings.ai_multi_message_enabled
    return settings.collaboration_open_for(user_id) and settings.ai_multi_message_enabled


async def sharing_view(db, settings, user) -> SharingView:
    rows = {
        row.edge: row
        for row in (
            await db.scalars(select(AiSharingPermission).where(AiSharingPermission.user_id == user.id))
        ).all()
    }
    prefs = await db.get(AiProactiveSettings, user.id)
    journal = bool(prefs and prefs.journal_context_enabled)
    open_ = _feature_open(settings, user.id)
    eligible = await collaboration_eligible(db, user)
    edges = []
    for edge, requester, specialist, kind, reads_journal in _specs(settings, user.id):
        row = rows.get(edge)
        reason: SharingReason | None = None
        if not open_:
            reason = "feature_unavailable"
        elif not eligible:
            reason = "ineligible_account"
        elif reads_journal and not journal:
            reason = "journal_context_off"
        edges.append(SharingEdgeView(
            edge=edge, kind=kind, requester=requester, specialist=specialist,  # type: ignore[arg-type]
            enabled=bool(row and row.enabled), version=row.version if row else 0,
            requires=["journal_context"] if reads_journal else [],
            available=reason is None, reason=reason,
        ))
    return SharingView(available=open_ and eligible, edges=edges)


@router.get("/ai/sharing", response_model=SharingView)
async def read_sharing(request: Request, actor: Actor = Depends(require_registered_actor)):
    async with transaction(request, actor, lock=False) as (db, user):
        return await sharing_view(db, request.app.state.settings, user)


@router.put("/ai/sharing/{edge}", response_model=SharingView)
async def update_sharing(
    edge: str, body: SharingInput, request: Request, actor: Actor = Depends(require_registered_actor)
):
    settings = request.app.state.settings
    from app.ai.collaboration.models import EDGE_VALUES

    if edge not in EDGE_VALUES:
        raise DomainError(404, "NOT_FOUND", "Không tìm thấy kiểu phối hợp này.")
    # Switching any edge off is always allowed; switching on only for an edge this account manages.
    managed = {item[0]: item for item in _specs(settings, actor.user_id)}
    reads_journal = bool(managed.get(edge, (None,) * 5)[4])
    key, payload = idempotency_key(request), {"edge": edge, **body.model_dump(mode="json")}
    revoked = False
    async with transaction(request, actor) as (db, user):
        if await previous_receipt(db, user, "ai:sharing", key, payload):
            return await sharing_view(db, settings, user)
        row = await db.scalar(
            select(AiSharingPermission)
            .where(AiSharingPermission.user_id == user.id, AiSharingPermission.edge == edge)
            .with_for_update()
        )
        if (row.version if row else 0) != body.expected_version:
            raise DomainError(409, "STALE_VERSION", "Cài đặt phối hợp vừa thay đổi. Mình đã tải lại để bạn xem.")
        if body.enabled:
            if edge not in managed or not _feature_open(settings, user.id):
                raise DomainError(503, "COLLABORATION_UNAVAILABLE",
                                  "Tính năng phối hợp đang tạm nghỉ. Bạn thử lại sau nhé.", True)
            if not await collaboration_eligible(db, user):
                raise DomainError(403, "ADULT_REQUIRED", "Tính năng này chỉ dành cho tài khoản đủ 18 tuổi.")
            if reads_journal:
                prefs = await db.get(AiProactiveSettings, user.id)
                if not (prefs and prefs.journal_context_enabled):
                    raise DomainError(
                        409, "SHARING_REQUIRES_JOURNAL_CONTEXT",
                        "Hãy bật \"Dùng khoảnh khắc đã lưu hôm qua\" ở Lịch hỏi thăm trước nhé.",
                    )
        changed = bool(row and row.enabled) != body.enabled
        if row is None:
            row = AiSharingPermission(user_id=user.id, edge=edge, enabled=body.enabled, version=1,
                                      policy_version=SHARING_POLICY_VERSION)
            db.add(row)
        elif changed:
            row.enabled, row.version = body.enabled, row.version + 1
            row.policy_version, row.updated_at = SHARING_POLICY_VERSION, now()
        if changed and not body.enabled:
            # Same revocation pattern as AI preferences: nothing derived under the old grant
            # may be used or persisted by any in-flight turn of this account.
            revoked = True
            user.data_version += 1
            await db.execute(
                update(AiRun).where(AiRun.user_id == user.id, AiRun.status == "running")
                .values(status="cancelled", version=2)
            )
        await db.flush()
        save_receipt(db, user, "ai:sharing", key, payload, {"version": row.version})
        result = await sharing_view(db, settings, user)
    if revoked:
        request.app.state.ai.invalidate(str(actor.user_id))
    return result
