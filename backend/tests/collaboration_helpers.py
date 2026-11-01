"""Synthetic setup for companion-collaboration tests. Never contacts a provider."""

import json
from datetime import date, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select

from tests.fakes import ScriptedModel, message_output

JOURNAL_CANARY = "CANARY-J-91"
USER_CANARY = "CANARY-U-27"


def key():
    return {"Idempotency-Key": str(uuid4())}


def specialist_model(payload, **kwargs) -> ScriptedModel:
    return ScriptedModel([[message_output(json.dumps(payload, ensure_ascii=False))]], **kwargs)


def primary(*texts, **kwargs) -> ScriptedModel:
    payload = {"messages": [{"text": text, "cards": []} for text in texts]}
    return ScriptedModel([[message_output(json.dumps(payload, ensure_ascii=False))]], **kwargs)


HABIT = {"habit_text": "Tắt màn hình 30 phút trước khi ngủ và thở chậm vài nhịp.", "duration_minutes": 5,
         "kind": "wind_down"}
ACTIVITY = {"activity_text": "Vẽ nhanh chiếc cốc trên bàn trong 10 phút, chỉ dùng bút bi.", "challenge_kind": "drawing"}


def energy(entry_ids, level="low", minutes=5):
    return {"energy": level, "time_budget_minutes": minutes, "basis": "journal",
            "source_entry_ids": [str(i) for i in entry_ids]}


async def setup(app, client, *, edges=("nhip_energy_for_rure", "nhip_habit_for_may", "rure_activity_for_guong"),
                journal=True):
    from tests.test_chat_persistence import enable
    from tests.test_proactive_api import settings_body

    await enable(client)
    settings = app.state.settings
    settings.ai_multi_message_enabled = True
    settings.ai_collaboration_enabled = True
    settings.proactive_enabled = True
    settings.ai_accounting_enabled = True
    app.state.ai.model_override = primary("ok")
    if journal:
        current = (await client.get("/api/v1/ai/proactive")).json()["settings"]["version"]
        response = await client.put("/api/v1/ai/proactive/settings",
                                    json=settings_body(journalContextEnabled=True, expectedVersion=current),
                                    headers=key())
        assert response.status_code == 200, response.text
    for name in edges:
        view = (await client.get("/api/v1/ai/sharing")).json()
        version = next(e["version"] for e in view["edges"] if e["edge"] == name)
        response = await client.put(f"/api/v1/ai/sharing/{name}", headers=key(),
                                    json={"enabled": True, "expectedVersion": version, "policyVersion": "sharing-v1"})
        assert response.status_code == 200, response.text


def local_today() -> date:
    from app.ai.proactive.schedule import local_date
    from app.infrastructure.database.models import now

    return local_date(now(), "Asia/Ho_Chi_Minh")


async def entry(app, uid, *, days_ago=1, status="saved", text=f"Ôn thi tới khuya, mệt {JOURNAL_CANARY}", mood=2):
    from app.modules.journal.models import JournalEntry

    async with app.state.database.sessions.begin() as db:
        row = JournalEntry(user_id=uid, local_date=local_today() - timedelta(days=days_ago),
                           timezone="Asia/Ho_Chi_Minh", mood=mood, text=text, status=status,
                           emotions=["mệt"], factors=["học tập"])
        db.add(row)
    return row.id


async def start(app, client, url, text, *, model=None):
    """Start one turn without waiting; returns the live run."""
    if model is not None:
        app.state.ai.model_override = model
    view = (await client.get(url)).json()
    accepted = await client.post(url + "/messages", headers=key(), json={
        "text": text, "clientMessageId": str(uuid4()), "expectedConversationVersion": view["version"]})
    assert accepted.status_code == 202, accepted.text
    return app.state.ai.runs[UUID(accepted.json()["runId"])]


async def finish(run):
    import asyncio

    await asyncio.wait_for(asyncio.gather(run.task, return_exceptions=True), 20)
    return run


async def receipts(app, run_id=None):
    from app.ai.collaboration.models import AiCollaboration

    async with app.state.database.sessions() as db:
        statement = select(AiCollaboration)
        if run_id is not None:
            statement = statement.where(AiCollaboration.primary_run_id == run_id)
        return (await db.scalars(statement)).all()


def sent_text(model: ScriptedModel, index=-1) -> str:
    call = model.calls[index]
    return call["instructions"] + "\n" + json.dumps(call["input"], ensure_ascii=False)
