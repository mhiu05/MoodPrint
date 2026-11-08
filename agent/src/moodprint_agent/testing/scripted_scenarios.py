"""Deterministic E2E runtime: the real Phase 3 registry, context, gateway and domain wiring with a
rule-driven stand-in for the provider. Loaded only by ``scripts/e2e_app.py`` under APP_ENV=test.

The stand-in decides each model request from the visible conversation (last user text and the tool
results of *this* turn), so it works across conversations, restarts and approval resumes. It proves
tool requests, approval boundaries and database rows; it says nothing about model behaviour.
"""

import asyncio
import json
from collections.abc import AsyncIterator, Sequence
from typing import Any, cast
from uuid import uuid4

from agents import Model
from agents.testing import ModelStep, ScriptedModel, assistant_message, function_call
from agents.usage import Usage
from moodprint_shared.config import AppConfig

from moodprint_agent.roleplay.scenarios import PERSONAS
from moodprint_agent.runtime import CompanionRuntime
from moodprint_agent.testing.fake_provider import build_fake_client
from moodprint_agent.tools.factory import build_registry

USAGE = Usage(requests=1, input_tokens=12, output_tokens=8, total_tokens=20)


def _d(item: Any) -> dict[str, Any] | None:
    return cast(dict[str, Any], item) if isinstance(item, dict) else None


def _text_of(item: Any) -> str:
    data = _d(item)
    content: Any = data.get("content") if data else None
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [_d(part) for part in cast(list[Any], content)]
        return " ".join(str(part.get("text", "")) for part in parts if part)
    return ""


def _is_user(item: Any) -> bool:
    data = _d(item)
    return data is not None and data.get("role") == "user"


def _json(value: Any) -> dict[str, Any]:
    try:
        parsed: Any = json.loads(value) if isinstance(value, str) else value
    except ValueError:
        return {}
    return cast(dict[str, Any], parsed) if isinstance(parsed, dict) else {}


class _Turn:
    """What has happened since the user's latest message."""

    def __init__(self, items: Sequence[Any]) -> None:
        last = max((i for i, item in enumerate(items) if _is_user(item)), default=-1)
        self.text = _text_of(items[last]).lower() if last >= 0 else ""
        self.history = list(items)
        names: dict[str, str] = {}
        self.calls: list[str] = []
        self.outputs: dict[str, dict[str, Any]] = {}
        for raw in items[last + 1 :]:
            item = _d(raw)
            if item is None:
                continue
            if item.get("type") == "function_call":
                names[str(item.get("call_id"))] = str(item.get("name"))
                self.calls.append(str(item.get("name")))
            elif item.get("type") == "function_call_output":
                name = names.get(str(item.get("call_id")))
                if name:
                    self.outputs[name] = _json(item.get("output"))

    def earlier_proposal(self, kind: str) -> str | None:
        """Newest stored proposal of this kind anywhere in the visible history."""
        for raw in reversed(self.history):
            item = _d(raw)
            if item and item.get("type") == "function_call_output":
                data = _json(item.get("output"))
                preview: Any = data.get("preview")
                if (
                    data.get("proposalId")
                    and isinstance(preview, dict)
                    and cast(dict[str, Any], preview).get("kind") == kind
                ):
                    return str(data["proposalId"])
        return None


def decide(items: Sequence[Any]) -> list[Any]:
    turn = _Turn(items)
    text = turn.text

    def call(name: str, args: dict[str, Any]) -> list[Any]:
        return [function_call(name, args, call_id=f"call-{uuid4().hex[:12]}")]

    if "nguồn" in text:
        if "knowledge_search" not in turn.calls:
            return call("knowledge_search", {"query": "tìm người lớn hỗ trợ khi bị bắt nạt"})
        return [assistant_message("Bạn có thể nhờ một người lớn đáng tin [S1].")]
    if "ghi mốc" in text:
        if "get_case_context" not in turn.calls:
            return call("get_case_context", {})
        if "propose_case_event" not in turn.calls:
            cases = cast(
                list[dict[str, Any]], turn.outputs.get("get_case_context", {}).get("cases") or []
            )
            if not cases:
                return [assistant_message("Mình chưa thấy hồ sơ nào để ghi mốc.")]
            return call(
                "propose_case_event",
                {
                    "case_id": cases[0]["id"],
                    "description": "Bạn A nhắn tin chế giễu trong nhóm lớp.",
                    "basis": "user_stated",
                    "rationale": "Bạn vừa kể điều này.",
                    "when": "2026-11-03",
                    "time_precision": "day",
                    "place": "Nhóm chat lớp",
                },
            )
        return [assistant_message("Đây là đề xuất CHƯA LƯU. Bạn có muốn lưu mốc này không?")]
    if "lưu mốc" in text:
        proposal = turn.earlier_proposal("case_event")
        if proposal and "save_confirmed_event" not in turn.calls:
            return call("save_confirmed_event", {"proposal_id": proposal})
        saved = turn.outputs.get("save_confirmed_event", {})
        done = saved.get("status") == "applied"
        return [assistant_message("Đã lưu mốc vào hồ sơ." if done else "Mình chưa lưu mốc này.")]
    if "lập kế hoạch" in text:
        if "get_case_context" not in turn.calls:
            return call("get_case_context", {})
        if "propose_action_plan" not in turn.calls:
            cases = cast(
                list[dict[str, Any]], turn.outputs.get("get_case_context", {}).get("cases") or []
            )
            if not cases:
                return [assistant_message("Mình chưa thấy hồ sơ nào để lập kế hoạch.")]
            return call(
                "propose_action_plan",
                {
                    "case_id": cases[0]["id"],
                    "goal": "Nói chuyện với cô chủ nhiệm",
                    "items": [
                        {
                            "label": "Ghi lại vài ý chính",
                            "priority": "high",
                            "reason": "Dễ nói hơn",
                        },
                        {
                            "label": "Hẹn gặp cô",
                            "priority": "normal",
                            "reason": "Có thời gian riêng",
                        },
                    ],
                    "base_version": None,
                    "rationale": "Bạn muốn nói với cô.",
                },
            )
        return [assistant_message("Đây là kế hoạch CHƯA LƯU. Bạn có muốn lưu không?")]
    if "lưu kế hoạch" in text:
        proposal = turn.earlier_proposal("action_plan")
        if proposal and "save_plan" not in turn.calls:
            return call("save_plan", {"proposal_id": proposal})
        done = turn.outputs.get("save_plan", {}).get("status") == "applied"
        return [assistant_message("Đã lưu kế hoạch." if done else "Mình chưa lưu kế hoạch.")]
    if "ghi nhớ" in text:
        if "propose_memory" not in turn.calls:
            return call(
                "propose_memory",
                {"category": "preference", "content": "Mình thích được trả lời ngắn gọn"},
            )
        return [assistant_message("Mình đã gợi ý, bạn duyệt ở phần ghi nhớ nhé.")]
    if "muốn chết" in text:
        return [
            assistant_message("Mình rất quan tâm đến bạn. Hãy nói ngay với một người lớn bạn tin.")
        ]
    return [assistant_message("Mình nghe đây. Bạn muốn kể thêm không?")]


_FAILED_ONCE: set[str] = set()
_PARTNER_LINES = {
    "teacher": ("Cô", "em", "cô"),
    "parent": ("Mẹ", "con", "mẹ"),
    "trusted_adult": ("Mình", "bạn", "mình"),
}


def partner_reply(system_instructions: str, items: Sequence[Any]) -> list[Any]:
    """A fixed persona line per role (the partner has no tools): enough to see role consistency."""
    role = next(
        (
            name
            for name, persona in PERSONAS.items()
            if f'"persona":"{persona}"' in system_instructions
        ),
        "teacher",
    )
    who, you, me = _PARTNER_LINES[role]
    turn = sum(1 for item in items if _is_user(item))
    return [
        assistant_message(
            f"{who} nghe {you} đây (lượt {turn}). {you.capitalize()} kể thêm giúp {me} nhé?"
        )
    ]


class RuleModel(Model):
    """A provider-neutral Model that answers each request from ``decide``.

    Test triggers in the user's text (all synthetic): "trả lời chậm" delays the answer by 8 s (cancel and
    network tests), "lỗi một lần" fails the first request with that exact text and then recovers
    (retry test), "lỗi mô hình" always fails (terminal failure). Roleplay requests (the partner prompt)
    get a fixed persona line.
    """

    def _plan(self, system_instructions: Any, input: Any) -> tuple[ScriptedModel, float]:
        items: list[Any] = (
            [{"role": "user", "content": input}] if isinstance(input, str) else list(input)
        )
        text = _Turn(items).text
        if "lỗi mô hình" in text:
            raise RuntimeError("e2e injected model failure")
        if "lỗi một lần" in text and text not in _FAILED_ONCE:
            _FAILED_ONCE.add(text)
            raise RuntimeError("e2e injected one-time model failure")
        delay = 8.0 if "trả lời chậm" in text else 0.0
        if isinstance(system_instructions, str) and "DIỄN TẬP" in system_instructions:
            output = partner_reply(system_instructions, items)
        else:
            output = decide(items)
        return ScriptedModel([ModelStep(output=output, usage=USAGE)]), delay

    async def get_response(  # type: ignore[override]
        self, system_instructions: Any, input: Any, *args: Any, **kwargs: Any
    ) -> Any:
        scripted, delay = self._plan(system_instructions, input)
        if delay:
            await asyncio.sleep(delay)
        return await scripted.get_response(system_instructions, input, *args, **kwargs)

    def stream_response(  # type: ignore[override]
        self, system_instructions: Any, input: Any, *args: Any, **kwargs: Any
    ) -> AsyncIterator[Any]:
        scripted, delay = self._plan(system_instructions, input)

        async def run() -> AsyncIterator[Any]:
            if delay:
                await asyncio.sleep(delay)
            async for event in scripted.stream_response(
                system_instructions, input, *args, **kwargs
            ):
                yield event

        return run()


def build_e2e_runtime(cfg: AppConfig) -> CompanionRuntime:
    """Frozen entry point used by ``scripts/e2e_app.py``: real wiring, scripted provider only.

    ``openai_client`` is the deterministic HTTP-boundary fake: evidence analysis and the roleplay coach
    run their real code against it (see ``fake_provider``).
    """
    return CompanionRuntime(
        cfg, build_registry(cfg), model=RuleModel(), openai_client=build_fake_client()
    )
