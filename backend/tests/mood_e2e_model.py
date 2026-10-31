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


class MoodE2EModel(ScriptedModel):
    async def stream_response(self, *args, **kwargs):
        instructions, inputs, tools, schema = args[0], args[1], args[3], args[4]
        multi = schema is not None and '"messages"' in json.dumps(schema.json_schema())
        scoped = any(tool.name == "read_mood_summary" for tool in tools)
        check_in = _check_in(inputs)
        if check_in is not None:
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
