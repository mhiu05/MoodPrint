"""Allowlisted SDK events translated to MoodPrint's v1 wire contract."""

import json
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from agents.items import ToolCallItem, ToolCallOutputItem
from agents.stream_events import StreamEvent as SDKStreamEvent
from moodprint_shared.contracts.streaming import StreamEvent, make_event

from moodprint_agent.tools.registry import ToolRegistry


@dataclass(slots=True)
class EventEmitter:
    run_id: UUID
    message_id: UUID
    registry: ToolRegistry
    seq: int = 0
    _tools_by_call: dict[str, str] = field(default_factory=dict[str, str])

    def remember_call(self, call_id: str, tool: str) -> None:
        """After a resume the SDK replays only the tool output; restore the call -> tool map."""
        self._tools_by_call[call_id] = tool

    def emit(self, event: str, data: dict[str, Any]) -> StreamEvent:
        self.seq += 1
        return make_event(event, seq=self.seq, run_id=self.run_id, data=data)

    def translate(self, event: SDKStreamEvent) -> StreamEvent | None:
        if event.type == "raw_response_event":
            if event.data.type == "response.output_text.delta":
                return self.emit(
                    "message.delta", {"message_id": self.message_id, "text": event.data.delta}
                )
            return None
        if event.type != "run_item_stream_event":
            return None
        if event.name == "tool_called" and isinstance(event.item, ToolCallItem):
            call_id, name = event.item.call_id, event.item.tool_name
            if call_id is None or name is None:
                return None
            self._tools_by_call[call_id] = name
            return self.emit(
                "tool.started",
                {"call_id": call_id, "tool": name, "label": self.registry.label(name)},
            )
        if event.name == "tool_output" and isinstance(event.item, ToolCallOutputItem):
            call_id = event.item.call_id
            if call_id is None or call_id not in self._tools_by_call:
                return None
            ok = True
            if isinstance(event.item.output, str):
                try:
                    output = json.loads(event.item.output)
                    ok = not (isinstance(output, dict) and "error" in output)
                except (ValueError, TypeError):
                    pass
            return self.emit(
                "tool.completed",
                {"call_id": call_id, "tool": self._tools_by_call[call_id], "ok": ok},
            )
        return None


def encode_sse(event: StreamEvent) -> str:
    return f"event: {event.event}\ndata: {event.model_dump_json(by_alias=True)}\n\n"
