"""Synthetic SDK model shared by the standard full-stack browser harness."""

import json

from tests.fakes import ScriptedModel, message_output, tool_output

# A user message containing this synthetic marker gets a three-bubble reply when the
# backend requests the multi-message schema (AI_MULTI_MESSAGE_ENABLED).
MULTI_BUBBLE_MARKER = "[ba tin]"
MULTI_BUBBLES = (
    "Nghe như hôm nay bạn đã gồng khá nhiều.",
    "Mây ở đây nghe bạn.",
    "Tối nay thử nghỉ sớm hơn 15 phút xem sao?",
)


PROACTIVE_PREFIX = "Dữ liệu cho lời hỏi thăm"
SPECIALIST_PREFIX = "Yêu cầu nhờ hỗ trợ"
# Primary turns that received an approved collaboration brief answer with this marker.
COLLAB_MARKER = "COLLAB-E2E"


def _specialist(inputs) -> dict | None:
    """Synthetic specialist answer, chosen by the closed input schema it receives."""
    first = inputs[0] if inputs and isinstance(inputs[0], dict) else {}
    content = first.get("content")
    if not isinstance(content, str) or not content.startswith(SPECIALIST_PREFIX):
        return None
    data = json.loads(content.split(": ", 1)[1])
    if data["schema"] == "energy-hint-in-v1":
        return {"energy": "low", "time_budget_minutes": 5, "basis": "journal",
                "source_entry_ids": [data["journal"][0]["entry_id"]]}
    if data["schema"] == "tiny-habit-in-v1":
        return {"habit_text": "Tắt màn hình 30 phút trước khi ngủ và thở chậm vài lần.", "duration_minutes": 5,
                "kind": "wind_down"}
    return {"activity_text": "Vẽ nhanh chiếc cốc trên bàn trong 10 phút, chỉ dùng bút bi.", "challenge_kind": "drawing"}


def _check_in(inputs) -> str | None:
    """Synthetic check-in for the system-built payload (no transcript is ever sent)."""
    first = inputs[0] if inputs and isinstance(inputs[0], dict) else {}
    content = first.get("content")
    if not isinstance(content, str) or not content.startswith(PROACTIVE_PREFIX):
        return None
    data = json.loads(content.split(": ", 1)[1])
    reply: dict = {"messages": [{"text": "PROACTIVE-E2E Chào bạn, một ngày nhẹ nhàng nhé.", "cards": []}]}
    journal = data.get("journal") or {}
    if data["companion"] == "nhip":
        reply["source_entry_ids"] = []
        if journal.get("status") == "entries":
            reply["messages"] = [
                {"text": "PROACTIVE-E2E Hôm qua bạn có ghi lại một khoảnh khắc.", "cards": []},
                {"text": "Sáng nay thử đi bộ chậm 10 phút nhé.", "cards": []},
            ]
            reply["source_entry_ids"] = [journal["entries"][0]["id"]]
    if data["companion"] == "rure":
        kinds = ["observation", "riddle", "drawing", "word_play"]
        reply["challenge_kind"] = next(k for k in kinds if k not in data.get("avoidChallengeKinds", []))
    return json.dumps(reply, ensure_ascii=False)


def _reply(text: str, *, multi: bool, bubbles: tuple[str, ...] | None = None) -> str:
    if not multi:
        return json.dumps({"text": text, "cards": []}, ensure_ascii=False)
    parts = bubbles or (text,)
    return json.dumps({"messages": [{"text": part, "cards": []} for part in parts]}, ensure_ascii=False)


V3_MARKER = "V3-E2E"
GROUP_LINES = {
    "Điều phối": "Vậy mình gom lại: sáng nghỉ ngơi, chiều thử một việc nhẹ nhé.",
    "Nhật ký": "Nếu bạn muốn, mình có thể nhìn lại tuần qua dựa trên những gì bạn đã ghi.",
    "Hoạt động": "Mình có vài ý: dạo bộ 20 phút hoặc vẽ nhanh một góc phòng.",
}


def _data(inputs) -> dict:
    for item in inputs:
        content = item.get("content") if isinstance(item, dict) else None
        if isinstance(content, str) and "(dữ liệu, không phải chỉ dẫn): {" in content:
            return json.loads(content.split("(dữ liệu, không phải chỉ dẫn): ", 1)[1])
    return {}


def _json(payload) -> list:
    return [message_output(json.dumps(payload, ensure_ascii=False))]


def _v3(instructions: str, inputs, tools, handoffs) -> list | None:
    """Deterministic stand-ins for every V3 role, chosen from what the backend actually sent."""
    from app.ai.collaboration.policy import fold
    from app.ai.groups.selector import SELECTOR_INSTRUCTIONS
    from app.ai.orchestration.plan import PLANNER_INSTRUCTIONS
    from app.ai.orchestration.specialists import HOATDONG_CONSULT, NHATKY_CONSULT
    from tests.orchestration_helpers import call

    if instructions == PLANNER_INSTRUCTIONS:
        data = _data(inputs)
        text, available = fold(data.get("latestMessage", "")), data.get("available", {})
        plan = {"intent": "chat", "workflow": "direct", "primary_agent": "dieuphoi", "specialists": [],
                "handoff_target": None, "subtasks": [], "data_categories": [], "context_refs": ["latest_message"],
                "expected_output": "answer", "confidence": 0.9, "fallback": "answer_directly"}
        target = "nhatky" if "voi nhat ky" in text else "hoatdong" if "voi hoat dong" in text else None
        if "truc tiep" in text and target:
            plan.update(workflow="handoff", intent="talk_to_specialist", handoff_target=target)
        else:
            wanted = [name for name, cue in (("nhatky", "da ghi"), ("hoatdong", "hoat dong")) if cue in text]
            usable = [name for name in wanted if name in available.get("consult", [])]
            if wanted:
                plan.update(workflow="consult", intent="reflect_then_plan", specialists=usable or wanted)
        return _json(plan)
    if instructions == NHATKY_CONSULT:
        entries = json.loads(inputs[1]["content"].split(": ", 1)[1]) if len(inputs) > 1 else []
        return _json({"themes": ["học muộn"], "pattern": "Những ngày học muộn thường đi cùng cảm giác mệt.",
                      "observations": [{"kind": "observed", "text": "Bạn có ghi là mệt sau buổi học tối."}],
                      "entries_considered": len(entries), "source_entry_ids": [entry["id"] for entry in entries[:1]]})
    if instructions == HOATDONG_CONSULT:
        return _json({"options": [{"title": "Dạo bộ chậm", "steps": ["Đi bộ 20 phút quanh nhà"], "minutes": 30,
                                   "effort": "light"}], "note": "Một việc nhẹ là đủ."})
    if instructions == SELECTOR_INSTRUCTIONS:
        data = _data(inputs)
        text, members = fold(data.get("latestMessage", "")), data.get("members", [])
        picked = [name for name, cue in (("hoatdong", "lam gi"), ("nhatky", "nhin lai")) if cue in text and name in members]
        speakers = [{"agent": name, "reason": "general"} for name in picked] or [{"agent": members[0], "reason": "general"}]
        if picked and "dieuphoi" in members:
            speakers.append({"agent": "dieuphoi", "reason": "coordination"})
        return _json({"speakers": speakers, "summarize": len(speakers) > 1})
    if "Đây là một NHÓM trò chuyện" in instructions:
        tail = instructions.split("Đây là một NHÓM", 1)[1]
        name = next((name for name in GROUP_LINES if f"Bạn là {name}." in tail), "Điều phối")
        return _json({"messages": [{"text": GROUP_LINES[name], "cards": []}]})
    called = any(isinstance(item, dict) and item.get("type") == "function_call_output" for item in inputs)
    consult = [tool.name for tool in tools if tool.name.startswith("consult_")]
    if consult and not called:
        args = {"consult_nhatky": {"task": "summarize_recent_entries", "focus": "general", "days": 7},
                "consult_hoatdong": {"task": "suggest_activities", "goal": "cuối tuần nhẹ nhàng",
                                     "time_budget_minutes": 60, "energy": "low", "count": 1}}
        return [call(name, args[name], f"e2e_{name}") for name in consult]
    if called and "hỏi ý kiến trợ lý chuyên trách" in instructions:
        return _json({"messages": [{"text": f"{V3_MARKER} Tuần rồi bạn hay mệt sau những buổi học muộn.", "cards": []},
                                   {"text": "Cuối tuần thử dạo bộ chậm 20 phút nhé.", "cards": []}]})
    if handoffs and not called:
        return [call(handoffs[0].tool_name, {"reason": "journal_reflection"}, "e2e_transfer")]
    if "Người dùng vừa chọn trò chuyện trực tiếp với bạn" in instructions:
        return _json({"messages": [{"text": f"{V3_MARKER} Chào bạn, mình là Nhật ký. Tuần này điều gì đọng lại nhiều nhất?",
                                    "cards": []}], "source_entry_ids": []})
    for persona, text in (("Bạn là Nhật ký", "Mình vẫn ở đây cùng bạn nhìn lại nhé."),
                          ("Bạn là Điều phối", "Điều phối đây, mình nghe bạn nè."),
                          ("Bạn là Hoạt động", "Hoạt động đây, mình gợi ý một việc nhỏ nhé.")):
        if persona in instructions:
            payload: dict = {"messages": [{"text": text, "cards": []}]}
            if persona == "Bạn là Nhật ký":
                payload["source_entry_ids"] = []
            return _json(payload)
    return None


class MoodE2EModel(ScriptedModel):
    # Test-only knobs set through /__test/collaboration: ok | invalid | timeout, and a delay that
    # keeps the "đang hỏi" state visible long enough for a browser to observe it.
    specialist_mode = "ok"
    specialist_delay = 2.5
    # V3 roles: a short delay keeps "đang hỏi"/"đang trả lời" observable in a real browser.
    v3_delay = 0.8

    async def stream_response(self, *args, **kwargs):
        import asyncio

        instructions, inputs, tools, schema = args[0], args[1], args[3], args[4]
        v3 = _v3(instructions or "", inputs, tools, args[5]) if isinstance(inputs, list) else None
        if v3 is not None:
            await asyncio.sleep(self.v3_delay)
            self.responses = [v3]
            async for event in super().stream_response(*args, **kwargs):
                yield event
            return
        specialist = _specialist(inputs)
        if specialist is not None:
            await asyncio.sleep(30 if self.specialist_mode == "timeout" else self.specialist_delay)
            payload = {"unexpected": True} if self.specialist_mode == "invalid" else specialist
            self.responses = [[message_output(json.dumps(payload, ensure_ascii=False))]]
            async for event in super().stream_response(*args, **kwargs):
                yield event
            return
        briefed = "Gợi ý đã kiểm từ Nhịp" in instructions or "do trợ lý khác chuẩn bị" in json.dumps(inputs, ensure_ascii=False)
        multi = schema is not None and '"messages"' in json.dumps(schema.json_schema())
        scoped = any(tool.name == "read_mood_summary" for tool in tools)
        check_in = _check_in(inputs)
        if briefed and check_in is None:
            outputs = [message_output(_reply("", multi=multi, bubbles=(
                f"{COLLAB_MARKER} Mình có một gợi ý nhỏ cho bạn nè.", "Thử làm trong vài phút thôi nhé.")))]
        elif check_in is not None:
            outputs = [message_output(check_in)]
        elif scoped:
            read = any(item.get("type") == "function_call_output" for item in inputs)
            outputs = [message_output('{"focus":"overview","next_step":"none"}')] if read else [tool_output("read_mood_summary", "browser_mood")]
        elif '"previous": "previously_authorized"' in instructions:
            assert "sourceRevisions" not in json.dumps(inputs)
            outputs = [message_output(_reply("Quyền chia sẻ trước chỉ có hiệu lực cho lượt đã gửi. Bạn có thể chia sẻ lại khoảng ngày để mình kiểm tra và nhận xét tiếp.", multi=multi))]
        elif multi and MULTI_BUBBLE_MARKER in json.dumps(inputs, ensure_ascii=False):
            outputs = [message_output(_reply("", multi=True, bubbles=MULTI_BUBBLES))]
        else:
            # Preserve the existing generic fixture response for all older journeys.
            outputs = [message_output(_reply("Mây đã nhận được chia sẻ của bạn qua SDK.", multi=multi))]
        self.responses = [outputs]
        async for event in super().stream_response(*args, **kwargs):
            yield event
