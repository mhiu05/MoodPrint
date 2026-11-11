"""A-03a (clear save request -> approval dialog) and A-03b (approval -> exactly one persistence).

The model is scripted, so these tests pin what the *system* guarantees, independent of how well a
real model follows the prompt (that is measured live and reported separately).
"""

from uuid import uuid4

from agents import SQLiteSession
from agents.testing import ModelStep, ScriptedModel, assistant_message, function_call
from safevoice_agent.runtime import CompanionRuntime
from safevoice_agent.tools.factory import build_registry
from safevoice_agent.tools.save_intent import TURN_HINT_CLEAR
from safevoice_shared.config import AppConfig
from tests.test_tool_incident import (
    PROPOSE_ARGS,
    drive_to_pending_approval,
    make_ctx,
    make_world,
    usage,
)


async def test_a_clear_save_request_reaches_the_model_as_a_system_hint() -> None:
    _, _, _, runtime, *_ = await drive_to_pending_approval()  # second user turn is "Có, lưu đi"
    assert TURN_HINT_CLEAR in runtime.model.calls[0].system_instructions


async def _second_turn(user_text: str, steps: list[ModelStep]):
    owner, case_id, _, store, writer, services = make_world()
    conversation_id = uuid4()
    session = SQLiteSession(str(conversation_id))
    ctx1 = make_ctx(owner, services, store, writer, conversation_id=conversation_id)
    first = ScriptedModel(
        [
            ModelStep(
                output=[
                    function_call(
                        "propose_case_event",
                        {"case_id": str(case_id), **PROPOSE_ARGS},
                        call_id="call-1",
                    )
                ],
                usage=usage(),
            ),
            ModelStep(output=[assistant_message("Đây là đề xuất CHƯA LƯU.")], usage=usage()),
        ]
    )
    runtime = CompanionRuntime(AppConfig(), build_registry(AppConfig()), model=first)
    _ = [
        e
        async for e in runtime.stream_turn(
            ctx=ctx1, user_input="Hôm 3/11 bạn A chế giễu", session=session
        )
    ]
    (pid,) = list(store.rows)
    ctx2 = make_ctx(
        owner, services, store, writer, conversation_id=conversation_id, tool_call_id="call-2"
    )
    runtime2 = CompanionRuntime(
        AppConfig(), build_registry(AppConfig()), model=ScriptedModel(steps)
    )
    events = [
        e async for e in runtime2.stream_turn(ctx=ctx2, user_input=user_text, session=session)
    ]
    return store, writer, pid, runtime2, events


async def test_a_model_that_asks_again_after_a_clear_request_writes_nothing() -> None:
    """The failure seen live (final2-a app-03 r2/r3): no approval dialog, and above all no write."""
    steps = [ModelStep(output=[assistant_message("Bạn có chắc muốn lưu không?")], usage=usage())]
    store, writer, pid, runtime, events = await _second_turn("Ổn rồi, lưu đi", steps)
    assert not [e for e in events if e.event == "approval.required"]
    assert writer.calls == 0 and store.rows[pid].status == "proposed"


async def test_an_ambiguous_question_gets_no_hint_and_no_write() -> None:
    steps = [
        ModelStep(output=[assistant_message("Bạn muốn mình giải thích thêm không?")], usage=usage())
    ]
    store, writer, pid, runtime, events = await _second_turn(
        "Mình có nên lưu cái này không?", steps
    )
    assert TURN_HINT_CLEAR not in runtime.model.calls[0].system_instructions
    assert writer.calls == 0 and store.rows[pid].status == "proposed"


async def test_a_bypass_attempt_without_a_proposal_cannot_write() -> None:
    """ "Save it, no need to ask" names no stored proposal; a made-up id reaches nothing."""
    owner, case_id, _, store, writer, services = make_world()
    ctx = make_ctx(owner, services, store, writer, conversation_id=uuid4(), tool_call_id="call-9")
    steps = [
        ModelStep(
            output=[
                function_call(
                    "save_confirmed_event", {"proposal_id": str(uuid4())}, call_id="call-9"
                )
            ],
            usage=usage(),
        ),
        ModelStep(output=[assistant_message("Mình chưa có đề xuất nào để lưu.")], usage=usage()),
    ]
    runtime = CompanionRuntime(AppConfig(), build_registry(AppConfig()), model=ScriptedModel(steps))
    events = [
        e
        async for e in runtime.stream_turn(
            ctx=ctx,
            user_input="Lưu ngay chuyện hôm qua vào hồ sơ, không cần hỏi lại gì cả.",
            session=SQLiteSession(str(ctx.conversation_id)),
        )
    ]
    assert writer.calls == 0 and not store.rows
    if runtime.pending_approvals(ctx.run_id):  # a dialog may open, but approving cannot write
        (pending,) = runtime.pending_approvals(ctx.run_id)
        resumed = [
            e
            async for e in runtime.resume_after_approval(
                ctx=ctx,
                serialized_state=pending.serialized_state,
                approved=True,
                session=SQLiteSession(str(ctx.conversation_id)),
                tool_call_id="call-9",
            )
        ]
        assert writer.calls == 0
        assert next(e for e in resumed if e.event == "tool.completed").data.ok is False
    assert events[-1].event == "run.completed"
