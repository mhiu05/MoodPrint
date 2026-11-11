"""I-AG-50…60: approved memory is selective, deletable, shared across the owner's conversations,
isolated between users and durable; the agent can only ever create candidates.

The model is scripted; its recorded instructions show exactly what a turn was allowed to see.
"""

from typing import Any
from uuid import uuid4

import pytest
from agents.testing import ModelStep, ScriptedModel, assistant_message, function_call
from agents.usage import Usage
from app.agent_gateway.sse import RunStream, produce
from app.modules.conversations.service import ConversationService
from app.modules.incidents.schemas import CaseCreate, EventWrite
from app.modules.incidents.service import IncidentService
from app.modules.memory.service import MemoryService
from safevoice_agent.runtime import CompanionRuntime
from safevoice_agent.tools.factory import build_registry
from safevoice_shared.config import AppConfig
from safevoice_shared.contracts.memory import CandidateDecision, MemoryCandidateCreate, MemoryCreate
from safevoice_shared.testing.knowledge_fixture import FixtureKnowledgeRetriever
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


def answer(message: str = "Mình nghe đây.") -> ModelStep:
    return ModelStep(output=[assistant_message(message)], usage=USAGE)


async def turn(engine: Any, auth: Any, conversation_id: Any, content: str, *steps: ModelStep):
    model = ScriptedModel(list(steps) or [answer()])
    runtime = CompanionRuntime(CFG, build_registry(CFG), model=model)
    service = ConversationService(engine, CFG)
    handle = await service.begin_turn(auth, conversation_id, uuid4(), content)
    await produce(
        knowledge=FixtureKnowledgeRetriever(),
        stream=RunStream(),
        runtime=runtime,
        service=service,
        auth=auth,
        turn=handle,
        request_id="it",
        content=content,
    )
    return model


async def new_conversation(engine: Any, auth: Any):
    return (await ConversationService(engine, CFG).create(auth, uuid4(), "Thử"))["id"]


def seen(model: ScriptedModel) -> str:
    return model.calls[0].system_instructions or ""


async def count(admin: Any, sql: str, **params: Any) -> int:
    async with admin.connect() as conn:
        return (await conn.execute(text(sql), params)).scalar_one()


async def test_an_approved_memory_appears_only_when_the_message_is_about_it(db_engine, identities):
    a, _ = identities
    await MemoryService(db_engine, CFG).create(
        a, MemoryCreate(category="preference", content="Mình thích được trả lời ngắn gọn")
    )
    conversation = await new_conversation(db_engine, a)
    related = await turn(db_engine, a, conversation, "Bạn hãy trả lời ngắn gọn giúp mình")
    unrelated = await turn(db_engine, a, conversation, "Hôm nay trời mưa to quá")
    assert "Mình thích được trả lời ngắn gọn" in seen(related)
    assert "[đã duyệt" in seen(related)  # labelled as something the user approved
    assert "Mình thích được trả lời ngắn gọn" not in seen(unrelated)  # no "include everything"


async def test_deleting_a_memory_removes_it_from_the_very_next_turn(db_engine, identities):
    a, _ = identities
    memory = MemoryService(db_engine, CFG)
    saved = await memory.create(
        a, MemoryCreate(category="preference", content="Mình thích đọc truyện tranh buổi tối")
    )
    conversation = await new_conversation(db_engine, a)
    before = await turn(db_engine, a, conversation, "Gợi ý truyện tranh cho mình nhé")
    assert "truyện tranh buổi tối" in seen(before)
    await memory.delete(a, saved.id)
    after = await turn(db_engine, a, conversation, "Gợi ý truyện tranh cho mình nhé")
    assert "truyện tranh buổi tối" not in seen(after)


async def test_a_memory_approved_from_one_conversation_is_available_in_another(
    db_engine, identities
):
    a, _ = identities
    memory = MemoryService(db_engine, CFG)
    first = await new_conversation(db_engine, a)
    candidate = await memory.propose(
        a,
        MemoryCandidateCreate(
            category="support_person",
            content="Mình tin cô chủ nhiệm hơn ai hết",
            source_conversation_id=first,
        ),
    )
    # Pending is not memory: nothing is shown before the user decides.
    second = await new_conversation(db_engine, a)
    pending = await turn(db_engine, a, second, "Mình nên nhờ ai là cô chủ nhiệm hay ai khác")
    assert "tin cô chủ nhiệm" not in seen(pending)
    await memory.decide(a, candidate.id, CandidateDecision(decision="approve"))
    approved = await turn(db_engine, a, second, "Mình nên nhờ ai là cô chủ nhiệm hay ai khác")
    assert "tin cô chủ nhiệm" in seen(approved)


async def test_another_users_memory_never_reaches_the_prompt(db_engine, identities):
    a, b = identities
    await MemoryService(db_engine, CFG).create(
        b, MemoryCreate(category="preference", content="Bí mật của người khác về món cà ri")
    )
    conversation = await new_conversation(db_engine, a)
    model = await turn(db_engine, a, conversation, "Bí mật về món cà ri là gì")
    assert "Bí mật của người khác" not in seen(model)


async def test_memory_is_durable_across_a_restart(db_engine, identities):
    a, _ = identities
    await MemoryService(db_engine, CFG).create(
        a, MemoryCreate(category="goal", content="Mục tiêu của mình là dám phát biểu trước lớp")
    )
    fresh = create_async_engine(local_value("TEST_DATABASE_URL"), pool_size=2, hide_parameters=True)
    try:  # a brand-new engine and service stand in for a restarted process
        restarted = await MemoryService(fresh, CFG).list(a)
        assert [m.content for m in restarted] == ["Mục tiêu của mình là dám phát biểu trước lớp"]
        conversation = (
            await ConversationService(fresh, CFG).create(a, uuid4(), "Sau khi khởi động lại")
        )["id"]
        model = await turn(fresh, a, conversation, "Mục tiêu phát biểu trước lớp của mình thế nào")
        assert "dám phát biểu trước lớp" in seen(model)
    finally:
        await fresh.dispose()


async def test_the_agent_can_only_propose_and_unsafe_candidates_are_refused(
    db_engine, identities, admin
):
    a, _ = identities
    conversation = await new_conversation(db_engine, a)
    good = {"category": "preference", "content": "Mình thích được hỏi từng bước một"}
    bad = {"category": "context", "content": "Bạn Lan đã đánh mình hôm 3/11 ở sân trường"}
    model = await turn(
        db_engine,
        a,
        conversation,
        "Hãy ghi nhớ giúp mình",
        ModelStep(output=[function_call("propose_memory", good, call_id="m1")], usage=USAGE),
        answer("Mình đã đề xuất, bạn duyệt nhé."),
    )
    assert model.remaining_steps == 0
    assert (
        await count(admin, "SELECT count(*) FROM app.user_memories WHERE owner_id=:o", o=a.user_id)
        == 0
    )
    candidates = await count(
        admin,
        "SELECT count(*) FROM app.memory_candidates WHERE owner_id=:o AND status='pending' "
        "AND source_kind='agent_proposed'",
        o=a.user_id,
    )
    assert candidates == 1

    conversation2 = await new_conversation(db_engine, a)
    await turn(
        db_engine,
        a,
        conversation2,
        "Ghi nhớ chuyện này",
        ModelStep(output=[function_call("propose_memory", bad, call_id="m2")], usage=USAGE),
        answer("Mình sẽ không ghi nhớ chuyện sự việc."),
    )
    total = await count(
        admin, "SELECT count(*) FROM app.memory_candidates WHERE owner_id=:o", o=a.user_id
    )
    assert total == 1  # the incident-style / named-person candidate never reached the table


async def test_a_linked_case_shows_up_as_a_headline_only(db_engine, identities, admin):
    a, _ = identities
    case = await IncidentService(db_engine).create(
        a,
        CaseCreate(
            id=uuid4(),
            title="Chuyện nhóm chat lớp 8A",
            summary="Tóm tắt riêng tư không được lộ ra ngoài đầu mục.",
            first_event=EventWrite(
                id=uuid4(),
                description="Chi tiết sự kiện bí mật không được nằm trong ngữ cảnh",
                time_precision="unknown",
                when="",
            ),
        ),
    )
    conversation = await new_conversation(db_engine, a)
    async with admin.begin() as conn:
        await conn.execute(
            text("UPDATE app.conversations SET linked_case_id=:c WHERE id=:id"),
            {"c": case.id, "id": conversation},
        )
    model = await turn(db_engine, a, conversation, "Mình nên làm gì tiếp")
    instructions = seen(model)
    assert "Chuyện nhóm chat lớp 8A" in instructions and 'events\\":1' in instructions
    assert "bí mật không được nằm" not in instructions
    assert "Tóm tắt riêng tư" not in instructions
