from uuid import uuid4

import pytest

from tests.test_social import key, open_room

pytestmark = pytest.mark.postgres


async def test_reveal_requires_data_owner_approval_and_identity_edit_revokes_access(clients):
    _, actors, _, room = await open_room(clients)
    a, b = actors[0][0], actors[1][0]
    identity = await a.patch(
        "/api/v1/users/me/identity",
        json={"field": "displayName", "value": "Tên riêng của A", "expectedVersion": 0},
        headers=key(),
    )
    assert identity.status_code == 200, identity.text
    request = await b.post(
        f"/api/v1/connections/{room}/reveal-requests",
        json={"field": "displayName", "ownerSide": "peer", "expectedIdentityVersion": 1},
        headers=key(),
    )
    assert request.status_code == 201, request.text
    assert "Tên riêng của A" not in request.text
    pending = request.json()
    forbidden = await b.post(
        f"/api/v1/reveal-requests/{pending['id']}/grant",
        json={"expectedVersion": 1, "previewDigest": "forged"},
        headers=key(),
    )
    assert forbidden.status_code == 403
    own = (await a.get(f"/api/v1/connections/{room}/reveal-requests")).json()[0]
    assert own["previewValue"] == "Tên riêng của A"
    granted = await a.post(
        f"/api/v1/reveal-requests/{pending['id']}/grant",
        json={"expectedVersion": 1, "previewDigest": own["previewDigest"]},
        headers=key(),
    )
    assert granted.status_code == 200, granted.text
    value = await b.get(f"/api/v1/reveal-grants/{pending['id']}/value")
    assert value.status_code == 200 and value.json()["value"] == "Tên riêng của A"
    await a.patch(
        "/api/v1/users/me/identity",
        json={"field": "displayName", "value": "Tên mới", "expectedVersion": 1},
        headers=key(),
    )
    assert (await b.get(f"/api/v1/reveal-grants/{pending['id']}/value")).status_code == 403


async def test_report_contains_only_selected_authorized_evidence_and_block_is_independent(clients):
    _, actors, refs, room = await open_room(clients)
    a, b = actors[0][0], actors[1][0]
    message = await b.post(
        f"/api/v1/connections/{room}/messages",
        json={"text": "Tin nhắn được chọn", "clientMessageId": str(uuid4())},
        headers=key(),
    )
    headers = key()
    body = {
        "peerRef": refs[0],
        "reason": "Nội dung không phù hợp",
        "selectedMessageIds": [message.json()["id"]],
    }
    report = await a.post("/api/v1/reports", json=body, headers=headers)
    assert report.status_code == 201, report.text
    assert report.json()["status"] == "received"
    assert "Tin nhắn được chọn" not in report.text
    replay = await a.post("/api/v1/reports", json=body, headers=headers)
    assert replay.json() == report.json()
    assert (await b.get(f"/api/v1/reports/{report.json()['id']}")).status_code == 404
    assert (await a.get(f"/api/v1/connections/{room}/messages")).status_code == 200
    too_many = await a.post(
        "/api/v1/reports",
        json={**body, "selectedMessageIds": [str(uuid4()) for _ in range(3)]},
        headers=key(),
    )
    assert too_many.status_code == 422
    blocked = await a.post("/api/v1/blocks", json={"peerRef": refs[0]}, headers=key())
    assert blocked.status_code == 201
    assert (await b.get(f"/api/v1/connections/{room}/messages")).status_code == 403


async def test_connection_block_does_not_need_an_unexpired_discovery_card(clients):
    _, actors, _, room = await open_room(clients)
    result = await actors[0][0].post(f"/api/v1/connections/{room}/block", json={}, headers=key())
    assert result.status_code == 201, result.text
    assert (await actors[1][0].get(f"/api/v1/connections/{room}/messages")).status_code == 403
