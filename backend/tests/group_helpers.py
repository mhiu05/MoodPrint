"""Synthetic V3 group-chat setup. Real SDK runs; only the Model is scripted per role."""

import asyncio
from uuid import UUID, uuid4

from tests.orchestration_helpers import key, reply, roles, scripted


async def groups_setup(app, client, *, journal=False):
    from tests.orchestration_helpers import v3_setup

    await v3_setup(app, client, edges=(), journal=journal)
    app.state.settings.ai_group_chat_enabled = True


async def create_group(client, members=("dieuphoi", "nhatky", "hoatdong"), name="Cuối tuần"):
    response = await client.post("/api/v1/ai/groups", json={"name": name, "members": list(members)}, headers=key())
    assert response.status_code == 201, response.text
    return response.json()


async def say(app, client, group_id, text, *, mentions=(), wait=True):
    view = (await client.get(f"/api/v1/ai/groups/{group_id}")).json()
    accepted = await client.post(f"/api/v1/ai/groups/{group_id}/messages", headers=key(), json={
        "text": text, "clientMessageId": str(uuid4()), "expectedVersion": view["version"],
        "mentions": list(mentions)})
    assert accepted.status_code == 202, accepted.text
    run = app.state.ai.runs[UUID(accepted.json()["turnId"])]
    if wait:
        await asyncio.wait_for(asyncio.gather(run.task, return_exceptions=True), 30)
    return run, accepted.json()


def speakers(app, **texts):
    """One scripted model per speaking agent; returns the models for input inspection."""
    models = {name: scripted(*[reply(text) for text in (value if isinstance(value, tuple) else (value,))])
              for name, value in texts.items()}
    roles(app, **models)
    return models
