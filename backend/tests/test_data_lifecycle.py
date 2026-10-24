import pytest

from tests.test_social import key

pytestmark = pytest.mark.postgres


async def test_deletion_denies_old_data_immediately_and_worker_retry_is_idempotent(clients):
    from app.modules.users.lifecycle import process_deletions

    app, actors = clients
    a, _ = actors[0]
    await a.post(
        "/api/v1/profiles/private-items", json={"text": "Private deletion canary"}, headers=key()
    )
    snapshot = (await a.get("/api/v1/session")).json()
    receipt = await a.post(
        "/api/v1/data-deletions",
        json={"scope": "all_private", "expectedVersion": snapshot["dataVersion"]},
        headers=key(),
    )
    assert receipt.status_code == 202, receipt.text
    assert (await a.get("/api/v1/profiles/private-items")).status_code == 409
    await process_deletions(app)
    await process_deletions(app)
    status = await a.get(f"/api/v1/data-deletions/{receipt.json()['id']}")
    assert status.json()["status"] == "completed"
    assert (await a.get("/api/v1/profiles/private-items")).json() == []
    assert (
        await actors[1][0].get(f"/api/v1/data-deletions/{receipt.json()['id']}")
    ).status_code == 404


async def test_export_is_owner_only_current_and_one_use_without_peer_transcripts(clients):
    _, actors = clients
    a, _ = actors[0]
    await a.post("/api/v1/profiles/private-items", json={"text": "Own export"}, headers=key())
    created = await a.post(
        "/api/v1/exports",
        json={"scopes": ["account", "private_items", "memories", "moods"]},
        headers=key(),
    )
    assert created.status_code == 201, created.text
    job = created.json()
    assert (await actors[1][0].get(f"/api/v1/exports/{job['id']}/download")).status_code == 404
    result = await a.get(f"/api/v1/exports/{job['id']}/download")
    assert result.status_code == 200 and result.json()["privateItems"][0]["text"] == "Own export"
    assert "messages" not in result.json()
    assert (await a.get(f"/api/v1/exports/{job['id']}/download")).status_code == 410
