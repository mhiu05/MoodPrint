import time
from uuid import uuid4

from app.ai.runtime import AiRuntime, LiveRun, Proposal
from app.ai.schemas import AIEvent
from app.core.config import Settings
from app.core.security import Actor
from app.infrastructure.database.connection import Database


def test_idle_expiry_physically_removes_replay_and_proposals_without_a_read():
    runtime = AiRuntime(Settings(_env_file=None), Database(Settings(_env_file=None)))
    c = runtime.store.create("owner", "session", "may")
    run = LiveRun(Actor(uuid4(), uuid4(), 1), c.id, 1, uuid4())
    run.events = [AIEvent(seq="1", type="final", data={"text": "PRIVATE-TEMPORARY", "cards": []})]
    run.terminal = True
    runtime.runs[run.id] = run
    proposal = Proposal(
        run.actor.user_id,
        run.actor.session_id,
        "may",
        "PRIVATE-PROPOSAL",
        "memory",
        1,
        time.monotonic() - 1,
    )
    runtime.proposals[proposal.id] = proposal
    c.touched -= 86401
    runtime.sweep()
    assert runtime.store.conversations == {}
    assert runtime.runs == {}
    assert runtime.proposals == {}
    assert run.events == []
