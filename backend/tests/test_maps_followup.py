"""A follow-up about places the assistant already named must keep the conversation."""
import pytest

from app.ai.schemas import PromptOptions
from app.ai.search.policy import search_intent


@pytest.mark.parametrize("prompt", [
    "gửi cho tôi maps của các địa điểm trên",
    "địa điểm bạn vừa gợi ý đấy",
    "cho mình link google maps những nơi bạn đề xuất",
    "Gửi maps các địa điểm như trên nhé",
    "những địa điểm đó ở đâu vậy",
])
def test_back_reference_is_not_a_public_maps_search(prompt):
    # A public search turn drops the whole transcript, so the assistant could not see its own plan.
    assert not search_intent(prompt, PromptOptions()).maps


@pytest.mark.parametrize("prompt", [
    "Tìm quán cà phê ở Hà Đông",
    "tìm quán cà phê gần mình",
    "gợi ý địa điểm vui chơi ở Hà Nội",
])
def test_fresh_place_search_still_uses_maps(prompt):
    assert search_intent(prompt, PromptOptions()).maps


def test_explicit_maps_tool_overrides_back_reference():
    assert search_intent("các địa điểm trên", PromptOptions(tools=["maps_search"])).maps


def test_hoatdong_may_link_places_it_named_to_google_maps_search():
    from app.ai.prompts import conversation_instructions

    assert "google.com/maps/search/?api=1&query=" in conversation_instructions("hoatdong", "activity")
    assert "google.com/maps" not in conversation_instructions("may", "conversation")


@pytest.mark.parametrize("prompt", ["gửi cho tôi maps của các địa điểm trên", "địa điểm bạn vừa gợi ý đấy"])
async def test_prepare_turn_keeps_history_for_back_reference(prompt):
    from app.ai.search.turn import prepare_turn
    from tests.test_maps_clarification import context

    runtime, run = context()
    turn = run()
    assert await prepare_turn(runtime, turn, "hoatdong", prompt) == []
    assert turn.public_search is False  # runtime only strips the transcript when this is True


PROMPT = (
    "chủ nhật tuần này mình có lịch đi chơi quanh khu vực hà đông, "
    "lên lịch trình kế hoạch chi tiết giúp mình, đi 1 mình, tài chính 1 triệu"
)


async def test_solo_hadong_itinerary_stays_in_one_finishable_reply():
    """A full itinerary used to run until the token cap and the stream died incomplete."""
    from app.ai.search.turn import prepare_turn
    from app.ai.skills.registry import SkillRegistry
    from tests.test_maps_clarification import context

    runtime, run = context()
    runtime.settings.ai_agent_skills_enabled = True
    runtime.skills = SkillRegistry()
    turn = run()
    assert await prepare_turn(runtime, turn, "hoatdong", PROMPT) == []
    assert turn.skill_id == "hangout"
    assert turn.public_search is False
    assert "dưới 1400 ký tự" in turn.turn_instructions
    assert "Không gọi công cụ tìm địa điểm" in turn.turn_instructions


async def test_hangout_plan_keeps_a_maps_link_instruction_during_search(monkeypatch):
    from app.ai.search import maps_jobs
    from app.ai.search.turn import prepare_turn
    from app.ai.skills.registry import SkillRegistry
    from tests.test_maps_clarification import context

    async def maps(_runtime, _run, _intent):
        return {"status": "pending", "places": []}

    monkeypatch.setattr(maps_jobs, "maps_for_turn", maps)
    runtime, run = context()
    runtime.settings.ai_agent_skills_enabled = True
    runtime.skills = SkillRegistry()
    turn = run()
    await prepare_turn(runtime, turn, "hoatdong", "Gợi ý đi chơi, tìm quán cà phê ở Hà Nội")
    assert turn.skill_id == "hangout"
    assert "một link Maps cho mỗi địa điểm" in turn.turn_instructions
    assert turn.turn_instructions.index("Không tự viết URL") < turn.turn_instructions.index("một link Maps cho mỗi địa điểm")


async def test_prepare_turn_still_isolates_a_fresh_maps_search(monkeypatch):
    from app.ai.search import maps_jobs
    from app.ai.search.turn import prepare_turn
    from tests.test_maps_clarification import context

    async def maps(_runtime, _run, _intent):
        return {"status": "needs_area"}

    monkeypatch.setattr(maps_jobs, "maps_for_turn", maps)
    runtime, run = context()
    turn = run()
    assert await prepare_turn(runtime, turn, "hoatdong", "Tìm quán cà phê")
    assert turn.public_search is True
