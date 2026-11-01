"""P2-03: deny-by-default matrix, deterministic rules R1–R4, typed contracts, minimal builder."""

import json
from datetime import date
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.ai.collaboration import policy
from app.ai.collaboration.contracts import (
    AllowedContext,
    CollaborationSummary,
    EnergyHint,
    InterestActivity,
    JournalExcerpt,
    TinyHabit,
)
from app.ai.collaboration.policy import Counters, Grants, Match, Signals, evaluate, match_rule

BOTS = ("may", "guong", "nhip", "rure", "caunoi")
ALLOWED = {("rure", "nhip"), ("may", "nhip"), ("guong", "rure")}
ALL_EDGES = {"nhip_energy_for_rure": 1, "nhip_habit_for_may": 1, "rure_activity_for_guong": 1}


@pytest.mark.parametrize("requester", BOTS)
@pytest.mark.parametrize("specialist", BOTS)
def test_matrix_is_deny_by_default(requester, specialist):
    spec = policy.edge_for(requester, specialist)
    assert (spec is not None) == ((requester, specialist) in ALLOWED)


def test_caunoi_has_no_edge_in_either_direction():
    assert all("caunoi" not in (spec.requester, spec.specialist) for spec in policy.EDGES.values())
    assert [spec.edge for spec in policy.EDGES.values() if spec.reads_journal] == ["nhip_energy_for_rure"]


def chat(bot, text, intent, **extra):
    return Signals(origin="chat", bot_id=bot, intent=intent, text=text, **extra)


@pytest.mark.parametrize(
    ("signals", "rule", "edge"),
    [
        (chat("rure", "Rủ Rê ơi gợi ý gì nhẹ nhàng hợp với mình hôm nay", "activity"), "R1", "nhip_energy_for_rure"),
        (chat("rure", "Hôm nay mình đang mệt, chơi gì đây", "activity"), "R1", "nhip_energy_for_rure"),
        (chat("may", "Mấy hôm nay mình mất ngủ", "conversation"), "R3", "nhip_habit_for_may"),
        (chat("may", "Có mẹo nào bớt căng thẳng không", "practical"), "R3", "nhip_habit_for_may"),
        (chat("guong", "Mình thích vẽ, nên thử làm gì trước?", "reflection"), "R4", "rure_activity_for_guong"),
        (Signals(origin="proactive", bot_id="rure", slot="morning"), "R2", "nhip_energy_for_rure"),
    ],
)
def test_each_rule_matches_its_canonical_case(signals, rule, edge):
    match = match_rule(signals)
    assert match is not None and (match.rule_id, match.edge) == (rule, edge)


@pytest.mark.parametrize(
    "signals",
    [
        chat("rure", "Gợi ý một trò chơi vui đi", "activity"),  # no personalization ask
        chat("rure", "nhẹ nhàng thôi", "conversation"),  # not an activity turn
        chat("may", "Hôm nay trời đẹp ghê", "conversation"),  # no habit need
        chat("may", "Mình mất ngủ, chỉ cần bạn lắng nghe thôi", "listening"),  # asked only to listen
        chat("may", "Ngủ ngon nhé", "conversation"),  # "ngủ" alone is never a need
        chat("guong", "Mình thích vẽ", "reflection"),  # no ask for an activity
        chat("guong", "Mình muốn thử làm gì đó về bản thân", "reflection"),  # "về" is not drawing
        chat("guong", "Mình muốn thử vẽ", "conversation"),  # wrong intent
        chat("nhip", "gợi ý gì nhẹ nhàng hợp với mình", "activity"),  # Nhịp is never a requester
        chat("caunoi", "gợi ý gì nhẹ nhàng hợp với mình", "activity"),
        Signals(origin="proactive", bot_id="rure", slot="evening"),
        Signals(origin="proactive", bot_id="nhip", slot="morning"),
        Signals(origin="proactive", bot_id="may", slot="morning"),
    ],
)
def test_rules_do_not_fire_without_their_conditions(signals):
    assert match_rule(signals) is None


def test_extracted_values_are_closed_enums():
    match = match_rule(chat("may", "Dạo này áp lực deadline quá", "support", local_hour=23))
    assert (match.need, match.time_of_day) == ("stress", "night")
    match = match_rule(chat("guong", "Mình muốn thử học guitar 15 phút mỗi ngày, nên thử làm gì", "reflection"))
    assert (match.interest_tag, match.time_budget_minutes) == ("music", 15)
    assert policy.time_of_day(7) == "morning" and policy.time_of_day(13) == "afternoon"
    assert policy.time_of_day(19) == "evening" and policy.time_of_day(3) == "night"


GRANTED = Grants(feature_enabled=True, eligible=True, enabled_edges=ALL_EDGES, journal_context_enabled=True)
OK = Counters(recent_entries=2)
R1 = chat("rure", "gợi ý gì nhẹ nhàng hợp với mình", "activity")
R3 = chat("may", "mình mất ngủ", "conversation")


def decide(signals=R1, grants=GRANTED, counters=OK):
    return evaluate(signals, match_rule(signals), grants, counters)


def test_allowed_when_every_condition_holds():
    decision = decide()
    assert decision.allowed and decision.reason == "ok" and decision.permission_version == 1


@pytest.mark.parametrize(
    ("kwargs", "reason", "recorded"),
    [
        ({"signals": chat("rure", "nhẹ nhàng thôi", "activity", depth=1)}, "depth", False),
        ({"signals": chat("rure", "nhẹ nhàng thôi", "activity", already_consulted=True)}, "already_consulted", False),
        ({"signals": chat("rure", "mình không muốn sống nữa, gợi ý gì nhẹ nhàng", "activity")}, "distress", False),
        ({"grants": Grants(feature_enabled=False, eligible=True, enabled_edges=ALL_EDGES,
                           journal_context_enabled=True)}, "feature_off", False),
        ({"grants": Grants(feature_enabled=True, eligible=False, enabled_edges=ALL_EDGES,
                           journal_context_enabled=True)}, "ineligible_account", False),
        ({"grants": Grants(feature_enabled=True, eligible=True, enabled_edges={"nhip_habit_for_may": 1},
                           journal_context_enabled=True)}, "edge_disabled", False),
        ({"grants": Grants(feature_enabled=True, eligible=True, enabled_edges=ALL_EDGES)}, "journal_consent_off", True),
        ({"counters": Counters(recent_entries=0)}, "no_data", True),
        ({"counters": Counters(recent_entries=1, collaborations_today=10)}, "daily_cap", True),
        ({"counters": Counters(recent_entries=1, budget_ratio=0.7)}, "budget", True),
        ({"counters": Counters(recent_entries=1, seconds_remaining=22.9)}, "time_budget", True),
        ({"counters": Counters(recent_entries=1, capacity_available=False)}, "capacity", True),
    ],
)
def test_every_gate_denies_with_its_reason(kwargs, reason, recorded):
    decision = decide(**kwargs)
    assert not decision.allowed and decision.reason == reason
    assert decision.recorded is recorded
    # The database refuses to record anything outside the operational vocabulary.
    assert (reason in policy.RECORDED_DENIALS) is recorded


def test_journal_gates_apply_only_to_the_journal_edge():
    no_journal = Grants(feature_enabled=True, eligible=True, enabled_edges=ALL_EDGES)
    assert decide(R3, no_journal, Counters(recent_entries=0)).allowed


def test_budget_below_share_and_enough_time_are_allowed():
    assert decide(counters=Counters(recent_entries=1, budget_ratio=0.69, seconds_remaining=23.0)).allowed


def test_no_match_is_never_allowed():
    assert not evaluate(R1, None, GRANTED, OK).allowed


def excerpt(text="Ôn thi tới khuya, mệt"):
    return JournalExcerpt(entry_id=uuid4(), revision=1, local_date=date(2026, 10, 30), mood=2,
                          emotions=("mệt",), factors=("học tập",), excerpt=text)


def test_builder_never_carries_user_words_or_unrelated_fields():
    canary = "CANARY-CHAT-5b1e"
    for signals in (
        chat("may", f"mình mất ngủ {canary}", "conversation"),
        chat("guong", f"Mình thích vẽ {canary}, nên thử làm gì", "reflection"),
    ):
        allowed = policy.allowed_context(match_rule(signals))
        assert canary not in allowed.canonical()
        assert not allowed.journal
    energy = policy.allowed_context(match_rule(R1), journal=(excerpt(),))
    payload = json.loads(energy.canonical())
    assert set(payload) == {"schema", "journal", "need", "time_of_day", "interest_tag", "time_budget_minutes"}
    assert payload["need"] is None and payload["interest_tag"] is None
    with pytest.raises(ValueError):
        policy.allowed_context(match_rule(R3), journal=(excerpt(),))


def test_allowed_context_rejects_fields_of_another_edge():
    with pytest.raises(ValidationError):
        AllowedContext(schema="tiny-habit-in-v1", need="sleep", time_of_day="night", interest_tag="music")
    with pytest.raises(ValidationError):
        AllowedContext(schema="tiny-habit-in-v1", need="sleep")
    with pytest.raises(ValidationError):
        AllowedContext(schema="energy-hint-in-v1")  # never consulted without authorized entries
    with pytest.raises(ValidationError):
        AllowedContext(schema="interest-activity-in-v1", interest_tag="astrology", time_budget_minutes=10)
    with pytest.raises(ValidationError):
        AllowedContext.model_validate({"schema": "tiny-habit-in-v1", "need": "sleep", "time_of_day": "night",
                                       "transcript": "x"})


def test_digest_is_stable_and_content_dependent():
    a = AllowedContext(schema="tiny-habit-in-v1", need="sleep", time_of_day="night")
    b = AllowedContext(schema="tiny-habit-in-v1", need="sleep", time_of_day="night")
    c = AllowedContext(schema="tiny-habit-in-v1", need="stress", time_of_day="night")
    assert a.digest() == b.digest() != c.digest() and len(a.digest()) == 64


def test_specialist_outputs_are_closed():
    EnergyHint(energy="low", time_budget_minutes=5, basis="journal", source_entry_ids=(uuid4(),))
    for bad in (
        {"energy": "exhausted", "time_budget_minutes": 5, "basis": "none"},
        {"energy": "low", "time_budget_minutes": 7, "basis": "none"},
        {"energy": "low", "time_budget_minutes": 5, "basis": "none", "note": "đọc nhật ký"},
    ):
        with pytest.raises(ValidationError):
            EnergyHint.model_validate(bad)
    with pytest.raises(ValidationError):
        TinyHabit(habit_text="x" * 201, duration_minutes=3, kind="breathing")
    with pytest.raises(ValidationError):
        TinyHabit(habit_text="Hít thở chậm 4 nhịp", duration_minutes=30, kind="breathing")
    with pytest.raises(ValidationError):
        InterestActivity(activity_text="Vẽ một chiếc cốc trong 10 phút", challenge_kind="astrology")


def test_templates_cover_every_rule_and_stay_plain():
    for spec in policy.EDGES.values():
        for rule in spec.rules:
            line = policy.summary_for(spec.edge, rule)
            assert line and len(line) <= 200
            CollaborationSummary(kind=spec.edge, companions=[spec.specialist, spec.requester], summary=line)
            lowered = line.lower()
            for term in ("agent", "tool", "handoff", "delegation", "run", "model", "bàn về bạn"):
                assert term not in lowered
    assert policy.summary_for("nhip_habit_for_may", "R1") is None


def test_match_carries_no_free_text():
    for signals in (R1, R3, chat("guong", "Mình thích vẽ, nên thử làm gì", "reflection")):
        match = match_rule(signals)
        assert isinstance(match, Match)
        assert all(not isinstance(value, str) or len(value) <= 32 for value in vars(match).values())
