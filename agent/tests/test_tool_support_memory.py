"""Support tools (U-AG-150…160), memory candidate gate (U-AG-80…95) and the pinned inventory."""

import re
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest
from agents import RunContextWrapper
from moodprint_agent.budget import RunToolBudget
from moodprint_agent.memory.validation import validate_candidate
from moodprint_agent.tools.context import CompanionToolContext
from moodprint_agent.tools.factory import build_registry
from moodprint_agent.tools.memory import propose_memory
from moodprint_agent.tools.support import draft_support_message, support_directory
from moodprint_agent.tools.support_data import DIRECTORY
from moodprint_shared.config import AppConfig
from moodprint_shared.contracts.agent import AgentServices
from moodprint_shared.contracts.auth import AuthContext
from moodprint_shared.contracts.context import ContextBundle


def make_ctx(memory: Any = None) -> CompanionToolContext:
    return CompanionToolContext(
        auth=AuthContext(uuid4(), "s", "aal1", "{}"),
        request_id="r",
        conversation_id=uuid4(),
        run_id=uuid4(),
        age_band=None,
        services=cast(AgentServices, SimpleNamespace(memory=memory)),
        context=ContextBundle(),
        budget=RunToolBudget(),
    )


# --- candidate gate -----------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("category", "content"),
    [
        ("communication", "Thích được trả lời ngắn gọn"),
        ("goal", "Muốn luyện nói chuyện với bố mẹ"),
        ("support_person", "Người lớn mình tin nhất là cô chủ nhiệm"),
        ("preference", "Mình thích nghe nhạc nhẹ khi căng thẳng"),
        ("communication", "Mình muốn được hỏi từng câu một"),
        ("goal", "Mình muốn tự tin hơn khi nói trước lớp"),
    ],
)
def test_durable_preferences_are_accepted(category: str, content: str) -> None:
    assert validate_candidate(category, content) is None  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("category", "content", "reason"),
    [
        ("context", "Hôm 12/11 bạn A chụp ảnh mình gửi vào nhóm", "contains_name"),
        ("preference", "Liên hệ mình qua nam@example.com", "contains_contact"),
        ("preference", "Số của mình là 0912 345 678", "contains_contact"),
        ("preference", "Xem https://fb.com/x nhé", "contains_contact"),
        ("preference", "Hay nhắn @minh_99 nhé", "contains_contact"),
        ("support_person", "Người mình tin là Nguyễn Văn Hùng", "contains_name"),
        ("support_person", "Bạn Lan là người mình tin", "contains_name"),
        ("context", "Các bạn hay bắt nạt mình ở lớp", "incident_content"),
        ("context", "Có người đe dọa mình", "incident_content"),
        ("context", "Ngày 12 mình bị loại khỏi nhóm", "incident_content"),
        ("preference", "x" * 501, "too_long"),
        ("preference", "   ", "empty_after_trim"),
        ("support_person", "Người mình tin là ai đó trong lớp", "category_mismatch"),
    ],
)
def test_names_contacts_and_incidents_are_rejected_with_a_code_not_the_text(
    category: str, content: str, reason: str
) -> None:
    assert validate_candidate(category, content) == reason  # type: ignore[arg-type]


async def test_agent_can_only_create_a_pending_candidate_never_a_memory() -> None:
    proposed: list[Any] = []

    class Memory:
        async def propose(self, auth, data):
            proposed.append(data)
            return SimpleNamespace(id=uuid4())

        async def create(self, *args, **kwargs):
            raise AssertionError("agents must not create approved memories")

    ctx = make_ctx(Memory())
    ok = await propose_memory(
        RunContextWrapper(ctx), category="communication", content="Thích trả lời ngắn gọn"
    )
    assert (
        ok["status"] == "proposed" and "chưa có gì được ghi nhớ".casefold() in ok["note"].casefold()
    )
    assert (
        proposed[0].source_kind == "agent_proposed"
        and proposed[0].source_conversation_id == ctx.conversation_id
    )
    again = await propose_memory(RunContextWrapper(ctx), category="goal", content="Muốn luyện nói")
    assert again["error"]["code"] == "candidate_limit" and len(proposed) == 1


async def test_rejected_candidate_never_reaches_the_memory_service() -> None:
    class Memory:
        async def propose(self, *args, **kwargs):
            raise AssertionError("must not be called")

    ctx = make_ctx(Memory())
    out = await propose_memory(
        RunContextWrapper(ctx), category="context", content="Hôm 12/11 bạn A chụp ảnh mình"
    )
    assert out["status"] == "rejected" and out["reason"] in {"contains_name", "incident_content"}
    assert ctx.scratch.memory_candidates == 0


# --- support tools ----------------------------------------------------------------------------------
async def test_directory_has_only_the_verified_hotline_number() -> None:
    numbers = {e["phone"] for entries in DIRECTORY.values() for e in entries if e["phone"]}
    assert numbers == {"111"}
    for entries in DIRECTORY.values():
        for entry in entries:
            if entry["phone"]:
                assert entry["source"] and entry["verifiedOn"]
    out = await support_directory(RunContextWrapper(make_ctx()), kind="urgent")
    assert out["verifiedOn"] == "2026-11-07" and out["entries"][0]["phone"] == "111"


async def test_draft_is_text_only_cleans_contacts_and_says_it_was_not_sent() -> None:
    out = await draft_support_message(
        RunContextWrapper(make_ctx()),
        recipient_role="teacher",
        purpose="Em bị loại khỏi nhóm làm bài, xem https://x.vn hoặc gọi 0912345678",
        key_points=[
            "Chuyện xảy ra 3 lần trong tuần",
            "Em muốn cô giúp xếp nhóm lại",
            "",
            "ý 4",
            "ý 5",
            "ý 6",
        ],
    )
    assert out["sent"] is False and "không gửi" in out["notice"]
    assert "0912" not in out["draft"] and "x.vn" not in out["draft"]
    assert out["draft"].count("\n- ") == 5  # blank and surplus points are dropped
    empty = await draft_support_message(
        RunContextWrapper(make_ctx()), recipient_role="parent", purpose="", key_points=[]
    )
    assert empty["error"]["code"] == "missing_content"


# --- inventory ------------------------------------------------------------------------------------------
EXPECTED_TOOLS = {
    "knowledge_search": ("read", False),
    "get_case_context": ("read", False),
    "propose_case_event": ("prepare", False),
    "save_confirmed_event": ("write", True),
    "get_action_plan": ("read", False),
    "propose_action_plan": ("prepare", False),
    "save_plan": ("write", True),
    "propose_memory": ("prepare", False),
    "support_directory": ("read", False),
    "draft_support_message": ("prepare", False),
}  # analyze_evidence (P3-09) and report_turn_assessment (S-06) join when implemented


def test_tool_inventory_is_pinned_so_a_new_tool_is_a_reviewed_change() -> None:
    registry = build_registry(AppConfig())
    assert set(registry.names()) == set(EXPECTED_TOOLS)
    for name, (access, approval) in EXPECTED_TOOLS.items():
        policy = registry.policy(name)
        assert (policy.access, policy.needs_approval) == (access, approval), name


def test_no_outbound_tools_and_no_identity_parameters() -> None:
    registry = build_registry(AppConfig())
    outbound = re.compile(r"(?:^|_)(send|post|email|call|submit|share)(?:_|$)")
    for name, params in registry.tool_signatures().items():
        assert not outbound.search(name), name
        assert not any(outbound.search(p) for p in params), (name, params)
        assert not {"user_id", "owner_id", "engine", "token", "jwt", "url"} & set(params), name
    assert "submit_share" not in registry.names()


def test_every_write_tool_takes_only_a_proposal_id() -> None:
    registry = build_registry(AppConfig())
    for name in registry.names():
        if registry.policy(name).access == "write":
            assert registry.tool_signatures()[name] == ("proposal_id",), name


def test_every_tool_has_a_vietnamese_ui_label() -> None:
    registry = build_registry(AppConfig())
    for name in registry.names():
        label = registry.label(name)
        assert label != name and label != name.replace("_", " ") and label[0].isupper(), name
