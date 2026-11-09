"""I-AG-90…100: practice sessions on PostgreSQL. Only the model is scripted."""

import asyncio
from dataclasses import replace
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest
from agents.testing import ModelStep, ScriptedModel, assistant_message
from agents.usage import Usage
from app.agent_gateway.sse import RunStream, produce
from app.core.errors import ApiError
from app.modules.conversations.service import ConversationService
from app.modules.incidents.schemas import CaseCreate
from app.modules.incidents.service import IncidentService
from app.modules.roleplay.schemas import RoleplayCreate
from app.modules.roleplay.service import RoleplayService
from moodprint_agent.roleplay.models import Rephrasing, RoleplayFeedback
from moodprint_agent.runtime import CompanionRuntime
from moodprint_agent.tools.factory import build_registry
from moodprint_shared.config import AppConfig
from moodprint_shared.contracts.errors import NotFound
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from backend.tests.integration.conftest import local_value

pytestmark = pytest.mark.integration
CFG = AppConfig()
USAGE = Usage(requests=1, input_tokens=5, output_tokens=5, total_tokens=10)


@pytest.fixture
async def admin():
    engine = create_async_engine(local_value("TEST_ADMIN_DATABASE_URL"), hide_parameters=True)
    try:
        yield engine
    finally:
        await engine.dispose()


def body(**changes: Any) -> RoleplayCreate:
    base: dict[str, Any] = {
        "id": uuid4(),
        "role": "teacher",
        "scenario_key": "teacher-group-chat",
        "user_goal": "Nói rõ chuyện nhóm chat.",
        "difficulty": 2,
    }
    base.update(changes)
    return RoleplayCreate(**base)


def runtime_for(model: ScriptedModel, cfg: AppConfig = CFG) -> CompanionRuntime:
    return CompanionRuntime(cfg, build_registry(cfg), model=model)


def scripted(count: int) -> ScriptedModel:
    return ScriptedModel(
        [
            ModelStep(output=[assistant_message(f"Cô nghe em ({n})")], usage=USAGE)
            for n in range(count)
        ]
    )


async def say(service, runtime, auth, conversation_id, text_: str, **kw: Any):
    turn = await service.begin_turn(auth, conversation_id, uuid4(), text_, **kw)
    stream = RunStream()
    await produce(
        stream=stream,
        runtime=runtime,
        service=service,
        auth=auth,
        turn=turn,
        request_id="it",
        content=text_,
    )
    return turn


class FakeClient:
    def __init__(self, feedback: RoleplayFeedback, delay: float = 0) -> None:
        self.calls, self._feedback, self._delay = 0, feedback, delay
        self.responses = SimpleNamespace(parse=self._parse)

    async def _parse(self, **kwargs: Any) -> Any:
        self.calls += 1
        assert kwargs["store"] is False and "max_output_tokens" in kwargs
        if self._delay:
            await asyncio.sleep(self._delay)
        return SimpleNamespace(
            output_parsed=self._feedback,
            usage=SimpleNamespace(input_tokens=120, output_tokens=80, total_tokens=200),
        )


def feedback() -> RoleplayFeedback:
    return RoleplayFeedback(
        summary="Bạn mô tả khá rõ.",
        strengths=["Bạn nói rõ chuyện xảy ra trong nhóm chat"],
        suggestions=["Nói cụ thể điều bạn muốn cô giúp"],
        rephrasings=[
            Rephrasing(original="Em muốn nhờ cô", better="Em nhờ cô nói chuyện với lớp", why="rõ"),
            Rephrasing(original="điều chưa từng nói", better="...", why="bịa"),
        ],
        follow_ups=["Luyện kịch bản nói với bố/mẹ"],
        safety_note=None,
    )


async def stored(admin, sql: str, **params: Any):
    async with admin.connect() as conn:
        return (await conn.execute(text(sql), params)).mappings().all()


async def test_create_is_idempotent_and_reusing_the_id_differently_is_a_conflict(
    db_engine, identities
):
    a, _ = identities
    service = RoleplayService(db_engine, CFG)
    request = body()
    first = await service.create(a, request, age_band="13-15", case_exists=False)
    again = await service.create(a, request, age_band="13-15", case_exists=False)
    assert again.id == first.id and again.conversation_id == first.conversation_id
    assert first.status == "active" and first.turn_count == 0 and first.max_turns == 30
    assert first.scenario_title and first.feedback is None and not first.use_case_context
    with pytest.raises(ApiError) as caught:
        await service.create(
            a, body(id=request.id, difficulty=3), age_band="13-15", case_exists=False
        )
    assert (caught.value.code, caught.value.status_code) == ("request_conflict", 409)


@pytest.mark.parametrize(
    "changes",
    [
        {"scenario_key": "no-such-scenario"},
        {"role": "parent"},  # scenario belongs to the teacher
        {"use_case_context": True},  # opted in without choosing a case
        {"linked_case_id": uuid4()},  # a case without opting in
    ],
)
async def test_invalid_scenario_role_or_case_options_are_refused(db_engine, identities, changes):
    a, _ = identities
    with pytest.raises(ApiError) as caught:
        await RoleplayService(db_engine, CFG).create(
            a, body(**changes), age_band=None, case_exists=False
        )
    assert caught.value.status_code == 422


async def test_turns_use_the_partner_mode_have_no_tools_and_are_counted(
    db_engine, identities, admin
):
    a, _ = identities
    roleplay = RoleplayService(db_engine, CFG)
    session = await roleplay.create(a, body(), age_band="13-15", case_exists=False)
    model = scripted(3)
    runtime = runtime_for(model)
    conversations = ConversationService(db_engine, CFG)
    for n in range(3):
        await say(conversations, runtime, a, session.conversation_id, f"Em chào cô, lượt {n}")
    assert len(model.calls) == 3
    for call in model.calls:
        assert call.tools == []  # no tool of any kind reaches the practice partner
        assert "scenario_data" in (call.system_instructions or "")
        assert "context_data" not in (call.system_instructions or "")  # no memory/case context
    read = await roleplay.get(a, session.id)
    assert read.turn_count == 3 and read.status == "active"
    messages = await stored(
        admin,
        "SELECT role FROM app.messages WHERE conversation_id=:c ORDER BY created_at",
        c=session.conversation_id,
    )
    assert [m["role"] for m in messages] == ["user", "assistant"] * 3
    # An ordinary chat is not affected: the same runtime still has its tools there.
    assert runtime.registry.names()


async def test_the_turn_limit_and_an_ended_session_are_conflicts_without_a_model_call(
    db_engine, identities
):
    a, _ = identities
    cfg = replace(CFG, agent=replace(CFG.agent, roleplay_max_turns=2))
    roleplay = RoleplayService(db_engine, cfg)
    session = await roleplay.create(a, body(), age_band=None, case_exists=False)
    model = scripted(2)
    conversations = ConversationService(db_engine, cfg)
    for n in range(2):
        await say(conversations, runtime_for(model, cfg), a, session.conversation_id, f"Lượt {n}")
    with pytest.raises(ApiError) as caught:
        await conversations.begin_turn(a, session.conversation_id, uuid4(), "Lượt thứ ba")
    assert (caught.value.code, caught.value.status_code) == ("roleplay_turn_limit", 409)
    assert caught.value.details == {"max_turns": 2}
    await roleplay.abandon(a, session.id)
    with pytest.raises(ApiError) as ended:
        await conversations.begin_turn(a, session.conversation_id, uuid4(), "Còn nói được không?")
    assert ended.value.code == "roleplay_ended"
    assert len(model.calls) == 2


async def test_danger_locks_the_session_and_the_model_is_never_asked(db_engine, identities, admin):
    a, _ = identities
    roleplay = RoleplayService(db_engine, CFG)
    session = await roleplay.create(a, body(), age_band=None, case_exists=False)
    model = scripted(1)
    conversations = ConversationService(db_engine, CFG)
    await say(conversations, runtime_for(model), a, session.conversation_id, "Em muốn tự tử")
    assert model.calls == ()
    assert (await roleplay.get(a, session.id)).safety_locked is True
    # The next, harmless-looking message still does not resume the persona.
    await say(conversations, runtime_for(model), a, session.conversation_id, "Thôi không sao đâu")
    assert model.calls == ()
    replies = await stored(
        admin,
        "SELECT content FROM app.messages WHERE conversation_id=:c AND role='assistant'",
        c=session.conversation_id,
    )
    assert len(replies) == 2 and all("111" in r["content"] for r in replies)


async def test_feedback_is_generated_once_grounded_and_idempotent(db_engine, identities, admin):
    a, _ = identities
    client = FakeClient(feedback(), delay=0.2)
    roleplay = RoleplayService(db_engine, CFG, cast(Any, client))
    session = await roleplay.create(a, body(), age_band=None, case_exists=False)
    with pytest.raises(ApiError) as empty:
        await roleplay.complete(a, session.id)
    assert empty.value.code == "roleplay_no_turns" and client.calls == 0
    conversations = ConversationService(db_engine, CFG)
    await say(
        conversations,
        runtime_for(scripted(1)),
        a,
        session.conversation_id,
        "Dạ, em muốn nhờ cô giúp",
    )
    results = await asyncio.gather(*(roleplay.complete(a, session.id) for _ in range(3)))
    again = await roleplay.complete(a, session.id)
    assert client.calls == 1  # concurrent and repeated completions pay once
    for done in (*results, again):
        assert done.status == "completed" and done.feedback is not None
    assert [r.original for r in again.feedback.rephrasings] == ["Em muốn nhờ cô"]  # type: ignore[union-attr]
    audit = await stored(
        admin,
        "SELECT count(*) AS n FROM app.audit_events WHERE entity_id=:id "
        "AND action='roleplay.feedback_generated'",
        id=session.id,
    )
    assert audit[0]["n"] == 1
    with pytest.raises(ApiError) as ended:
        await conversations.begin_turn(a, session.conversation_id, uuid4(), "Thêm một câu")
    assert ended.value.code == "roleplay_ended"


async def test_another_user_cannot_read_finish_leave_or_speak_in_the_session(db_engine, identities):
    a, b = identities
    roleplay = RoleplayService(db_engine, CFG, cast(Any, FakeClient(feedback())))
    session = await roleplay.create(a, body(), age_band=None, case_exists=False)
    for call in (roleplay.get, roleplay.complete, roleplay.abandon):
        with pytest.raises(NotFound):
            await call(b, session.id)
    assert await roleplay.list(b) == []
    with pytest.raises(NotFound):
        await ConversationService(db_engine, CFG).begin_turn(
            b, session.conversation_id, uuid4(), "Cho mình vào với"
        )
    assert (await roleplay.get(a, session.id)).turn_count == 0


async def test_the_case_summary_reaches_the_partner_only_when_the_user_opted_in(
    db_engine, identities
):
    a, _ = identities
    case = await IncidentService(db_engine).create(
        a, CaseCreate(id=uuid4(), title="Hồ sơ nhóm chat lớp", summary="Bị chế giễu trong nhóm.")
    )
    roleplay = RoleplayService(db_engine, CFG)
    plain = await roleplay.create(a, body(), age_band=None, case_exists=False)
    opted = await roleplay.create(
        a,
        body(use_case_context=True, linked_case_id=case.id),
        age_band=None,
        case_exists=True,
    )
    model = scripted(2)
    conversations = ConversationService(db_engine, CFG)
    await say(conversations, runtime_for(model), a, plain.conversation_id, "Em chào cô")
    await say(conversations, runtime_for(model), a, opted.conversation_id, "Em chào cô")
    without, with_case = (call.system_instructions or "" for call in model.calls)
    assert "Hồ sơ nhóm chat lớp" not in without and "case_summary_user_allowed" not in without
    assert "Hồ sơ nhóm chat lớp" in with_case and "case_summary_user_allowed" in with_case
