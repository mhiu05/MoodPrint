"""V3-07: fast-path triage, structured plan schema and the pure policy layer (no model, no I/O)."""

import pytest
from pydantic import ValidationError

from app.ai.orchestration.plan import OrchestrationPlan
from app.ai.orchestration.policy import Counters, Grants, Signals, available, validate
from app.ai.orchestration.triage import triage

ALL_EDGES = {
    "dieuphoi_consult_nhatky": 2, "dieuphoi_consult_hoatdong": 3,
    "dieuphoi_handoff_nhatky": 4, "dieuphoi_handoff_hoatdong": 5,
}
GRANTS = Grants(feature=True, eligible=True, edges=ALL_EDGES, journal_context=True)
COUNTERS = Counters(steps_today=0, daily_cap=20, budget_ratio=None, budget_share=0.7, seconds_remaining=28,
                    specialist_timeout=10)
SAFE = Signals(distress=False, journal_refused=False)


def plan(**fields):
    body = {
        "intent": "reflect_then_plan", "workflow": "consult", "primary_agent": "dieuphoi",
        "specialists": ["nhatky", "hoatdong"], "handoff_target": None,
        "subtasks": [{"agent": "nhatky", "task": "summarize_recent_entries", "focus": "tuần rồi"},
                     {"agent": "hoatdong", "task": "suggest_activities", "focus": "cuối tuần nhẹ nhàng"}],
        "data_categories": ["journal_entries", "time_budget"], "context_refs": ["latest_message"],
        "expected_output": "plan", "confidence": 0.9, "fallback": "answer_directly",
    }
    body.update(fields)
    return OrchestrationPlan.model_validate(body)


@pytest.mark.parametrize("text", ["chào", "Chào bạn!", "cảm ơn nha", "ok", "hihi", "Điều phối ơi chào nhé"])
def test_trivial_messages_take_the_fast_path(text):
    assert triage(text) == "direct"


@pytest.mark.parametrize("text", [
    "Giúp mình xem lại những điều mình đã ghi trong tuần rồi lên vài hoạt động nhẹ nhàng cho cuối tuần.",
    "Mình muốn nói chuyện trực tiếp với Nhật ký để nhìn lại cảm xúc tuần này.",
    "Gợi ý cho mình một hoạt động nhẹ tối nay",
    "Chia nhỏ mục tiêu học tiếng Anh giúp mình",
])
def test_specialist_cues_take_the_smart_path(text):
    assert triage(text) == "plan"


def test_distress_never_reaches_the_planner():
    assert triage("Mình không muốn sống nữa, nhật ký tuần này toàn chuyện tệ") == "direct"


def test_plan_schema_is_closed_and_bounded():
    with pytest.raises(ValidationError):
        plan(specialists=["nhatky", "hoatdong", "nhatky"])
    with pytest.raises(ValidationError):
        plan(specialists=["may"])
    with pytest.raises(ValidationError):
        plan(grant_journal=True)  # a model cannot add a permission field
    with pytest.raises(ValidationError):
        plan(confidence=1.5)
    with pytest.raises(ValidationError):
        plan(subtasks=[{"agent": "nhatky", "task": "summarize_recent_entries", "focus": "x" * 121}])


def test_consult_both_when_every_grant_holds():
    decision = validate(plan(), GRANTS, COUNTERS, SAFE)
    assert decision.workflow == "consult" and decision.consult == ("nhatky", "hoatdong")
    assert decision.handoff is None and decision.denied == {}
    assert decision.versions == {"nhatky": 2, "hoatdong": 3}


def test_a_disabled_edge_removes_only_that_specialist():
    grants = Grants(feature=True, eligible=True, edges={"dieuphoi_consult_hoatdong": 3}, journal_context=True)
    decision = validate(plan(), grants, COUNTERS, SAFE)
    assert decision.consult == ("hoatdong",) and decision.denied == {"nhatky": "edge_disabled"}


def test_journal_specialist_needs_journal_context_and_respects_a_refusal():
    no_context = Grants(feature=True, eligible=True, edges=ALL_EDGES, journal_context=False)
    decision = validate(plan(), no_context, COUNTERS, SAFE)
    assert decision.consult == ("hoatdong",) and decision.denied == {"nhatky": "journal_consent_off"}
    refused = validate(plan(), GRANTS, COUNTERS, Signals(distress=False, journal_refused=True))
    # A refusal is honoured silently: never recorded as a denial reason.
    assert refused.consult == ("hoatdong",) and refused.denied == {}


def test_handoff_needs_its_edge_and_confidence():
    handoff = plan(workflow="handoff", specialists=[], handoff_target="nhatky", intent="talk_to_specialist")
    assert validate(handoff, GRANTS, COUNTERS, SAFE).handoff == "nhatky"
    only_consult = Grants(feature=True, eligible=True, edges={"dieuphoi_consult_nhatky": 2}, journal_context=True)
    blocked = validate(handoff, only_consult, COUNTERS, SAFE)
    assert blocked.workflow == "direct" and blocked.denied == {"nhatky": "edge_disabled"}
    unsure = validate(plan(workflow="handoff", specialists=[], handoff_target="nhatky", confidence=0.3),
                      GRANTS, COUNTERS, SAFE)
    assert unsure.workflow == "direct" and unsure.denied == {"nhatky": "low_confidence"}


@pytest.mark.parametrize(("counters", "reason"), [
    (Counters(steps_today=19, daily_cap=20, budget_ratio=None, budget_share=0.7, seconds_remaining=28,
              specialist_timeout=10), "daily_cap"),
    (Counters(steps_today=0, daily_cap=20, budget_ratio=0.8, budget_share=0.7, seconds_remaining=28,
              specialist_timeout=10), "budget"),
    (Counters(steps_today=0, daily_cap=20, budget_ratio=None, budget_share=0.7, seconds_remaining=15,
              specialist_timeout=10), "time_budget"),
    (Counters(steps_today=0, daily_cap=20, budget_ratio=None, budget_share=0.7, seconds_remaining=28,
              specialist_timeout=10, capacity=False), "capacity"),
])
def test_cost_limits_fall_back_to_a_direct_answer(counters, reason):
    decision = validate(plan(), GRANTS, counters, SAFE)
    assert decision.workflow == "direct" or len(decision.consult) == 1
    assert reason in decision.denied.values()


def test_structural_and_safety_gates_deny_everything():
    for grants in (Grants(feature=False, eligible=True, edges=ALL_EDGES, journal_context=True),
                   Grants(feature=True, eligible=False, edges=ALL_EDGES, journal_context=True)):
        assert validate(plan(), grants, COUNTERS, SAFE).workflow == "direct"
    distress = validate(plan(), GRANTS, COUNTERS, Signals(distress=True, journal_refused=False))
    assert distress.workflow == "direct" and distress.denied == {}


def test_direct_plan_and_available_options():
    assert validate(plan(workflow="direct", specialists=[]), GRANTS, COUNTERS, SAFE).workflow == "direct"
    assert available(GRANTS, SAFE) == {"consult": ["nhatky", "hoatdong"], "handoff": ["nhatky", "hoatdong"]}
    none = Grants(feature=True, eligible=True, edges={}, journal_context=True)
    assert available(none, SAFE) == {"consult": [], "handoff": []}
    assert available(Grants(feature=True, eligible=True, edges=ALL_EDGES, journal_context=False), SAFE)["consult"] == [
        "hoatdong"]
