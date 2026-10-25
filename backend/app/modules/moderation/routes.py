import hmac
import secrets
from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, or_, select, update

from app.contracts import ActionReceipt, EmptyInput, VersionInput
from app.core.errors import DomainError
from app.core.security import (
    Actor,
    idempotency_key,
    previous_receipt,
    require_actor,
    save_receipt,
    transaction,
)
from app.infrastructure.database.models import now
from app.modules.moderation.models import IdentityField, Report, RevealAccess
from app.modules.moderation.schemas import (
    IdentityEdit,
    IdentityView,
    PeerReferenceView,
    ReportInput,
    ReportView,
    RevealDecision,
    RevealInput,
    RevealView,
)
from app.modules.social import service as svc
from app.modules.social.models import CandidateReference, Connection, HumanMessage

router = APIRouter()

REPORTS_PER_DAY = 5


@router.post("/connections/{connection_id}/peer-reference", response_model=PeerReferenceView)
async def peer_reference(
    connection_id: UUID, body: EmptyInput, request: Request, actor: Actor = Depends(require_actor)
):
    peer_id = await svc.room_peer(request, actor, connection_id)
    key, payload = idempotency_key(request), {"connectionId": str(connection_id)}
    async with svc.pair_transaction(request, actor, peer_id) as (db, user, peer):
        old = await previous_receipt(db, user, "safety:reference", key, payload)
        if old:
            return PeerReferenceView(peer_ref=UUID(old["resourceId"]))
        # This reference identifies a known interaction, not permission to view peer content.
        ref = CandidateReference(
            user_id=user.id,
            peer_id=peer.id,
            profile_version=0,
            peer_profile_version=0,
            consent_version=0,
            peer_consent_version=0,
            expires_at=now() + timedelta(minutes=15),
        )
        db.add(ref)
        await db.flush()
        save_receipt(db, user, "safety:reference", key, payload, {"resourceId": str(ref.id)})
        return PeerReferenceView(peer_ref=ref.id)


def reveal_view(row, actor_id, identity=None):
    owner = row.owner_id == actor_id
    return RevealView(
        id=row.id,
        field=row.field,
        owner_side="self" if owner else "peer",
        status=row.status,
        version=row.version,
        identity_version=row.identity_version,
        expires_at=row.expires_at,
        preview_value=identity.value
        if owner and identity and identity.version == row.identity_version
        else None,
        preview_digest=row.preview_digest
        if owner and identity and identity.version == row.identity_version
        else None,
    )


@router.get("/users/me/identity", response_model=list[IdentityView])
async def own_identity(request: Request, actor: Actor = Depends(require_actor)):
    async with transaction(request, actor) as (db, user):
        return [
            IdentityView.model_validate(item)
            for item in (
                await db.scalars(select(IdentityField).where(IdentityField.user_id == user.id))
            ).all()
        ]


@router.patch("/users/me/identity", response_model=IdentityView)
async def edit_identity(
    body: IdentityEdit, request: Request, actor: Actor = Depends(require_actor)
):
    key, payload = idempotency_key(request), body.model_dump(mode="json")
    async with transaction(request, actor) as (db, user):
        old = await previous_receipt(db, user, f"identity:{body.field}", key, payload)
        identity = await db.get(IdentityField, (user.id, body.field))
        if not old:
            if (identity.version if identity else 0) != body.expected_version:
                raise DomainError(409, "STALE_VERSION", "Thông tin đã thay đổi.")
            if identity:
                identity.value, identity.version = body.value.strip(), identity.version + 1
            else:
                identity = IdentityField(
                    user_id=user.id, field=body.field, value=body.value.strip()
                )
                db.add(identity)
            await db.execute(
                update(RevealAccess)
                .where(
                    RevealAccess.owner_id == user.id,
                    RevealAccess.field == body.field,
                    RevealAccess.status.in_(["granted", "pending"]),
                )
                .values(status="revoked", version=RevealAccess.version + 1)
            )
            await db.flush()
            save_receipt(
                db, user, f"identity:{body.field}", key, payload, {"version": identity.version}
            )
        return IdentityView.model_validate(identity)


@router.post(
    "/connections/{connection_id}/reveal-requests", response_model=RevealView, status_code=201
)
async def request_reveal(
    connection_id: UUID, body: RevealInput, request: Request, actor: Actor = Depends(require_actor)
):
    peer_id = await svc.room_peer(request, actor, connection_id)
    key, payload = idempotency_key(request), body.model_dump(mode="json")
    async with svc.pair_transaction(request, actor, peer_id) as (db, user, peer):
        await svc.live_room(db, user, peer, connection_id)
        owner, recipient = (user.id, peer.id) if body.owner_side == "self" else (peer.id, user.id)
        identity = await db.get(IdentityField, (owner, body.field))
        if identity is None:
            raise DomainError(
                409, "IDENTITY_UNAVAILABLE", "Người này chưa sẵn sàng chia sẻ thông tin đó."
            )
        old = await previous_receipt(db, user, f"reveal:create:{connection_id}", key, payload)
        if old:
            row = await db.get(RevealAccess, UUID(old["resourceId"]))
        else:
            if body.expected_identity_version not in (0, identity.version):
                raise DomainError(409, "IDENTITY_CHANGED", "Thông tin đã thay đổi.")
            previous = (
                await db.scalars(
                    select(RevealAccess)
                    .where(
                        RevealAccess.connection_id == connection_id,
                        RevealAccess.owner_id == owner,
                        RevealAccess.recipient_id == recipient,
                        RevealAccess.field == body.field,
                    )
                    .order_by(RevealAccess.expires_at.desc())
                )
            ).first()
            if previous and previous.cooldown_until and previous.cooldown_until > now():
                raise DomainError(
                    429, "REVEAL_COOLDOWN", "Hãy để người kia có thêm thời gian trước khi hỏi lại."
                )
            if (
                previous
                and previous.status in ("pending", "granted")
                and (previous.status == "granted" or previous.expires_at > now())
                and previous.identity_version == identity.version
            ):
                row = previous
            else:
                row = RevealAccess(
                    connection_id=connection_id,
                    owner_id=owner,
                    recipient_id=recipient,
                    field=body.field,
                    identity_version=identity.version,
                    preview_digest=secrets.token_urlsafe(24),
                    expires_at=now() + timedelta(days=7),
                )
                db.add(row)
                await db.flush()
            save_receipt(
                db,
                user,
                f"reveal:create:{connection_id}",
                key,
                payload,
                {"resourceId": str(row.id)},
            )
        return reveal_view(row, user.id, identity)


@router.get("/connections/{connection_id}/reveal-requests", response_model=list[RevealView])
async def list_reveals(
    connection_id: UUID, request: Request, actor: Actor = Depends(require_actor)
):
    peer_id = await svc.room_peer(request, actor, connection_id)
    # Polled read: live-policy checks without row locks.
    async with svc.pair_transaction(request, actor, peer_id, lock=False) as (db, user, peer):
        await svc.live_room(db, user, peer, connection_id, lock=False)
        rows = (
            await db.scalars(
                select(RevealAccess).where(
                    RevealAccess.connection_id == connection_id,
                    or_(RevealAccess.owner_id == user.id, RevealAccess.recipient_id == user.id),
                )
            )
        ).all()
        result = []
        for row in rows:
            identity = (
                await db.get(IdentityField, (row.owner_id, row.field))
                if row.owner_id == user.id
                else None
            )
            item = reveal_view(row, user.id, identity)
            if row.status == "pending" and row.expires_at <= now():
                item.status = "expired"
            result.append(item)
        return result


async def find_reveal(request, actor, identity):
    async with request.app.state.database.require()() as db:
        row = await db.get(RevealAccess, identity)
        if not row or actor.user_id not in (row.owner_id, row.recipient_id):
            svc.missing()
        peer_id = row.recipient_id if row.owner_id == actor.user_id else row.owner_id
        return row.connection_id, peer_id


@router.post("/reveal-requests/{reveal_id}/grant", response_model=RevealView)
async def grant(
    reveal_id: UUID, body: RevealDecision, request: Request, actor: Actor = Depends(require_actor)
):
    connection_id, peer_id = await find_reveal(request, actor, reveal_id)
    key, payload = idempotency_key(request), body.model_dump(mode="json")
    async with svc.pair_transaction(request, actor, peer_id) as (db, user, peer):
        await svc.live_room(db, user, peer, connection_id)
        row = await db.get(RevealAccess, reveal_id)
        if row.owner_id != user.id:
            raise DomainError(403, "OWNER_REQUIRED", "Chỉ chủ thông tin mới có thể đồng ý chia sẻ.")
        identity = await db.get(IdentityField, (user.id, row.field))
        old = await previous_receipt(db, user, f"reveal:grant:{reveal_id}", key, payload)
        if not old:
            if (
                not identity
                or identity.version != row.identity_version
                or row.version != body.expected_version
                or row.status != "pending"
                or row.expires_at <= now()
                or not hmac.compare_digest(row.preview_digest, body.preview_digest)
            ):
                raise DomainError(409, "REVEAL_CHANGED", "Yêu cầu hoặc bản xem trước đã thay đổi.")
            row.status, row.version = "granted", row.version + 1
            save_receipt(
                db, user, f"reveal:grant:{reveal_id}", key, payload, {"resourceId": str(row.id)}
            )
        if row.status != "granted" or not identity or identity.version != row.identity_version:
            svc.deny()
        return reveal_view(row, user.id, identity)


@router.post("/reveal-requests/{reveal_id}/decline", response_model=ActionReceipt)
async def decline(
    reveal_id: UUID, body: VersionInput, request: Request, actor: Actor = Depends(require_actor)
):
    _, peer_id = await find_reveal(request, actor, reveal_id)
    key, payload = idempotency_key(request), body.model_dump(mode="json")
    async with svc.pair_transaction(request, actor, peer_id) as (db, user, peer):
        row = await db.get(RevealAccess, reveal_id)
        if row.owner_id != user.id:
            svc.deny("OWNER_REQUIRED")
        old = await previous_receipt(db, user, f"reveal:decline:{reveal_id}", key, payload)
        if old:
            return ActionReceipt.model_validate(old)
        if row.version != body.expected_version or row.status != "pending":
            raise DomainError(409, "REVEAL_CHANGED", "Yêu cầu đã thay đổi.")
        row.status, row.version, row.cooldown_until = (
            "declined",
            row.version + 1,
            now() + timedelta(days=7),
        )
        result = svc.receipt(row.id, row.version)
        save_receipt(
            db,
            user,
            f"reveal:decline:{reveal_id}",
            key,
            payload,
            result.model_dump(mode="json", by_alias=True),
        )
        return result


@router.get("/reveal-grants/{reveal_id}/value", response_model=IdentityView)
async def revealed_value(reveal_id: UUID, request: Request, actor: Actor = Depends(require_actor)):
    connection_id, peer_id = await find_reveal(request, actor, reveal_id)
    async with svc.pair_transaction(request, actor, peer_id) as (db, user, peer):
        await svc.live_room(db, user, peer, connection_id)
        row = await db.get(RevealAccess, reveal_id)
        identity = await db.get(IdentityField, (row.owner_id, row.field))
        if (
            row.recipient_id != user.id
            or row.status != "granted"
            or not identity
            or identity.version != row.identity_version
        ):
            svc.deny("REVEAL_UNAVAILABLE")
        return IdentityView.model_validate(identity)


@router.delete("/reveal-grants/{reveal_id}", response_model=ActionReceipt)
async def revoke(
    reveal_id: UUID, body: VersionInput, request: Request, actor: Actor = Depends(require_actor)
):
    _, peer_id = await find_reveal(request, actor, reveal_id)
    key, payload = idempotency_key(request), body.model_dump(mode="json")
    async with svc.pair_transaction(request, actor, peer_id) as (db, user, peer):
        row = await db.get(RevealAccess, reveal_id)
        if row.owner_id != user.id:
            svc.missing()
        old = await previous_receipt(db, user, f"reveal:revoke:{reveal_id}", key, payload)
        if old:
            return ActionReceipt.model_validate(old)
        if row.version != body.expected_version:
            raise DomainError(409, "REVEAL_CHANGED", "Quyền chia sẻ đã thay đổi.")
        row.status, row.version = "revoked", row.version + 1
        result = svc.receipt(row.id, row.version)
        save_receipt(
            db,
            user,
            f"reveal:revoke:{reveal_id}",
            key,
            payload,
            result.model_dump(mode="json", by_alias=True),
        )
        return result


async def activity_evidence(db, reporter_id, subject_id, rooms, body) -> list[dict]:
    """Copy the subject's revealed activity answers, so later retention cannot erase them."""
    from app.modules.activities import content
    from app.modules.activities.models import ActivityResponse, ActivitySession

    copied = []
    for ref in {(item.session_id, item.round) for item in body.selected_activity_responses}:
        session = await db.get(ActivitySession, ref[0])
        theirs = await db.get(ActivityResponse, (ref[0], subject_id, ref[1]))
        mine = await db.get(ActivityResponse, (ref[0], reporter_id, ref[1]))
        # Only an answer this reporter could see: same pair, both answered, not skipped.
        if (
            session is None
            or session.connection_id not in [room.id for room in rooms]
            or theirs is None
            or theirs.skipped
            or mine is None
            or mine.skipped
        ):
            raise DomainError(
                403, "EVIDENCE_DENIED", "Không thể dùng câu trả lời này làm bằng chứng."
            )
        item = content.item_by_id(session.content.get("bank", ""), theirs.item_id)
        label = item["options"][theirs.choice] if theirs.choice is not None else None
        copied.append(
            {
                "kind": "activity",
                "sessionId": str(session.id),
                "round": theirs.round,
                "activity": session.kind,
                "prompt": item["prompt"],
                "text": " · ".join(part for part in (label, theirs.text) if part),
            }
        )
    return copied


@router.post("/reports", response_model=ReportView, status_code=201)
async def report(body: ReportInput, request: Request, actor: Actor = Depends(require_actor)):
    key, payload = idempotency_key(request), body.model_dump(mode="json")
    async with request.app.state.database.require()() as db:
        ref = await db.get(CandidateReference, body.peer_ref)
        if not ref or ref.user_id != actor.user_id:
            svc.missing()
        peer_id, expired = ref.peer_id, ref.expires_at <= now()
    async with svc.pair_transaction(request, actor, peer_id) as (db, user, peer):
        old = await previous_receipt(db, user, "report:create", key, payload)
        if old:
            return ReportView.model_validate(await db.get(Report, UUID(old["resourceId"])))
        if expired:
            raise DomainError(
                410, "REFERENCE_EXPIRED", "Phiên báo cáo đã hết hạn. Vui lòng thử lại."
            )
        recent = await db.scalar(
            select(func.count()).where(
                Report.reporter_id == user.id, Report.created_at > now() - timedelta(days=1)
            )
        )
        if recent >= REPORTS_PER_DAY:
            raise DomainError(
                429, "REPORT_QUOTA", "Bạn đã gửi nhiều báo cáo hôm nay. Hãy thử lại sau.", True
            )
        rooms = (
            await db.scalars(
                select(Connection).where(
                    or_(
                        (Connection.low_user_id == user.id) & (Connection.high_user_id == peer.id),
                        (Connection.low_user_id == peer.id) & (Connection.high_user_id == user.id),
                    )
                )
            )
        ).all()
        if not rooms:
            raise DomainError(
                403, "INTERACTION_REQUIRED", "Chỉ có thể báo cáo một kết nối đã có tương tác."
            )
        evidence = []
        for identity in set(body.selected_message_ids):
            message = await db.get(HumanMessage, identity)
            if (
                not message
                or message.connection_id not in [room.id for room in rooms]
                or message.created_at <= now() - timedelta(days=90)
            ):
                raise DomainError(
                    403, "EVIDENCE_DENIED", "Không thể dùng tin nhắn này làm bằng chứng."
                )
            # Evidence must come from this pair's own rooms, but the room need not be
            # live: abuse is often reported right after blocking or ending a connection.
            evidence.append({"messageId": str(message.id), "text": message.text})
        evidence += await activity_evidence(db, user.id, peer.id, rooms, body)
        latest = max(rooms, key=lambda room: room.created_at)
        row = Report(
            reporter_id=user.id,
            subject_id=peer.id,
            reason=body.reason,
            evidence=evidence,
            connection_id=latest.id,
        )
        db.add(row)
        await db.flush()
        save_receipt(db, user, "report:create", key, payload, {"resourceId": str(row.id)})
        return ReportView.model_validate(row)


@router.get("/reports/{report_id}", response_model=ReportView)
async def report_status(report_id: UUID, request: Request, actor: Actor = Depends(require_actor)):
    async with transaction(request, actor) as (db, user):
        row = await db.get(Report, report_id)
        if not row or row.reporter_id != user.id:
            svc.missing()
        return ReportView.model_validate(row)
