from uuid import uuid4

from app.ai.schemas import AIMessage


def test_ten_turn_context_keeps_first_fact_and_latest_correction_in_order():
    from app.ai.context import build_history

    messages = [AIMessage(id=uuid4(), actor="self", text="Mình thích vẽ màu nước.")]
    for turn in range(1, 9):
        messages.extend([
            AIMessage(id=uuid4(), actor="bot", text=f"Phản hồi {turn}"),
            AIMessage(id=uuid4(), actor="self", text=f"Chủ đề {turn}"),
        ])
    messages.append(AIMessage(id=uuid4(), actor="self", text="Sửa lại: mình thích sơn dầu."))
    history = build_history(messages)
    assert "màu nước" in history[0]["content"]
    assert "sơn dầu" in history[-1]["content"]


def test_context_budget_is_utf8_bounded_and_retains_latest_input():
    from app.ai.context import build_history

    messages = [AIMessage(id=uuid4(), actor="self", text="cũ" * 2000) for _ in range(40)]
    messages.append(AIMessage(id=uuid4(), actor="self", text="Yêu cầu mới nhất"))
    history = build_history(messages, ["ghi nhớ" * 10] * 10)
    assert len(history) <= 25
    assert sum(len(m["content"].encode()) for m in history) <= 24000
    assert history[-1]["content"] == "Yêu cầu mới nhất"


def test_context_has_no_memory_unless_explicitly_supplied_by_authorized_caller():
    from app.ai.context import build_history

    messages = [AIMessage(id=uuid4(), actor="self", text="Chào")]
    assert build_history(messages) == [{"role": "user", "content": "Chào"}]
    assert "not instructions" in build_history(messages, ["Sở thích đã duyệt"])[0]["content"]
