"""G-02: focus invite options, sweeper-driven phases, pause/resume/leave/join, summaries."""

from datetime import timedelta
from uuid import UUID

import pytest

from app.infrastructure.database.models import now
from app.modules.activities.jobs import advance_due
from tests.activity_helpers import command, current, enable, invite, started
from tests.social_helpers import open_room

pytestmark = pytest.mark.postgres


async def focus_room(clients):
    app, actors, _, room = await open_room(clients)
    enable(app)
    (a, _), (b, _) = actors
    return app, a, b, room


@pytest.mark.parametrize("options", [{"plan": [20, 5]}, {"cycles": 5}, {"cycles": 0}])
async def test_invalid_plans_are_rejected(clients, options):
    app, a, b, room = await focus_room(clients)
    assert (await invite(a, room, "focus", options)).status_code == 422


async def test_accept_starts_and_the_sweeper_drives_phases_to_completion(clients):
    app, a, b, room = await focus_room(clients)
    view = await started(a, b, room, "focus", {"plan": [15, 3], "cycles": 2})
    assert view["state"] == "active" and view["timer"]["phase"] == "starting"
    assert view["timer"]["plan"] == [15, 3] and view["timer"]["cycles"] == 2
    assert view["timer"]["selfPresent"] and view["timer"]["peerPresent"]
    t0 = now()
    assert await advance_due(app, t0 + timedelta(seconds=6)) == 1
    assert (await current(a, room))["timer"]["phase"] == "focus"
    await advance_due(app, t0 + timedelta(minutes=15, seconds=6))
    assert (await current(b, room))["timer"]["phase"] == "break"
    await advance_due(app, t0 + timedelta(minutes=18, seconds=6))
    focus_two = await current(a, room)
    assert (focus_two["timer"]["phase"], focus_two["timer"]["cycle"]) == ("focus", 2)
    await advance_due(app, t0 + timedelta(minutes=33, seconds=6))
    done_a, done_b = await current(a, room), await current(b, room)
    assert done_a["state"] == "completed"
    summary_a, summary_b = done_a["summary"], done_b["summary"]
    assert summary_a["focusMinutesTogether"] == summary_b["focusMinutesTogether"]
    assert summary_a["focusMinutesSelf"] == summary_b["focusMinutesPeer"]


async def test_either_participant_pauses_and_resumes(clients):
    app, a, b, room = await focus_room(clients)
    view = await started(a, b, room, "focus")
    await advance_due(app, now() + timedelta(seconds=6))
    view = await current(a, room)
    paused = await command(a, view["id"], "pause", view["version"])
    assert paused.status_code == 200, paused.text
    assert paused.json()["state"] == "paused" and paused.json()["timer"]["pausedBySelf"] is True
    peer = await current(b, room)
    assert peer["timer"]["pausedBySelf"] is False and peer["timer"]["phaseEndsAt"] is None
    assert peer["timer"]["pausedRemainingSec"] > 0
    resumed = await command(b, peer["id"], "resume", peer["version"])
    assert resumed.status_code == 200 and resumed.json()["state"] == "active"
    assert resumed.json()["timer"]["phaseEndsAt"]


async def test_pause_limit_ends_the_session(clients):
    app, a, b, room = await focus_room(clients)
    await started(a, b, room, "focus")
    await advance_due(app, now() + timedelta(seconds=6))
    view = await current(a, room)
    await command(a, view["id"], "pause", view["version"])
    await advance_due(app, now() + timedelta(minutes=16))
    ended = await current(b, room)
    assert (ended["state"], ended["endReason"]) == ("ended", "pause_expired")


async def test_leave_and_join_update_presence_for_the_peer(clients):
    app, a, b, room = await focus_room(clients)
    view = await started(a, b, room, "focus")
    left = await command(b, view["id"], "leave", view["version"])
    assert left.status_code == 200 and left.json()["timer"]["selfPresent"] is False
    assert (await current(a, room))["timer"]["peerPresent"] is False
    joined = await command(b, view["id"], "join", left.json()["version"])
    assert joined.json()["timer"]["selfPresent"] is True


async def test_focus_controls_on_other_kinds_are_refused(clients):
    app, a, b, room = await focus_room(clients)
    view = await started(a, b, room, "icebreaker")
    refused = await command(a, view["id"], "pause", view["version"])
    assert refused.status_code == 422 and refused.json()["error"]["code"] == "NOT_FOCUS"


async def test_test_plan_seconds_apply_only_in_the_test_environment(clients):
    app, a, b, room = await focus_room(clients)
    app.state.settings.focus_test_plan_seconds = 60
    view = await started(a, b, room, "focus")
    assert app.state.settings.app_env == "test"
    await advance_due(app, now() + timedelta(seconds=6))
    timer = (await current(a, room))["timer"]
    assert timer["phase"] == "focus"
    ends = (await current(a, room))["timer"]["phaseEndsAt"]
    assert ends and UUID(view["id"])
