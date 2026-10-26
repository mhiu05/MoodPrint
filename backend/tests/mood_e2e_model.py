"""Synthetic SDK model shared by the standard full-stack browser harness."""

import json

from tests.fakes import ScriptedModel, message_output, tool_output


class MoodE2EModel(ScriptedModel):
    async def stream_response(self, *args, **kwargs):
        instructions, inputs, tools = args[0], args[1], args[3]
        scoped = any(tool.name == "read_mood_summary" for tool in tools)
        if scoped:
            read = any(item.get("type") == "function_call_output" for item in inputs)
            outputs = [message_output('{"focus":"overview","next_step":"none"}')] if read else [tool_output("read_mood_summary", "browser_mood")]
        elif '"previous": "previously_authorized"' in instructions:
            assert "sourceRevisions" not in json.dumps(inputs)
            outputs = [message_output(json.dumps({"text": "Quyền chia sẻ trước chỉ có hiệu lực cho lượt đã gửi. Bạn có thể chia sẻ lại khoảng ngày để mình kiểm tra và nhận xét tiếp.", "cards": []}, ensure_ascii=False))]
        else:
            # Preserve the existing generic fixture response for all older journeys.
            outputs = [message_output(json.dumps({"text": "Mây đã nhận được chia sẻ của bạn qua SDK.", "cards": []}, ensure_ascii=False))]
        self.responses = [outputs]
        async for event in super().stream_response(*args, **kwargs):
            yield event
