import hmac
from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, or_, select, update
from sqlalchemy.dialects.postgresql import insert

from app.contracts import ActionReceipt, EmptyInput, VersionInput
from app.core.errors import DomainError
from app.core.security import (
    Actor,
    assert_purpose,
    idempotency_key,
    previous_receipt,
    require_actor,
    save_receipt,
    transaction,
)
from app.infrastructure.database.models import Consent, User, now
from app.modules.matching import scoring
from app.modules.profiles.taxonomy import TAXONOMY
from app.modules.social import service as svc
from app.modules.social.models import (
    Block,
    CandidateReference,
    Connection,
    ConnectionRead,
    ConnectionRequest,
    HumanMessage,
    MatchingDraft,
    Pair,
    PublishedProfile,
)
from app.modules.social.schemas import (
    BlockInput,
    CandidateCardDTO,
    CandidateInput,
    CandidateListDTO,
    ConnectionView,
    DraftInput,
    DraftView,
    MessageInput,
    MessagePage,
    MessageView,
    PreviewView,
    PublicProfile,
    PublishedView,
    PublishInput,
    ReadInput,
    ReadView,
    RequestView,
)
from app.modules.social.summary import PREVIEW_CHARS, last_messages, unread_by_room, visible_rooms

router = APIRouter()


@router.get("/profiles/matching-draft", response_model=DraftView)
async def get_draft(request: Request, actor: Actor = Depends(require_actor)):
    async with transaction(request, actor) as (db, user):
        draft = await db.get(MatchingDraft, user.id)
        return DraftView(
            profile=PublicProfile.model_validate(draft.payload) if draft else PublicProfile(),
            version=draft.version if draft else 0,
            published_version=user.profile_version,
        )


@router.put("/profiles/matching-draft", response_model=DraftView)
async def save_draft(body: DraftInput, request: Request, actor: Actor = Depends(require_actor)):
    key, payload = idempotency_key(request), body.model_dump(mode="json")
    async with transaction(request, actor) as (db, user):
        old = await previous_receipt(db, user, "draft:save", key, payload)
        draft = await db.get(MatchingDraft, user.id)
        if not old:
            if (draft.version if draft else 0) != body.expected_version:
                raise DomainError(409, "STALE_VERSION", "Bản nháp đã thay đổi.")
            if draft is None:
                draft = MatchingDraft(user_id=user.id, payload=svc.public_payload(body))
                db.add(draft)
            else:
                draft.payload = svc.public_payload(body)
                draft.version += 1
                draft.preview_digest = None
                draft.preview_expires_at = None
            await db.flush()
            save_receipt(db, user, "draft:save", key, payload, {"version": draft.version})
        return DraftView(
            profile=PublicProfile.model_validate(draft.payload),
            version=draft.version,
            published_version=user.profile_version,
        )


@router.get("/profiles/published/current", response_model=PublishedView | None)
async def published_current(request: Request, actor: Actor = Depends(require_actor)):
    async with transaction(request, actor) as (db, user):
        profile = await db.scalar(
            select(PublishedProfile).where(
                PublishedProfile.user_id == user.id, PublishedProfile.valid
            )
        )
        if profile is None:
            return None
        consent = await db.get(Consent, (user.id, "MATCH"))
        live = (
            profile.version == user.profile_version
            and consent is not None
            and consent.enabled
            and profile.consent_version == consent.version
        )
        return PublishedView(
            id=profile.id,
            profile=PublicProfile.model_validate(profile.payload),
            version=profile.version,
            state="live" if live else "needs_republish",
            profile_version=user.profile_version,
        )


@router.post("/profiles/matching-draft/preview", response_model=PreviewView)
async def preview_draft(request: Request, actor: Actor = Depends(require_actor)):
    async with transaction(request, actor) as (db, user):
        draft = await db.get(MatchingDraft, user.id)
        if not draft:
            svc.missing()
        svc.validate_publishable(draft.payload)
        draft.preview_digest = svc.new_preview()
        draft.preview_expires_at = now() + timedelta(minutes=15)
        return PreviewView(
            profile=PublicProfile.model_validate(draft.payload),
            draft_version=draft.version,
            preview_digest=draft.preview_digest,
        )


@router.post("/profiles/published", response_model=PublishedView, status_code=201)
async def publish(body: PublishInput, request: Request, actor: Actor = Depends(require_actor)):
    key, payload = idempotency_key(request), body.model_dump(mode="json")
    async with transaction(request, actor) as (db, user):
        consents = await assert_purpose(db, user, "MATCH")
        old = await previous_receipt(db, user, "profile:publish", key, payload)
        if old:
            profile = await db.get(PublishedProfile, UUID(old["resourceId"]))
            if (
                not profile
                or not profile.valid
                or profile.version != user.profile_version
                or profile.consent_version != consents["MATCH"].version
            ):
                raise DomainError(409, "PROFILE_CHANGED", "Hồ sơ đã thay đổi.")
        else:
            draft = await db.get(MatchingDraft, user.id)
            if (
                not draft
                or draft.version != body.draft_version
                or user.profile_version != body.expected_published_version
                or not draft.preview_digest
                or not draft.preview_expires_at
                or draft.preview_expires_at <= now()
                or not hmac.compare_digest(draft.preview_digest, body.preview_digest)
            ):
                raise DomainError(409, "PREVIEW_CHANGED", "Hãy xem lại bản xem trước mới nhất.")
            svc.validate_publishable(draft.payload)
            # DR-03: a new profile changes discovery only; rooms and requests stay valid.
            await db.execute(
                update(PublishedProfile)
                .where(PublishedProfile.user_id == user.id, PublishedProfile.valid)
                .values(valid=False)
            )
            user.profile_version += 1
            profile = PublishedProfile(
                user_id=user.id,
                payload=draft.payload,
                version=user.profile_version,
                consent_version=consents["MATCH"].version,
                taxonomy_version=TAXONOMY.version,
            )
            db.add(profile)
            await db.flush()
            save_receipt(db, user, "profile:publish", key, payload, {"resourceId": str(profile.id)})
        return PublishedView(
            id=profile.id,
            profile=PublicProfile.model_validate(profile.payload),
            version=profile.version,
            profile_version=user.profile_version,
        )


@router.delete("/profiles/published/current", response_model=ActionReceipt)
async def withdraw(body: VersionInput, request: Request, actor: Actor = Depends(require_actor)):
    key, payload = idempotency_key(request), body.model_dump(mode="json")
    async with transaction(request, actor) as (db, user):
        old = await previous_receipt(db, user, "profile:withdraw", key, payload)
        if old:
            return ActionReceipt.model_validate(old)
        if user.profile_version != body.expected_version:
            raise DomainError(409, "STALE_VERSION", "Hồ sơ đã thay đổi.")
        await db.execute(
            update(PublishedProfile)
            .where(PublishedProfile.user_id == user.id, PublishedProfile.valid)
            .values(valid=False)
        )
        user.profile_version += 1
        result = svc.receipt(user.id, user.profile_version)
        save_receipt(
            db,
            user,
            "profile:withdraw",
            key,
            payload,
            result.model_dump(mode="json", by_alias=True),
        )
        return result


@router.get("/matching/candidates", response_model=CandidateListDTO)
async def candidates(request: Request, actor: Actor = Depends(require_actor)):
    from app.core.security import lock_actor
    from app.modules.social.retrieval import ranked_candidates

    async with request.app.state.database.require()() as db, db.begin():
        user = await db.get(User, actor.user_id)
        own, consent = await svc.current_profile(db, user)
        shortlist = await ranked_candidates(db, user, own, consent)
    # Recheck the shortlisted public snapshots while holding all account gates
    # in canonical order. Never acquire a peer gate after locking the actor first.
    async with request.app.state.database.require()() as db, db.begin():
        rows = (
            await db.scalars(
                select(User)
                .where(User.id.in_([actor.user_id, *shortlist]))
                .order_by(User.id)
                .with_for_update()
            )
        ).all()
        users = {user.id: user for user in rows}
        user = await lock_actor(db, actor)
        own, own_consent = await svc.current_profile(db, user)
        result: list[CandidateCardDTO] = []
        for peer_id in shortlist:
            if len(result) == 5:
                break
            peer = users.get(peer_id)
            if peer is None:
                continue
            try:
                _, published, snapshots = await svc.base_eligibility(
                    db, user, peer, own_snapshot=(own, own_consent)
                )
            except DomainError:
                continue
            low, high = sorted((user.id, peer.id))
            pair = await db.scalar(
                select(Pair).where(Pair.low_user_id == low, Pair.high_user_id == high)
            )
            if pair:
                if pair.cooldown_until and pair.cooldown_until > now():
                    continue
                pending = await db.scalar(
                    select(ConnectionRequest).where(
                        ConnectionRequest.pair_id == pair.id, ConnectionRequest.status == "pending"
                    )
                )
                room = await db.scalar(
                    select(Connection).where(
                        Connection.pair_id == pair.id, Connection.status == "open"
                    )
                )
                # Any live request or open room hides the pair, whatever either profile became.
                if pending and pending.expires_at + timedelta(days=30) > now():
                    continue
                if room:
                    continue
            points = scoring.score(
                scoring.v1_view(own.payload), scoring.v1_view(published.payload)
            )
            if points < 30:
                continue
            ref = CandidateReference(
                user_id=user.id,
                peer_id=peer.id,
                profile_version=own.version,
                peer_profile_version=published.version,
                consent_version=snapshots[str(user.id)]["consent"],
                peer_consent_version=snapshots[str(peer.id)]["consent"],
                expires_at=now() + timedelta(minutes=15),
            )
            db.add(ref)
            await db.flush()
            alias, alias_seed = svc.pair_alias(user.id, peer.id)
            result.append(
                CandidateCardDTO(
                    candidate_ref=ref.id,
                    alias=alias,
                    avatar_seed=alias_seed,
                    profile=PublicProfile.model_validate(published.payload),
                    reasons=svc.reasons(own.payload, published.payload),
                    profile_version=own.version,
                    peer_version=published.version,
                )
            )
        return CandidateListDTO(candidates=result)


@router.post("/matching/skips", response_model=ActionReceipt)
async def skip(body: CandidateInput, request: Request, actor: Actor = Depends(require_actor)):
    ref = await svc.resolve_reference(request, actor, body.candidate_ref)
    key, payload = idempotency_key(request), body.model_dump(mode="json")
    async with svc.pair_transaction(request, actor, ref.peer_id) as (db, user, peer):
        _, _, snapshots = await svc.base_eligibility(db, user, peer)
        svc.check_reference(ref, user, peer, snapshots)
        pair = await svc.canonical_pair(db, user.id, peer.id)
        old = await previous_receipt(db, user, "pair:skip", key, payload)
        if old:
            return ActionReceipt.model_validate(old)
        pair.cooldown_until = now() + timedelta(days=30)
        pair.version += 1
        result = svc.receipt(pair.id, pair.version)
        save_receipt(
            db, user, "pair:skip", key, payload, result.model_dump(mode="json", by_alias=True)
        )
        return result


@router.post("/connection-requests", response_model=RequestView, status_code=201)
async def send_request(
    body: CandidateInput, request: Request, actor: Actor = Depends(require_actor)
):
    ref = await svc.resolve_reference(request, actor, body.candidate_ref)
    key, payload = idempotency_key(request), body.model_dump(mode="json")
    async with svc.pair_transaction(request, actor, ref.peer_id) as (db, user, peer):
        _, _, snapshots = await svc.base_eligibility(db, user, peer)
        svc.check_reference(ref, user, peer, snapshots)
        pair = await svc.canonical_pair(db, user.id, peer.id)
        old = await previous_receipt(db, user, "request:send", key, payload)
        if old:
            pending = await db.get(ConnectionRequest, UUID(old["resourceId"]))
            return svc.request_view(pending, user.id)
        pending, room = await svc.interaction(db, pair, snapshots)
        if room or (pair.cooldown_until and pair.cooldown_until > now()):
            raise DomainError(409, "PAIR_UNAVAILABLE", "Cặp kết nối chưa thể nhận lời mời mới.")
        if pending and pending.sender_id != user.id:
            # Sending back completes the peer's invitation, like accept; no quota applies.
            await svc.open_mutual_room(db, pair, pending, snapshots)
        elif not pending:
            await svc.invitation_quota(db, user.id)
            pending = ConnectionRequest(
                pair_id=pair.id,
                sender_id=user.id,
                recipient_id=peer.id,
                snapshots=snapshots,
                expires_at=now() + timedelta(days=7),
            )
            db.add(pending)
            await db.flush()
        save_receipt(db, user, "request:send", key, payload, {"resourceId": str(pending.id)})
        return svc.request_view(pending, user.id)


@router.get("/connection-requests", response_model=list[RequestView])
async def list_requests(request: Request, actor: Actor = Depends(require_actor)):
    async with transaction(request, actor) as (db, user):
        await assert_purpose(db, user, "MATCH")
        rows = (
            await db.scalars(
                select(ConnectionRequest)
                .where(
                    or_(
                        ConnectionRequest.sender_id == user.id,
                        ConnectionRequest.recipient_id == user.id,
                    )
                )
                .order_by(ConnectionRequest.created_at.desc())
                .limit(100)
            )
        ).all()
        result = []
        for row in rows:
            # Terminal metadata contains no peer identity/content. Pending validity is rechecked on decisions.
            view = svc.request_view(row, user.id)
            if row.status == "pending" and row.expires_at <= now():
                view.status = "expired"
            elif row.status == "pending":
                peer = await db.get(
                    User, row.recipient_id if row.sender_id == user.id else row.sender_id
                )
                view.peer = await svc.peer_card(db, user, peer) if peer else None
            result.append(view)
        return result


async def decide(request_id, decision, body, request, actor):
    async with request.app.state.database.require()() as db:
        initial = await db.get(ConnectionRequest, request_id)
        if not initial or actor.user_id not in (initial.sender_id, initial.recipient_id):
            svc.missing()
        peer_id = initial.recipient_id if initial.sender_id == actor.user_id else initial.sender_id
    key, payload = idempotency_key(request), body.model_dump(mode="json")
    operation = f"request:{decision}:{request_id}"
    async with svc.pair_transaction(request, actor, peer_id) as (db, user, peer):
        gate = svc.consent_view(await svc.room_gate(db, user, peer))
        snapshots = None
        if decision == "accept":
            # Opening a room still needs both published profiles (DR-03 keeps requests
            # alive across edits, but a withdrawn sender cannot be accepted).
            try:
                _, _, snapshots = await svc.base_eligibility(db, user, peer)
            except DomainError as error:
                if error.code not in ("PROFILE_REQUIRED", "PAIR_INELIGIBLE"):
                    raise
        pair = await svc.canonical_pair(db, user.id, peer.id, False)
        row = await db.scalar(
            select(ConnectionRequest).where(ConnectionRequest.id == request_id).with_for_update()
        )
        if (
            decision in ("accept", "decline")
            and row.recipient_id != user.id
            or decision == "cancel"
            and row.sender_id != user.id
        ):
            raise DomainError(403, "WRONG_ACTOR", "Bạn không thể thực hiện lựa chọn này.")
        old = await previous_receipt(db, user, operation, key, payload)
        if old:
            if svc.consent_view(row.snapshots) != gate:
                svc.deny()
            return svc.request_view(row, user.id)
        if (
            row.version != body.expected_version
            or row.status != "pending"
            or row.expires_at <= now()
            or svc.consent_view(row.snapshots) != gate
            or (decision == "accept" and snapshots is None)
        ):
            raise DomainError(409, "REQUEST_CHANGED", "Lời mời đã thay đổi hoặc hết hạn.")
        if decision == "accept" and snapshots is not None:
            await svc.open_mutual_room(db, pair, row, snapshots)
        else:
            row.status = "declined" if decision == "decline" else "cancelled"
            row.version += 1
            pair.cooldown_until = now() + timedelta(days=30)
        save_receipt(db, user, operation, key, payload, {"resourceId": str(row.id)})
        return svc.request_view(row, user.id)


@router.post("/connection-requests/{request_id}/accept", response_model=RequestView)
async def accept(
    request_id: UUID, body: VersionInput, request: Request, actor: Actor = Depends(require_actor)
):
    return await decide(request_id, "accept", body, request, actor)


@router.post("/connection-requests/{request_id}/decline", response_model=RequestView)
async def decline(
    request_id: UUID, body: VersionInput, request: Request, actor: Actor = Depends(require_actor)
):
    return await decide(request_id, "decline", body, request, actor)


@router.post("/connection-requests/{request_id}/cancel", response_model=RequestView)
async def cancel(
    request_id: UUID, body: VersionInput, request: Request, actor: Actor = Depends(require_actor)
):
    return await decide(request_id, "cancel", body, request, actor)


@router.get("/connections", response_model=list[ConnectionView])
async def list_connections(request: Request, actor: Actor = Depends(require_actor)):
    async with transaction(request, actor) as (db, user):
        await assert_purpose(db, user, "MATCH")
        rooms = await visible_rooms(db, user)
        ids = [room.id for room in rooms]
        unread, last = await unread_by_room(db, user.id, ids), await last_messages(db, ids)
        result = []
        for room in rooms:
            view = svc.connection_view(room)
            view.unread_count = unread.get(room.id, 0)
            if message := last.get(room.id):
                view.last_message_at = message.created_at
                view.last_message_preview = message.text[:PREVIEW_CHARS]
                view.last_message_sender = "self" if message.sender_id == user.id else "peer"
            result.append(view)
        result.sort(key=lambda view: view.last_message_at or view.created_at, reverse=True)
        return result


@router.post("/connections/{connection_id}/read", response_model=ReadView)
async def mark_read(
    connection_id: UUID, body: ReadInput, request: Request, actor: Actor = Depends(require_actor)
):
    """Monotonic private read marker; naturally idempotent, so no receipt is stored."""
    peer_id = await svc.room_peer(request, actor, connection_id)
    async with svc.pair_transaction(request, actor, peer_id, lock=False) as (db, user, peer):
        room = await svc.live_room(db, user, peer, connection_id, lock=False)
        statement = insert(ConnectionRead).values(
            connection_id=room.id,
            user_id=user.id,
            last_read_seq=min(int(body.seq), room.next_seq),
            updated_at=now(),
        )
        value = await db.scalar(
            statement.on_conflict_do_update(
                index_elements=[ConnectionRead.connection_id, ConnectionRead.user_id],
                set_={
                    "last_read_seq": func.greatest(
                        ConnectionRead.last_read_seq, statement.excluded.last_read_seq
                    ),
                    "updated_at": now(),
                },
            ).returning(ConnectionRead.last_read_seq)
        )
        return ReadView(last_read_seq=str(value))


@router.get("/connections/{connection_id}", response_model=ConnectionView)
async def get_connection(
    connection_id: UUID, request: Request, actor: Actor = Depends(require_actor)
):
    peer_id = await svc.room_peer(request, actor, connection_id)
    # Polled read: same live-policy checks without row locks that would contend with writers.
    async with svc.pair_transaction(request, actor, peer_id, lock=False) as (db, user, peer):
        room = await svc.live_room(db, user, peer, connection_id, lock=False)
        return svc.connection_view(room)


@router.post("/connections/{connection_id}/messages", response_model=MessageView, status_code=201)
async def send_message(
    connection_id: UUID, body: MessageInput, request: Request, actor: Actor = Depends(require_actor)
):
    peer_id = await svc.room_peer(request, actor, connection_id)
    key, payload = idempotency_key(request), body.model_dump(mode="json")
    async with svc.pair_transaction(request, actor, peer_id) as (db, user, peer):
        room = await svc.live_room(db, user, peer, connection_id)
        operation = f"message:send:{room.id}"
        prior = await previous_receipt(db, user, operation, key, payload)
        if prior:
            persisted = await db.get(HumanMessage, UUID(prior["resourceId"]))
            if not persisted or persisted.created_at <= now() - timedelta(days=90):
                raise DomainError(410, "MESSAGE_EXPIRED", "Tin nhắn không còn khả dụng.")
            return svc.message_view(persisted, user.id)
        old = await db.scalar(
            select(HumanMessage).where(
                HumanMessage.connection_id == room.id,
                HumanMessage.sender_id == user.id,
                HumanMessage.client_message_id == body.client_message_id,
            )
        )
        if old:
            if old.text != body.text:
                raise DomainError(
                    409, "MESSAGE_CONFLICT", "Mã tin nhắn đã được dùng với nội dung khác."
                )
            save_receipt(db, user, operation, key, payload, {"resourceId": str(old.id)})
            return svc.message_view(old, user.id)
        await svc.message_quota(db, user.id)
        room.next_seq += 1
        message = HumanMessage(
            connection_id=room.id,
            sender_id=user.id,
            client_message_id=body.client_message_id,
            text=body.text,
            seq=room.next_seq,
        )
        db.add(message)
        await db.flush()
        save_receipt(db, user, operation, key, payload, {"resourceId": str(message.id)})
        return svc.message_view(message, user.id)


@router.get("/connections/{connection_id}/messages", response_model=MessagePage)
async def get_messages(
    connection_id: UUID,
    request: Request,
    after_seq: str = Query("0", alias="afterSeq", pattern=r"^\d{1,19}$"),
    actor: Actor = Depends(require_actor),
):
    peer_id = await svc.room_peer(request, actor, connection_id)
    # A message and room.next_seq commit together, so an unlocked read never sees a gap.
    async with svc.pair_transaction(request, actor, peer_id, lock=False) as (db, user, peer):
        room = await svc.live_room(db, user, peer, connection_id, lock=False)
        rows = (
            await db.scalars(
                select(HumanMessage)
                .where(
                    HumanMessage.connection_id == room.id,
                    HumanMessage.seq > int(after_seq),
                    HumanMessage.created_at > now() - timedelta(days=90),
                )
                .order_by(HumanMessage.seq)
                .limit(100)
            )
        ).all()
        return MessagePage(
            messages=[svc.message_view(row, user.id) for row in rows],
            high_water_seq=str(room.next_seq),
        )


@router.post("/connections/{connection_id}/end", response_model=ActionReceipt)
async def end(
    connection_id: UUID, body: VersionInput, request: Request, actor: Actor = Depends(require_actor)
):
    peer_id = await svc.room_peer(request, actor, connection_id)
    key, payload = idempotency_key(request), body.model_dump(mode="json")
    async with svc.pair_transaction(request, actor, peer_id) as (db, user, peer):
        pair = await svc.canonical_pair(db, user.id, peer.id, False)
        room = await db.scalar(
            select(Connection).where(Connection.id == connection_id).with_for_update()
        )
        old = await previous_receipt(db, user, f"room:end:{room.id}", key, payload)
        if old:
            return ActionReceipt.model_validate(old)
        if room.version != body.expected_version or room.status != "open":
            raise DomainError(409, "ROOM_CHANGED", "Kết nối đã thay đổi.")
        room.status = "closed"
        room.version += 1
        pair.cooldown_until = now() + timedelta(days=30)
        result = svc.receipt(room.id, room.version)
        save_receipt(
            db,
            user,
            f"room:end:{room.id}",
            key,
            payload,
            result.model_dump(mode="json", by_alias=True),
        )
        return result


@router.post("/blocks", response_model=ActionReceipt, status_code=201)
async def block(body: BlockInput, request: Request, actor: Actor = Depends(require_actor)):
    ref = await svc.resolve_reference(request, actor, body.peer_ref)
    key, payload = idempotency_key(request), body.model_dump(mode="json")
    return await block_peer(ref.peer_id, key, payload, request, actor)


async def block_peer(peer_id, key, payload, request, actor):
    async with svc.pair_transaction(request, actor, peer_id) as (db, user, peer):
        pair = await svc.canonical_pair(db, user.id, peer.id)
        old = await previous_receipt(db, user, "pair:block", key, payload)
        if old:
            return ActionReceipt.model_validate(old)
        if not await db.get(Block, (user.id, peer.id)):
            db.add(Block(blocker_id=user.id, blocked_id=peer.id))
        await db.execute(
            update(Connection)
            .where(Connection.pair_id == pair.id, Connection.status == "open")
            .values(status="blocked", version=Connection.version + 1)
        )
        await db.execute(
            update(ConnectionRequest)
            .where(ConnectionRequest.pair_id == pair.id, ConnectionRequest.status == "pending")
            .values(status="invalidated", version=ConnectionRequest.version + 1)
        )
        pair.cooldown_until = now() + timedelta(days=30)
        pair.version += 1
        result = svc.receipt(pair.id, pair.version)
        save_receipt(
            db, user, "pair:block", key, payload, result.model_dump(mode="json", by_alias=True)
        )
        return result


@router.post("/connections/{connection_id}/block", response_model=ActionReceipt, status_code=201)
async def block_connection(
    connection_id: UUID, body: EmptyInput, request: Request, actor: Actor = Depends(require_actor)
):
    peer_id = await svc.room_peer(request, actor, connection_id)
    return await block_peer(
        peer_id, idempotency_key(request), {"connectionId": str(connection_id)}, request, actor
    )
