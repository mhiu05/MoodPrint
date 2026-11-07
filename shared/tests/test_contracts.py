import json
from dataclasses import FrozenInstanceError
from uuid import UUID

import pytest
from pydantic import ValidationError

ID = UUID("11111111-1111-4111-8111-111111111111")


def test_auth_repr_does_not_contain_claims():
    from moodprint_shared.contracts.auth import AuthContext

    auth = AuthContext(ID, None, None, '{"private":"claims-sentinel"}')
    assert "claims-sentinel" not in repr(auth)
    with pytest.raises(FrozenInstanceError):
        auth.user_id = ID


def test_dtos_are_frozen_and_use_camel_case():
    from moodprint_shared.contracts.knowledge import KnowledgeQuery

    query = KnowledgeQuery(text="tổng hợp", topK=2)
    with pytest.raises(ValidationError):
        query.top_k = 3
    assert query.model_dump(by_alias=True)["topK"] == 2
    with pytest.raises(ValidationError):
        KnowledgeQuery(text="", top_k=0)


def test_knowledge_scope_forbids_user_identity():
    from moodprint_shared.contracts.knowledge import RetrievalScope

    with pytest.raises(ValidationError):
        RetrievalScope(request_id="r", user_id=ID)


def test_memory_content_limit():
    from moodprint_shared.contracts.memory import MemoryCreate

    with pytest.raises(ValidationError):
        MemoryCreate(category="preference", content="x" * 501)


def test_timeline_unknown_never_accepts_invented_date():
    from moodprint_shared.contracts.incidents import EventCreate

    with pytest.raises(ValidationError):
        EventCreate(id=ID, when="2026-01-01", time_precision="unknown", description="synthetic")


@pytest.mark.parametrize(
    "event,data",
    [
        ("run.started", {"runId": str(ID), "conversationId": str(ID), "messageId": str(ID)}),
        ("message.delta", {"messageId": str(ID), "text": "Chào bạn"}),
        ("message.completed", {"messageId": str(ID), "content": "Chào bạn", "citations": []}),
        ("tool.started", {"callId": "c", "tool": "get_server_time", "label": "Xem giờ"}),
        ("tool.completed", {"callId": "c", "tool": "get_server_time", "ok": True}),
        (
            "approval.required",
            {
                "approvalId": str(ID),
                "tool": "save",
                "label": "Lưu",
                "preview": {},
                "expiresAt": "2026-11-07T00:00:00Z",
            },
        ),
        (
            "run.usage",
            {
                "inputTokens": 2,
                "outputTokens": 1,
                "totalTokens": 3,
                "requests": 1,
                "toolCalls": 0,
                "latencyMs": 4,
            },
        ),
        ("run.completed", {"status": "completed"}),
        ("run.failed", {"code": "run_timeout", "message": "Hết thời gian", "retryable": True}),
        ("heartbeat", {}),
    ],
)
def test_event_round_trip_json(event, data):
    from moodprint_shared.contracts.streaming import STREAM_EVENT_ADAPTER

    payload = {"event": event, "v": 1, "seq": 1, "runId": str(ID), "data": data}
    value = STREAM_EVENT_ADAPTER.validate_python(payload)
    serialized = STREAM_EVENT_ADAPTER.dump_json(value, by_alias=True)
    assert STREAM_EVENT_ADAPTER.validate_json(serialized) == value
    assert json.loads(serialized)["event"] == event


def test_tool_event_rejects_arguments():
    from moodprint_shared.contracts.streaming import STREAM_EVENT_ADAPTER

    with pytest.raises(ValidationError):
        STREAM_EVENT_ADAPTER.validate_python(
            {
                "event": "tool.started",
                "v": 1,
                "seq": 1,
                "runId": str(ID),
                "data": {"callId": "c", "tool": "t", "label": "t", "arguments": {"private": True}},
            }
        )


def test_error_contract_exposes_safe_http_metadata():
    from moodprint_shared.contracts.errors import NotFound, VersionConflict

    assert NotFound().status_code == 404
    conflict = VersionConflict(details={"latest": {"version": 2}})
    assert conflict.code == "version_conflict"
    assert conflict.details == {"latest": {"version": 2}}


def test_all_service_modules_import():
    from moodprint_shared.contracts.agent import (
        AgentServices,
        AgentToolContext,
        CompanionTurn,
        ToolPolicy,
    )
    from moodprint_shared.contracts.context import ContextBuilder, ContextBundle
    from moodprint_shared.contracts.conversations import AgentSession, ConversationService
    from moodprint_shared.contracts.evidence import EvidenceService
    from moodprint_shared.contracts.incidents import IncidentService
    from moodprint_shared.contracts.plans import ActionPlanService

    assert all(
        (
            AgentServices,
            AgentToolContext,
            CompanionTurn,
            ToolPolicy,
            AgentSession,
            ConversationService,
            ContextBuilder,
            ContextBundle,
            EvidenceService,
            IncidentService,
            ActionPlanService,
        )
    )
