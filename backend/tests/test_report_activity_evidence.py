"""T-MOD-03, T-PRIV-01: activity answers as report evidence; read markers in export/deletion."""

from uuid import uuid4

import pytest
from sqlalchemy import select

from app.modules.moderation.models import Report
from app.modules.social.models import ConnectionRead
from tests.activity_helpers import enable, respond, started
from tests.conftest import add_actor
from tests.social_helpers import consent, key, open_room

pytestmark = pytest.mark.postgres


async def answered(clients, a_skips=False):
    app, actors, _, room = await open_room(clients)
    enable(app)
    (a, a_id), (b, b_id) = actors
    sid = (await started(a, b, room))["id"]
    await respond(b, sid, 1, text="LỜI-LẼ-XÚC-PHẠM")
    if a_skips:
        await respond(a, sid, 1, skipped=True)
    else:
        await respond(a, sid, 1, choice=0)
    ref = (
        await a.post(f"/api/v1/connections/{room}/peer-reference", json={}, headers=key())
    ).json()["peerRef"]
    return app, a, b, room, sid, ref


async def file_report(client, ref, responses):
    return await client.post(
        "/api/v1/reports",
        json={"peerRef": ref, "reason": "Xúc phạm", "selectedActivityResponses": responses},
        headers=key(),
    )


async def test_a_revealed_peer_answer_is_copied_into_the_report(clients):
    app, a, b, room, sid, ref = await answered(clients)
    created = await file_report(a, ref, [{"sessionId": sid, "round": 1}])
    assert created.status_code == 201, created.text
    async with app.state.database.sessions() as db:
        report = await db.scalar(select(Report))
    [evidence] = report.evidence
    assert evidence["kind"] == "activity" and evidence["text"] == "LỜI-LẼ-XÚC-PHẠM"
    assert evidence["round"] == 1 and evidence["prompt"]
    assert str(report.connection_id) == room


async def test_unseen_foreign_or_too_many_answers_are_refused(clients):
    app, a, b, room, sid, ref = await answered(clients, a_skips=True)
    hidden = await file_report(a, ref, [{"sessionId": sid, "round": 1}])
    assert hidden.status_code == 403 and hidden.json()["error"]["code"] == "EVIDENCE_DENIED"
    foreign = await file_report(a, ref, [{"sessionId": str(uuid4()), "round": 1}])
    assert foreign.status_code == 403
    many = await file_report(a, ref, [{"sessionId": sid, "round": r} for r in (1, 2, 3)])
    assert many.status_code == 422


async def test_read_markers_are_exported_and_deleted_with_the_account(clients):
    from app.modules.users.lifecycle import process_deletions

    app, actors, _, room = await open_room(clients)
    (a, a_id), (b, _) = actors
    await b.post(
        f"/api/v1/connections/{room}/messages",
        json={"text": "chào", "clientMessageId": str(uuid4())},
        headers=key(),
    )
    await a.post(f"/api/v1/connections/{room}/read", json={"seq": "1"}, headers=key())
    job = (await a.post("/api/v1/exports", json={"scopes": ["social"]}, headers=key())).json()
    exported = (await a.get(f"/api/v1/exports/{job['id']}/download")).json()["social"]
    assert [row["lastReadSeq"] for row in exported["readMarkers"]] == ["1"]
    version = (await a.get("/api/v1/session")).json()["dataVersion"]
    deletion = await a.post(
        "/api/v1/data-deletions",
        json={"scope": "account", "expectedVersion": version},
        headers=key(),
    )
    assert deletion.status_code == 202, deletion.text
    await process_deletions(app)
    async with app.state.database.sessions() as db:
        assert (
            await db.scalars(select(ConnectionRead).where(ConnectionRead.user_id == a_id))
        ).all() == []


async def test_a_third_user_cannot_attach_this_pairs_answers(clients):
    app, a, b, room, sid, ref = await answered(clients)
    c, _ = await add_actor(app, 3)
    await consent(c)
    forged = await file_report(c, ref, [{"sessionId": sid, "round": 1}])
    assert forged.status_code == 404
