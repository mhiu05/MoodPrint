"""Exhaustive hard purge of a guest's active footprint, incidents and late writers (GE-06.1)."""

from datetime import date, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import DBAPIError

from tests.guest_helpers import add_guest

pytestmark = pytest.mark.postgres
LIFETIME = timedelta(seconds=7200)


async def seed_owned(app, uid: UUID, *, peer: UUID, guest: bool) -> dict[str, list[UUID]]:
    """One row in every store a personal account (or a guest) may own; returns saved plain IDs."""
    from app.ai.memory_models import MemoryProposal
    from app.ai.models import AiConversation, AiMessageRecord, AiPreference, AiTurn
    from app.infrastructure.database.models import (
        AgeDeclaration,
        AiRun,
        AiUsage,
        ConsentEvent,
        Idempotency,
        Memory,
        Mood,
        Outbox,
        now,
    )
    from app.modules.journal.models import JournalEntry, JournalMedia
    from app.modules.moderation.models import IdentityField
    from app.modules.social.models import CandidateReference, MatchingDraft, PublishedProfile
    from app.modules.users.models import DataJob

    soon = now() + timedelta(minutes=10)
    async with app.state.database.sessions.begin() as db:
        db.add(AgeDeclaration(user_id=uid, birth_year=2000, policy_version="self-declared-age-v1"))
        db.add(ConsentEvent(user_id=uid, purpose="AI", enabled=True, version=2, policy_version="v1"))
        db.add(Mood(user_id=uid, local_date=date.today(), value=3, timezone="Asia/Bangkok"))
        journal = JournalEntry(user_id=uid, local_date=date.today(), timezone="Asia/Bangkok", mood=4, text="journal canary")
        db.add(journal)
        await db.flush()
        db.add(JournalMedia(user_id=uid, entry_id=journal.id, type="image", object_path=f"guest-purge/{uid}",
                            mime_type="image/png", size_bytes=10, status="ready"))
        memory = Memory(user_id=uid, bot_id="may", text="bộ nhớ", proposal_id=uuid4())
        db.add(memory)
        db.add(
            MemoryProposal(
                user_id=uid, bot_id="may", text="đề xuất", data_version=1,
                ai_consent_version=1, mem_consent_version=1, expires_at=soon,
            )
        )
        conversation = AiConversation(user_id=uid, bot_id="may", expires_at=soon)
        db.add(conversation)
        await db.flush()
        run = AiRun(user_id=uid, conversation_id=conversation.id, bot_id="may")
        db.add(run)
        await db.flush()
        db.add(AiMessageRecord(conversation_id=conversation.id, sequence=1, actor="bot", text="đáp", run_id=run.id))
        db.add(
            AiTurn(
                run_id=run.id, user_id=uid, scope_id=uuid4(), session_id=uuid4(),
                client_message_id=uuid4(), input_digest="d", data_version=1, worker_id=uuid4(),
                lease_until=soon,
            )
        )
        db.add(
            AiUsage(
                run_id=run.id, user_id=uid, worker_id=uuid4(), model="m", prompt_version="p",
                pricing_version="x", lease_until=soon,
            )
        )
        db.add(AiPreference(user_id=uid, history_enabled=True, semantic_memory_enabled=False, version=1))
        db.add(Outbox(user_id=uid, kind="legacy", resource_id=str(uuid4()), version=1))
        db.add(IdentityField(user_id=uid, field="display", value="tên"))
        db.add(DataJob(user_id=uid, kind="export", scope="moods", status="ready"))
        db.add(
            Idempotency(user_id=uid, operation="mood:save", key=f"k-{uuid4()}", digest="d", receipt={})
        )
        db.add(MatchingDraft(user_id=uid, payload={}))
        db.add(PublishedProfile(user_id=uid, payload={}, version=1, consent_version=1, valid=False))
        db.add(
            CandidateReference(
                user_id=uid, peer_id=peer, profile_version=1, peer_profile_version=1,
                consent_version=1, peer_consent_version=1, expires_at=soon,
            )
        )
        await db.flush()
        from tests.proactive_helpers import seed_proactive

        await seed_proactive(db, uid, conversation_id=conversation.id, run_id=run.id)
        return {
            "conversation": [conversation.id],
            "run": [run.id],
            "memory": [memory.id],
        }


async def seed_guest_only(app, guest) -> None:
    from app.modules.guests.models import GuestOperationLink, GuestProvisioningAttempt
    from app.modules.moderation.models import StaffRole

    async with app.state.database.sessions.begin() as db:
        db.add(StaffRole(user_id=guest.user_id, role="moderator", granted_by="forged-test"))
        db.add(
            GuestOperationLink(
                user_id=guest.user_id, kind="ai", operation_key_hash="a" * 64,
                payload_digest="b" * 64, state="claimed", worker_id=uuid4(),
                lease_token=uuid4(), lease_until=datetime.now().astimezone() + timedelta(minutes=1),
            )
        )
        db.add(
            GuestProvisioningAttempt(
                intent_hash=uuid4().hex * 2, provider_correlation=uuid4().hex * 2,
                provider_subject=guest.user_id, provider_session_id=guest.provider_session_id,
                user_id=guest.user_id, state="granted",
            )
        )


async def claim(app, guest) -> UUID:
    """The cleanup worker's claim step (lease only); GE-06.2 owns the real claimer."""
    from app.modules.guests.models import GuestCleanupJob

    token = uuid4()
    async with app.state.database.sessions.begin() as db:
        await db.execute(
            update(GuestCleanupJob)
            .where(GuestCleanupJob.user_id == guest.user_id)
            .values(state="running", lease_token=token, lease_until=func.clock_timestamp() + timedelta(seconds=30))
        )
    return token


async def purge(app, user_id, token):
    from app.modules.guests.lifecycle import purge_guest

    async with app.state.database.sessions.begin() as db:
        return await purge_guest(db, user_id, token)


async def user_reference_counts(app, uid: UUID) -> dict[str, int]:
    """Metadata-derived: every column of every table that is a foreign key to users.id."""
    from app.infrastructure.database.models import Base

    counts: dict[str, int] = {}
    async with app.state.database.sessions() as db:
        for table in Base.metadata.sorted_tables:
            for column in table.columns:
                if any(fk.column.table.name == "users" for fk in column.foreign_keys):
                    key = f"{table.name}.{column.name}"
                    counts[key] = await db.scalar(
                        select(func.count()).select_from(table).where(column == uid)
                    )
    return counts


async def provider_rows(app, uid: UUID) -> tuple[int, int]:
    async with app.state.database.sessions() as db:
        return (
            await db.scalar(text("select count(*) from auth.users where id=:u"), {"u": uid}),
            await db.scalar(text("select count(*) from auth.sessions where user_id=:u"), {"u": uid}),
        )


def test_inventory_classifies_every_orm_table():
    from app.infrastructure.database.models import Base
    from app.modules.guests.lifecycle import INVENTORY

    tables = {name.removeprefix("moodprint.") for name in Base.metadata.tables}
    assert tables == set(INVENTORY), (
        f"unclassified={sorted(tables - set(INVENTORY))} obsolete={sorted(set(INVENTORY) - tables)}"
    )
    assert set(INVENTORY.values()) == {"owner", "purged", "social", "detached"}


async def test_purge_removes_every_guest_owned_store(clients):
    app, actors = clients
    registered_client, registered_id = actors[0]
    guest = await add_guest(app, started_ago=LIFETIME + timedelta(seconds=5), consents=True)
    saved = await seed_owned(app, guest.user_id, peer=actors[1][1], guest=True)
    await seed_owned(app, registered_id, peer=actors[1][1], guest=False)  # registered canaries
    await seed_guest_only(app, guest)
    registered_before = await user_reference_counts(app, registered_id)
    registered_provider = await provider_rows(app, registered_id)
    guest_before = await user_reference_counts(app, guest.user_id)
    assert sum(guest_before.values()) > 20, "the seed must populate many stores"
    assert (await provider_rows(app, guest.user_id)) == (1, 1)

    assert await purge(app, guest.user_id, await claim(app, guest)) == "removed"

    after = await user_reference_counts(app, guest.user_id)
    assert all(count == 0 for count in after.values()), {k: v for k, v in after.items() if v}
    async with app.state.database.sessions() as db:
        for ids, table in (
            (saved["conversation"], "ai_messages"),
            (saved["run"], "ai_turns"),
            (saved["run"], "ai_usage"),
            (saved["memory"], "memory_embeddings"),
            (saved["memory"], "memories"),
        ):
            column = {"ai_messages": "conversation_id", "memories": "id"}.get(table, "run_id" if table.startswith("ai_") else "memory_id")
            hits = await db.scalar(
                text(f"select count(*) from moodprint.{table} where {column} = any(:ids)"),
                {"ids": ids},
            )
            assert hits == 0, table
        leftovers = await db.scalar(
            text(
                "select count(*) from moodprint.guest_provisioning_attempts"
                " where provider_subject=:u or provider_session_id=:s"
            ),
            {"u": guest.user_id, "s": guest.provider_session_id},
        )
        assert leftovers == 0, "no attempt row may keep provider ids"
    assert await provider_rows(app, guest.user_id) == (0, 0), "provider identity and children are gone"
    from app.modules.journal.models import JournalStorageDeletion

    async with app.state.database.sessions() as db:
        assert await db.scalar(select(JournalStorageDeletion.object_path).where(
            JournalStorageDeletion.object_path == f"guest-purge/{guest.user_id}"
        )) == f"guest-purge/{guest.user_id}"
    # The registered counterpart's stores and its provider identity are untouched.
    assert await user_reference_counts(app, registered_id) == registered_before
    assert await provider_rows(app, registered_id) == registered_provider
    # Replay of a completed purge is safe and creates nothing.
    assert await purge(app, guest.user_id, uuid4()) == "removed"
    assert await user_reference_counts(app, registered_id) == registered_before


async def test_purge_is_fenced_unless_the_lease_and_the_deadline_allow_it(clients):
    app, _ = clients
    expired = await add_guest(app, started_ago=LIFETIME + timedelta(seconds=5))
    token = await claim(app, expired)
    assert await purge(app, expired.user_id, uuid4()) == "fenced", "a stale/foreign lease cannot purge"
    assert (await user_reference_counts(app, expired.user_id))["auth_sessions.user_id"] == 1
    live = await add_guest(app)
    assert await purge(app, live.user_id, await claim(app, live)) == "fenced", "an active trial is never purged early"
    assert (await live.client.get("/api/v1/session")).status_code == 200
    assert await purge(app, expired.user_id, token) == "removed"


async def test_purge_preserves_peer_evidence_as_incident(clients):
    from app.infrastructure.database.models import AuthSession, User
    from app.modules.guests.models import GuestCleanupJob
    from app.modules.social.models import Connection, HumanMessage, Pair

    app, actors = clients
    _, registered_id = actors[0]
    guest = await add_guest(app, started_ago=LIFETIME + timedelta(seconds=5), consents=True)
    await seed_owned(app, guest.user_id, peer=registered_id, guest=True)
    async with app.state.database.sessions.begin() as db:
        low, high = sorted((registered_id, guest.user_id))
        pair = Pair(low_user_id=low, high_user_id=high)
        db.add(pair)
        await db.flush()
        room = Connection(pair_id=pair.id, low_user_id=low, high_user_id=high, snapshots={})
        db.add(room)
        await db.flush()
        db.add(
            HumanMessage(
                connection_id=room.id, sender_id=registered_id, client_message_id=uuid4(),
                seq=1, text="REGISTERED-EVIDENCE",
            )
        )
        room_id = room.id
    token = await claim(app, guest)
    assert await purge(app, guest.user_id, token) == "incident_required"
    async with app.state.database.sessions() as db:
        job = await db.get(GuestCleanupJob, guest.user_id)
        user = await db.get(User, guest.user_id)
        sessions = (await db.scalars(select(AuthSession).where(AuthSession.user_id == guest.user_id))).all()
        evidence = await db.scalar(select(func.count()).select_from(HumanMessage).where(HumanMessage.connection_id == room_id))
    assert job.state == "incident_required" and job.alerted_at is not None
    assert job.lease_token is None
    assert user is not None and user.status == "deleting", "never reactivated, never claimed complete"
    assert sessions and all(row.revoked for row in sessions)
    assert evidence == 1, "the registered user's evidence is retained, never cascaded away"
    assert (await guest.client.get("/api/v1/session")).status_code == 401


async def test_guest_only_social_graph_is_cleaned_as_disposable_corruption(clients):
    from app.infrastructure.database.models import User
    from app.modules.social.models import Connection, HumanMessage, Pair

    app, _ = clients
    first = await add_guest(app, started_ago=LIFETIME + timedelta(seconds=5))
    second = await add_guest(app)
    async with app.state.database.sessions.begin() as db:
        low, high = sorted((first.user_id, second.user_id))
        pair = Pair(low_user_id=low, high_user_id=high)
        db.add(pair)
        await db.flush()
        room = Connection(pair_id=pair.id, low_user_id=low, high_user_id=high, snapshots={})
        db.add(room)
        await db.flush()
        db.add(HumanMessage(connection_id=room.id, sender_id=first.user_id, client_message_id=uuid4(), seq=1, text="x"))
    assert await purge(app, first.user_id, await claim(app, first)) == "removed"
    async with app.state.database.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(HumanMessage)) == 0
        assert await db.scalar(select(func.count()).select_from(Pair)) == 0
        assert await db.get(User, second.user_id) is not None, "the other guest's identity is untouched"


@pytest.mark.parametrize("evidence_kind", ["message", "participant", "response", "read"])
async def test_guest_graph_with_registered_child_authorship_requires_incident(clients, evidence_kind):
    from app.modules.activities.models import ActivityParticipant, ActivityResponse, ActivitySession
    from app.modules.social.models import Connection, ConnectionRead, HumanMessage, Pair
    app, actors = clients
    registered_id = actors[0][1]
    first = await add_guest(app, started_ago=LIFETIME + timedelta(seconds=5))
    second = await add_guest(app)
    async with app.state.database.sessions.begin() as db:
        low, high = sorted((first.user_id, second.user_id))
        pair = Pair(low_user_id=low, high_user_id=high)
        db.add(pair)
        await db.flush()
        room = Connection(pair_id=pair.id, low_user_id=low, high_user_id=high, snapshots={})
        db.add(room)
        await db.flush()
        activity = ActivitySession(connection_id=room.id, pair_id=pair.id, inviter_id=first.user_id, invitee_id=second.user_id,
                                   kind="icebreaker", definition_version="v1", state="active")
        db.add(activity)
        await db.flush()
        if evidence_kind == "message":
            row = HumanMessage(connection_id=room.id, sender_id=registered_id, client_message_id=uuid4(), seq=1, text="REGISTERED-CHILD-EVIDENCE")
        elif evidence_kind == "read":
            row = ConnectionRead(connection_id=room.id, user_id=registered_id)
        elif evidence_kind == "participant":
            row = ActivityParticipant(session_id=activity.id, user_id=registered_id, role="invitee")
        else:
            row = ActivityResponse(session_id=activity.id, user_id=registered_id, round=1, item_id="synthetic", text="REGISTERED-RESPONSE-EVIDENCE")
        db.add(row)
    assert await purge(app, first.user_id, await claim(app, first)) == "incident_required"
    async with app.state.database.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(type(row))) == 1
    assert (await first.client.get("/api/v1/session")).status_code == 401


async def test_helper_failure_rolls_back_every_row_then_retries(clients):
    app, _ = clients
    guest = await add_guest(app, started_ago=LIFETIME + timedelta(seconds=5), consents=True)
    async with app.state.database.sessions.begin() as db:
        from app.infrastructure.database.models import Mood

        db.add(Mood(user_id=guest.user_id, local_date=date.today(), value=3, timezone="Asia/Bangkok"))
        # A permanent provider identity makes the guarded helper refuse: the purge must abort whole.
        await db.execute(text("update auth.users set is_anonymous=false where id=:u"), {"u": guest.user_id})
    token = await claim(app, guest)
    with pytest.raises(DBAPIError):
        await purge(app, guest.user_id, token)
    counts = await user_reference_counts(app, guest.user_id)
    assert counts["moods.user_id"] == 1 and counts["auth_sessions.user_id"] == 1
    assert (await provider_rows(app, guest.user_id))[0] == 1
    async with app.state.database.sessions.begin() as db:
        await db.execute(text("update auth.users set is_anonymous=true where id=:u"), {"u": guest.user_id})
    assert await purge(app, guest.user_id, token) == "removed"


async def test_late_writer_cannot_resurrect(clients):
    from app.ai.embeddings import _authorization
    from app.infrastructure.database.models import AiUsage, Mood
    from app.modules.guests.models import GuestUsage

    app, _ = clients
    guest = await add_guest(app, started_ago=LIFETIME + timedelta(seconds=5), consents=True)
    saved = {"run": [uuid4()]}
    assert await purge(app, guest.user_id, await claim(app, guest)) == "removed"
    for model_row in (
        Mood(user_id=guest.user_id, local_date=date.today(), value=4, timezone="Asia/Bangkok"),
        GuestUsage(user_id=guest.user_id),
    ):
        with pytest.raises(DBAPIError):
            async with app.state.database.sessions.begin() as db:
                db.add(model_row)
    async with app.state.database.sessions.begin() as db:
        updated = await db.execute(
            update(AiUsage).where(AiUsage.run_id == saved["run"][0]).values(model="late")
        )
        assert updated.rowcount == 0, "a late usage snapshot updates nothing and creates nothing"
        assert await _authorization(db, guest.user_id) is None
    assert sum((await user_reference_counts(app, guest.user_id)).values()) == 0
