"""V3-11: AI groups — creation, membership, rename, delete, owner isolation, flags."""

import pytest

from tests.group_helpers import create_group, groups_setup
from tests.orchestration_helpers import key

pytestmark = pytest.mark.postgres
BASE = "/api/v1/ai/groups"


async def test_group_lifecycle_for_the_owner(clients):
    app, [(client, uid), _] = clients
    await groups_setup(app, client)
    group = await create_group(client, ("nhatky", "hoatdong"), name="  Cuối   tuần  ")
    assert group["name"] == "Cuối tuần" and group["version"] == 1
    assert [(m["botId"], m["status"], m["journalAccess"]) for m in group["members"]] == [
        ("nhatky", "active", False), ("hoatdong", "active", False)]
    listed = (await client.get(BASE)).json()
    assert [item["groupId"] for item in listed] == [group["groupId"]]
    url = f"{BASE}/{group['groupId']}"
    view = (await client.get(url)).json()
    assert view["messages"] == [] and view["activeTurnId"] is None

    renamed = await client.patch(url, json={"name": "Kế hoạch", "expectedVersion": 1}, headers=key())
    assert renamed.status_code == 200 and renamed.json()["name"] == "Kế hoạch"
    added = await client.post(url + "/members", json={"botId": "dieuphoi", "shareHistory": False,
                                                       "expectedVersion": 1}, headers=key())
    assert added.status_code == 200, added.text
    assert {m["botId"] for m in added.json()["members"] if m["status"] == "active"} == {"nhatky", "hoatdong", "dieuphoi"}
    duplicate = await client.post(url + "/members", json={"botId": "dieuphoi", "shareHistory": False,
                                                           "expectedVersion": 1}, headers=key())
    assert duplicate.status_code == 409 and duplicate.json()["error"]["code"] == "ALREADY_MEMBER"
    removed = await client.delete(url + "/members/hoatdong?expectedVersion=1", headers=key())
    assert removed.status_code == 200
    statuses = {m["botId"]: m["status"] for m in removed.json()["members"]}
    assert statuses == {"nhatky": "active", "hoatdong": "removed", "dieuphoi": "active"}
    # Never below two members.
    second = await client.delete(url + "/members/nhatky?expectedVersion=1", headers=key())
    assert second.status_code == 409 and second.json()["error"]["code"] == "GROUP_MIN_MEMBERS"
    # Re-adding a removed member reactivates it.
    again = await client.post(url + "/members", json={"botId": "hoatdong", "shareHistory": True,
                                                       "expectedVersion": 1}, headers=key())
    assert again.status_code == 200
    assert {m["botId"]: m["status"] for m in again.json()["members"]}["hoatdong"] == "active"

    journal = await client.put(url + "/members/nhatky/journal-access", json={"enabled": True, "expectedVersion": 1},
                               headers=key())
    assert journal.status_code == 200
    assert next(m for m in journal.json()["members"] if m["botId"] == "nhatky")["journalAccess"] is True
    wrong = await client.put(url + "/members/hoatdong/journal-access", json={"enabled": True, "expectedVersion": 1},
                             headers=key())
    assert wrong.status_code == 422

    deleted = await client.delete(url, headers=key())
    assert deleted.status_code == 204
    assert (await client.get(url)).status_code == 404 and (await client.get(BASE)).json() == []


@pytest.mark.parametrize("members", [["dieuphoi"], ["dieuphoi", "dieuphoi"], ["dieuphoi", "may"], []])
async def test_invalid_membership_is_rejected(clients, members):
    app, [(client, _uid), _] = clients
    await groups_setup(app, client)
    response = await client.post(BASE, json={"name": "Nhóm", "members": members}, headers=key())
    assert response.status_code == 422


async def test_groups_are_owner_scoped_and_hidden_from_direct_chat(clients):
    app, [(client, _uid), (other, _other_uid)] = clients
    await groups_setup(app, client)
    group = await create_group(client)
    url = f"{BASE}/{group['groupId']}"
    for request in (other.get(url), other.patch(url, json={"name": "x", "expectedVersion": 1}, headers=key()),
                    other.delete(url, headers=key()),
                    other.post(url + "/members", json={"botId": "dieuphoi", "shareHistory": False,
                                                       "expectedVersion": 1}, headers=key())):
        response = await request
        assert response.status_code in (403, 404), response.text
    assert (await other.get(BASE)).status_code in (200, 403)
    assert (await client.get(f"/api/v1/ai/conversations/{group['groupId']}")).status_code == 404
    assert all(item["conversationId"] != group["groupId"]
               for item in (await client.get("/api/v1/ai/conversations")).json())


async def test_flags_and_eligibility_gate_groups(clients):
    from tests.conftest import add_actor

    app, [(client, _uid), _] = clients
    await groups_setup(app, client)
    app.state.settings.ai_group_chat_enabled = False
    assert (await client.post(BASE, json={"name": "x", "members": ["dieuphoi", "nhatky"]},
                              headers=key())).status_code == 404
    assert (await client.get("/api/v1/session")).json()["features"]["groupChat"] is False
    app.state.settings.ai_group_chat_enabled = True
    assert (await client.get("/api/v1/session")).json()["features"]["groupChat"] is True
    teen_client, _teen = await add_actor(app, 7, age_band="teen")
    app.state.test_clients.append(teen_client)
    response = await teen_client.post(BASE, json={"name": "x", "members": ["dieuphoi", "nhatky"]}, headers=key())
    assert response.status_code in (403, 404)
