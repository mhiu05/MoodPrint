"""Two-actor helpers for shared-activity tests (real PostgreSQL, real routes)."""

from tests.social_helpers import key


def enable(app, kinds=("icebreaker", "coop_quiz", "focus")):
    app.state.settings.activities_enabled = True
    app.state.settings.activity_kinds = list(kinds)


async def invite(client, room, kind="icebreaker", options=None, headers=None):
    body = {"kind": kind, **({"options": options} if options else {})}
    return await client.post(
        f"/api/v1/connections/{room}/activities", json=body, headers=headers or key()
    )


async def command(client, session, op, version, headers=None):
    path = f"/api/v1/activities/{session}/" + (
        f"focus/{op}" if op in ("pause", "resume", "leave", "join") else op
    )
    return await client.post(path, json={"expectedVersion": version}, headers=headers or key())


async def current(client, room):
    response = await client.get(f"/api/v1/connections/{room}/activities/current")
    assert response.status_code == 200, response.text
    return response.json()


async def respond(client, session, round_number, version=0, headers=None, **answer):
    return await client.post(
        f"/api/v1/activities/{session}/responses",
        json={"round": round_number, "expectedVersion": version, **answer},
        headers=headers or key(),
    )


async def ready(client, session, round_number, version=0):
    return await client.post(
        f"/api/v1/activities/{session}/ready",
        json={"round": round_number, "expectedVersion": version},
        headers=key(),
    )


async def started(client_a, client_b, room, kind="icebreaker", options=None):
    """A invites, B accepts; returns B's view of the active session."""
    sent = await invite(client_a, room, kind, options)
    assert sent.status_code == 201, sent.text
    session = sent.json()
    accepted = await command(client_b, session["id"], "accept", session["version"])
    assert accepted.status_code == 200, accepted.text
    return accepted.json()
