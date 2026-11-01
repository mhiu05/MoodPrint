"""Synthetic V3 orchestration setup. Real SDK Runner/as_tool/handoff; only the Model is scripted."""

import json
from uuid import UUID, uuid4

from openai.types.responses import ResponseFunctionToolCall
from sqlalchemy import select

from tests.fakes import ScriptedModel, message_output

V3_EDGES = ("dieuphoi_consult_nhatky", "dieuphoi_consult_hoatdong", "dieuphoi_handoff_nhatky",
            "dieuphoi_handoff_hoatdong")
HISTORY_CANARY = "CANARY-HIST-58"
JOURNAL_CANARY = "CANARY-JOUR-73"


def key():
    return {"Idempotency-Key": str(uuid4())}


def call(name: str, args: dict, call_id: str | None = None) -> ResponseFunctionToolCall:
    identifier = call_id or f"call_{name}"
    return ResponseFunctionToolCall(id=f"fc_{identifier}", call_id=identifier, name=name,
                                    arguments=json.dumps(args, ensure_ascii=False), type="function_call",
                                    status="completed")


def scripted(*responses) -> ScriptedModel:
    """Each response is a list of output items or a JSON-serializable final payload."""
    return ScriptedModel([
        item if isinstance(item, list) else [message_output(json.dumps(item, ensure_ascii=False))]
        for item in responses
    ])


def reply(*texts, **extra) -> dict:
    return {"messages": [{"text": text, "cards": []} for text in texts], **extra}


def plan(**fields) -> dict:
    body = {
        "intent": "reflect_then_plan", "workflow": "consult", "primary_agent": "dieuphoi",
        "specialists": ["nhatky", "hoatdong"], "handoff_target": None,
        "subtasks": [], "data_categories": ["journal_entries", "time_budget"],
        "context_refs": ["latest_message"], "expected_output": "plan", "confidence": 0.9,
        "fallback": "answer_directly",
    }
    body.update(fields)
    return body


REFLECTION = {"themes": ["học muộn", "mệt"], "pattern": "Mệt thường đi cùng những ngày học muộn.",
              "observations": [{"kind": "observed", "text": "Bạn có ghi là mệt sau buổi học tối."},
                               {"kind": "inferred", "text": "Có thể bạn cần một cuối tuần nhẹ hơn."}],
              "entries_considered": 1, "source_entry_ids": []}
ACTIVITIES = {"options": [{"title": "Dạo bộ chậm", "steps": ["Đi bộ 20 phút quanh nhà", "Không mang điện thoại"],
                           "minutes": 30, "effort": "light"}],
              "note": "Chọn một việc nhẹ là đủ."}


async def v3_setup(app, client, *, edges=V3_EDGES, journal=True):
    from tests.test_chat_persistence import enable
    from tests.test_proactive_api import settings_body

    await enable(client)
    settings = app.state.settings
    settings.ai_multi_message_enabled = True
    settings.ai_three_agent_experience_enabled = True
    settings.ai_smart_orchestration_enabled = True
    settings.ai_accounting_enabled = True
    settings.proactive_enabled = True
    app.state.ai.model_override = scripted(reply("ok"))
    if journal:
        current = (await client.get("/api/v1/ai/proactive")).json()["settings"]["version"]
        response = await client.put("/api/v1/ai/proactive/settings", headers=key(),
                                    json=settings_body(journalContextEnabled=True, expectedVersion=current))
        assert response.status_code == 200, response.text
    for name in edges:
        await set_edge(client, name, True)


async def set_edge(client, name, enabled):
    view = (await client.get("/api/v1/ai/sharing")).json()
    version = next(e["version"] for e in view["edges"] if e["edge"] == name)
    response = await client.put(f"/api/v1/ai/sharing/{name}", headers=key(),
                                json={"enabled": enabled, "expectedVersion": version, "policyVersion": "sharing-v1"})
    assert response.status_code == 200, response.text
    return response


def roles(app, **models):
    """Per-role synthetic models: planner, dieuphoi, nhatky, hoatdong, nhatky:consult, hoatdong:consult."""
    app.state.ai.agent_model_overrides = {name.replace("_", ":"): model for name, model in models.items()}


async def steps(app, run_id: UUID):
    from app.ai.orchestration.models import AiOrchestrationStep

    async with app.state.database.sessions() as db:
        return (await db.scalars(select(AiOrchestrationStep).where(AiOrchestrationStep.workflow_run_id == run_id)
                                 .order_by(AiOrchestrationStep.kind, AiOrchestrationStep.ordinal))).all()


async def usage(app, run_id: UUID):
    from app.infrastructure.database.models import AiUsage

    async with app.state.database.sessions() as db:
        return await db.get(AiUsage, run_id)


def sent(model: ScriptedModel, index: int = -1) -> str:
    call_ = model.calls[index]
    return (call_["instructions"] or "") + "\n" + json.dumps(call_["input"], ensure_ascii=False)
