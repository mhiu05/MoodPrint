"""SDK-compatible synthetic models for tests; these never contact a provider."""

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from agents import Model
from agents.items import ModelResponse, TResponseStreamEvent
from openai.types.responses import (
    Response,
    ResponseCompletedEvent,
    ResponseFunctionToolCall,
    ResponseOutputMessage,
    ResponseOutputText,
    ResponseTextDeltaEvent,
)
from openai.types.responses.response_output_item import ResponseOutputItem


def message_output(text: str) -> ResponseOutputMessage:
    return ResponseOutputMessage(
        id="message_test",
        content=[ResponseOutputText(annotations=[], text=text, type="output_text")],
        role="assistant",
        status="completed",
        type="message",
    )


def tool_output(name: str, identifier: str) -> ResponseFunctionToolCall:
    return ResponseFunctionToolCall(
        id=f"function_{identifier}",
        call_id=identifier,
        name=name,
        arguments="{}",
        type="function_call",
        status="completed",
    )


def completed_response(outputs: list[ResponseOutputItem]) -> Response:
    return Response(
        id="response_test",
        created_at=0,
        model="test-only",
        object="response",
        output=outputs,
        parallel_tool_calls=False,
        tool_choice="auto",
        tools=[],
        status="completed",
    )


class ScriptedModel(Model):
    def __init__(self, responses: list[list[ResponseOutputItem]], *, hold: bool = False):
        self.responses = responses
        self.calls: list[dict[str, Any]] = []
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.hold = hold
        self.cancelled = False
        self.stream_finished = False

    async def get_response(self, *args: Any, **kwargs: Any) -> ModelResponse:
        raise AssertionError("The application must use the SDK streaming path")

    async def stream_response(
        self, *args: Any, **kwargs: Any
    ) -> AsyncIterator[TResponseStreamEvent]:
        self.calls.append(
            {
                "instructions": args[0],
                "input": args[1],
                "settings": args[2],
                "tools": args[3],
                "output_schema": args[4],
                "handoffs": args[5],
                "tracing": args[6],
                **kwargs,
            }
        )
        self.started.set()
        try:
            if self.hold:
                await self.release.wait()
            outputs = self.responses[min(len(self.calls) - 1, len(self.responses) - 1)]
            yield ResponseTextDeltaEvent(
                content_index=0,
                delta="UNVALIDATED-RAW-CANARY",
                item_id="message_test",
                logprobs=[],
                output_index=0,
                sequence_number=0,
                type="response.output_text.delta",
            )
            yield ResponseCompletedEvent(
                response=completed_response(outputs), sequence_number=1, type="response.completed"
            )
            self.stream_finished = True
        except asyncio.CancelledError:
            self.cancelled = True
            raise


def make_test_model(text: str) -> ScriptedModel:
    return ScriptedModel(
        [[message_output(json.dumps({"text": text, "cards": []}, ensure_ascii=False))]]
    )
class FakeEmbedder:
    """Deterministic synthetic vectors; never a quality claim about real embeddings."""

    def __init__(self, dimensions=1024, synonyms=None, *, delay=0, error=None):
        import asyncio

        self.dimensions = dimensions
        self.synonyms = synonyms or {"kiệt sức": "mệt", "rã rời": "mệt", "lo lắng": "lo",
                                    "thư thái": "bình yên", "bồn chồn": "lo", "người thân": "gia đình",
                                    "vận động": "chạy bộ", "áp lực thời gian": "hạn chót"}
        self.delay, self.error = delay, error
        self.calls = 0
        self.started = asyncio.Event()

    async def embed(self, text, input_type):
        import asyncio
        import hashlib
        import math
        import re
        import unicodedata

        self.calls += 1
        self.started.set()
        if isinstance(self.delay, asyncio.Event):
            await self.delay.wait()
        elif self.delay:
            await asyncio.sleep(self.delay)
        if self.error:
            raise self.error
        normalized = unicodedata.normalize("NFC", text).casefold()
        if input_type == "document" and "\n\n" in normalized:
            # Toy model ignores the shared metadata header; it measures plumbing.
            normalized = normalized.split("\n\n", 1)[1]
        for source, target in self.synonyms.items():
            normalized = normalized.replace(source, target)
        vector = [0.0] * self.dimensions
        for token in re.findall(r"\w+", normalized):
            index = int.from_bytes(hashlib.sha256(token.encode()).digest()[:4], "big") % self.dimensions
            vector[index] += 1
        if not any(vector):
            vector[0] = 1
        norm = math.sqrt(sum(value * value for value in vector))
        return [value / norm for value in vector]
