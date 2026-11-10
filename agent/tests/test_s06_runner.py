"""Extraction mechanics with an injected synthetic provider, never live quality evidence."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def assessment(urgency="none"):
    return {
        "observed_facts": [],
        "user_reported_facts": [],
        "possible_patterns": [],
        "uncertainties": [],
        "urgency": urgency,
    }


class SyntheticProvider:
    def __init__(self, *, chunks=None, tool=True, classified=None, duplicate_tool=False):
        self.chunks = chunks
        self.tool = tool
        self.classified = assessment() if classified is None else classified
        self.duplicate_tool = duplicate_tool
        self.requests = []
        self.classifications = []

    async def stream(self, request):
        from evals.s06_runner import ProviderEvent

        self.requests.append(request)
        if self.chunks is not None:
            chunks = self.chunks
        elif request.mechanism == "a_json_stream":
            chunks = [json.dumps({"reply": "Mình nghe bạn.", **assessment()})]
        else:
            chunks = ["Mình nghe ", "bạn."]
        for chunk in chunks:
            yield ProviderEvent("text_delta", text=chunk)
        if request.mechanism == "b_closing_tool" and self.tool:
            yield ProviderEvent(
                "tool_call", tool_name="report_turn_assessment", arguments=assessment()
            )
            if self.duplicate_tool:
                yield ProviderEvent(
                    "tool_call", tool_name="report_turn_assessment", arguments=assessment()
                )

    async def classify(self, request):
        self.classifications.append(request)
        return self.classified


def slot_for(mechanism):
    from evals.s06_mechanisms import build_plan

    plan = build_plan(repeat=1)
    return plan, next(slot for slot in plan["slots"] if slot["mechanism"] == mechanism)


@pytest.mark.asyncio
async def test_json_reply_stream_decodes_escapes_before_the_assessment_finishes():
    from evals.s06_runner import ProviderEvent, run_slot

    plan, slot = slot_for("a_json_stream")
    deltas = []

    class SplitJSONProvider(SyntheticProvider):
        async def stream(self, request):
            self.requests.append(request)
            yield ProviderEvent("text_delta", text='{"reply":"Xin \\u0063h\\u00e0o \\ud83d')
            assert deltas == ["Xin chào "]  # no lone high surrogate escapes into the stream
            yield ProviderEvent("text_delta", text="\\ude00\\nBạn")
            assert "".join(deltas) == "Xin chào 😀\nBạn"
            yield ProviderEvent(
                "text_delta", text='",' + json.dumps(assessment(), ensure_ascii=False)[1:]
            )

    times = iter([0.0, 0.125, 0.5])
    provider = SplitJSONProvider()
    row = await run_slot(plan, slot, provider, on_delta=deltas.append, clock=lambda: next(times))
    assert row["status"] == "completed"
    assert row["reply"] == "Xin chào 😀\nBạn"
    assert row["ttft_ms"] == 125
    assert row["structured"]["urgency"] == "none"
    assert provider.requests[0].output_schema["properties"]["reply"]["type"] == "string"


@pytest.mark.asyncio
async def test_json_assessment_accepts_the_camel_case_fields_in_the_actual_sdk_schema():
    from evals.s06_runner import run_slot

    plan, slot = slot_for("a_json_stream")
    provider = SyntheticProvider(
        chunks=[
            json.dumps(
                {
                    "reply": "Hello",
                    "observedFacts": [],
                    "userReportedFacts": [],
                    "possiblePatterns": [],
                    "uncertainties": [],
                    "urgency": "none",
                }
            )
        ]
    )
    row = await run_slot(plan, slot, provider)
    assert row["status"] == "completed"
    assert row["structured"]["observed_facts"] == []


@pytest.mark.asyncio
async def test_closing_assessment_tool_is_read_only_budget_exempt_and_invoked_once():
    from evals.s06_runner import run_slot

    plan, slot = slot_for("b_closing_tool")
    provider, deltas = SyntheticProvider(), []
    row = await run_slot(plan, slot, provider, on_delta=deltas.append)
    assert row["status"] == "completed" and row["reply"] == "Mình nghe bạn."
    assert "".join(deltas) == row["reply"]
    assert row["requests"] == 1
    assert row["assessment_tool_calls"] == 1
    tool = provider.requests[0].closing_tool
    assert tool["name"] == "report_turn_assessment"
    assert tool["access"] == "read" and tool["budget_exempt"] is True
    assert set(tool["parameters"]["required"]) == set(assessment())
    assert provider.classifications == []


@pytest.mark.asyncio
async def test_postprocess_classifier_sees_the_reply_and_keeps_deterministic_floor_separate():
    from evals.s06_runner import run_slot

    plan, slot = slot_for("c_postprocess_classifier")
    target = next(item for item in plan["inputs"] if item["case_id"] == slot["case_id"])
    target["turns"] = ["Mình muốn chết."]
    provider = SyntheticProvider()
    row = await run_slot(plan, slot, provider)
    assert row["status"] == "completed" and row["requests"] == 2
    assert provider.classifications[0].reply == "Mình nghe bạn."
    assert provider.classifications[0].turns == ("Mình muốn chết.",)
    assert row["structured"]["urgency"] == "none"
    assert row["deterministic_urgency"] == "immediate"
    assert row["urgency_union"] == "immediate"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mechanism", "provider"),
    [
        ("a_json_stream", SyntheticProvider(chunks=['{"reply":"partial"'])),
        ("a_json_stream", SyntheticProvider(chunks=['{"reply":"x","urgency":"none"}'])),
        ("b_closing_tool", SyntheticProvider(tool=False)),
        ("b_closing_tool", SyntheticProvider(duplicate_tool=True)),
        ("c_postprocess_classifier", SyntheticProvider(classified={"urgency": "none"})),
    ],
)
async def test_incomplete_or_invalid_extraction_is_a_failed_slot(mechanism, provider):
    from evals.s06_runner import run_slot

    plan, slot = slot_for(mechanism)
    row = await run_slot(plan, slot, provider)
    assert row["status"] == "failed" and row["structured"] is None
    assert row["crashed"] == "ExtractionFailed"


@pytest.mark.asyncio
async def test_default_plan_executes_all_240_pinned_slots_with_synthetic_provider_only():
    from evals.s06_mechanisms import build_plan
    from evals.s06_runner import run_plan

    plan = build_plan()
    provider = SyntheticProvider()
    rows = await run_plan(plan, provider)
    assert len(rows) == 240
    assert all(row["status"] == "completed" for row in rows)
    assert all(row["provenance_id"] == plan["provenance_id"] for row in rows)
    assert len(provider.requests) == 240 and len(provider.classifications) == 60
    assert sum(row["requests"] for row in rows) == 300
    assert plan["max_requests"] == sum(row["requests"] for row in rows)
    assert {row["repeat"] for row in rows} == {1, 2, 3}
    assert all(row["structured"] is None for row in rows if row["mechanism"] == "text_baseline")


@pytest.mark.asyncio
async def test_openai_adapter_uses_only_injected_client_with_explicit_safe_request_shapes():
    from evals.s06_runner import OpenAIExtractionProvider, run_slot
    from moodprint_shared.config import AppConfig

    calls, closed = [], []

    class FakeStream:
        def __init__(self, events):
            self.events = events

        async def __aiter__(self):
            for event in self.events:
                yield event

        async def close(self):
            closed.append(True)

    async def create(**kwargs):
        calls.append(kwargs)
        if not kwargs.get("stream"):
            return SimpleNamespace(
                status="completed", output=[], output_text=json.dumps(assessment())
            )
        content = "Mình nghe bạn."
        if kwargs.get("text"):
            content = json.dumps({"reply": content, **assessment()})
        events = [SimpleNamespace(type="response.output_text.delta", delta=content)]
        if kwargs.get("tools"):
            events.append(
                SimpleNamespace(
                    type="response.output_item.done",
                    item=SimpleNamespace(
                        type="function_call",
                        name="report_turn_assessment",
                        arguments=json.dumps(assessment()),
                    ),
                )
            )
        events.append(
            SimpleNamespace(type="response.completed", response=SimpleNamespace(status="completed"))
        )
        return FakeStream(events)

    client = SimpleNamespace(responses=SimpleNamespace(create=create))
    provider = OpenAIExtractionProvider(client, AppConfig())
    assert calls == []
    for mechanism in ("a_json_stream", "b_closing_tool", "c_postprocess_classifier"):
        plan, slot = slot_for(mechanism)
        row = await run_slot(plan, slot, provider)
        assert row["status"] == "completed"
    assert len(calls) == 4 and len(closed) == 3
    assert all(call["store"] is False and call["model"] == "gpt-6-luna" for call in calls)
    assert all(call["max_output_tokens"] > 0 for call in calls)
    assert all("temperature" not in call and "top_p" not in call for call in calls)
    assert calls[0]["text"]["format"]["type"] == "json_schema"
    assert calls[0]["text"]["format"]["strict"] is True
    assert calls[1]["tools"][0]["name"] == "report_turn_assessment"
    assert calls[1]["tools"][0]["strict"] is True
    assert "tools" not in calls[2]
    assert calls[3]["text"]["format"]["name"] == "TurnAssessment"


@pytest.mark.asyncio
async def test_openai_adapter_refusal_or_unfinished_stream_is_failed_not_coverage():
    from evals.s06_runner import OpenAIExtractionProvider, run_slot
    from moodprint_shared.config import AppConfig

    class RefusedStream:
        async def __aiter__(self):
            yield SimpleNamespace(type="response.refusal.delta", delta="synthetic refusal")

        async def close(self):
            pass

    async def create(**kwargs):
        return RefusedStream()

    provider = OpenAIExtractionProvider(
        SimpleNamespace(responses=SimpleNamespace(create=create)), AppConfig()
    )
    plan, slot = slot_for("a_json_stream")
    row = await run_slot(plan, slot, provider)
    assert row["status"] == "failed" and row["structured"] is None


@pytest.mark.asyncio
async def test_budget_error_wrapped_by_sdk_stops_plan_before_the_next_request():
    import httpx
    from evals.budget import BudgetExhausted
    from evals.s06_mechanisms import build_plan
    from evals.s06_runner import run_plan
    from openai import APIConnectionError

    class BlockedProvider(SyntheticProvider):
        async def stream(self, request):
            self.requests.append(request)
            try:
                raise BudgetExhausted("synthetic exhausted cumulative ledger")
            except BudgetExhausted as cause:
                raise APIConnectionError(
                    request=httpx.Request("POST", "https://example.invalid")
                ) from cause
            yield  # pragma: no cover - preserve async-generator shape

    provider = BlockedProvider()
    rows = await run_plan(build_plan(), provider)
    assert len(provider.requests) == 1 and len(rows) == 1
    assert rows[0]["blocked"] == "cumulative_budget_guard"
