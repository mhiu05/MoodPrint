import shutil

import pytest


def test_hangout_does_not_direct_users_to_retired_shared_activities():
    from app.ai.skills.registry import SkillRegistry

    registry = SkillRegistry()
    assert "activity hiện có" not in registry.instructions("hangout")
    assert registry.load()["hangout"].version == "2"


def test_registry_loads_six_trusted_skills():
    from app.ai.skills.registry import SkillRegistry
    registry = SkillRegistry()
    assert set(registry.load()) == {
        "hangout", "learn-new-thing", "weekly-review", "mood-patterns",
        "guided-journal", "reframe-thought",
    }
    assert "source_entry_ids" in registry.instructions("weekly-review")
    for identity in ("weekly-review", "mood-patterns", "guided-journal", "reframe-thought"):
        assert "không chẩn đoán" in registry.instructions(identity).casefold()
    assert "GPS" in registry.instructions("hangout")
    assert "5–15" in registry.instructions("learn-new-thing")
    with pytest.raises(ValueError):
        registry.instructions("../../.env")


def test_missing_and_oversize_skill_is_unavailable_not_arbitrary_code(tmp_path):
    from app.ai.skills.registry import ROOT, SkillRegistry
    shutil.copytree(ROOT, tmp_path / "skills")
    root = tmp_path / "skills"
    (root / "hangout/SKILL.md").write_text("x" * 17000, encoding="utf8")
    registry = SkillRegistry(root)
    assert "hangout" not in registry.load()
    assert "learn-new-thing" in registry.load()


@pytest.mark.parametrize(("prompt", "expected"), [
    ("Gợi ý đi chơi cuối tuần", "hangout"), ("goi y di choi", "hangout"),
    ("Có 10 phút muốn học điều mới", "learn-new-thing"),
    ("không muốn đi đâu", None), ("Hôm qua mình đã đi chơi", None),
    ("Muốn đi chơi và học điều mới", None),
])
def test_current_prompt_resolver_respects_negation_and_ambiguity(prompt, expected):
    from app.ai.skills.resolver import resolve_skill
    assert resolve_skill(prompt, None, "hoatdong") == expected


def test_manual_skill_wins_without_handoff_or_tools():
    from app.ai.skills.resolver import resolve_skill
    assert resolve_skill("Gợi ý đi chơi", "learn-new-thing", "nhatky") == "learn-new-thing"
    assert resolve_skill("Gợi ý đi chơi", None, "rure") is None


def test_agent_allowlists_are_subsets_of_v3():
    from app.ai.agents import V3_IDS
    from app.ai.skills.registry import AGENTS, SPECS

    assert set(AGENTS) == set(SPECS)
    assert all(agents and set(agents) <= set(V3_IDS) for agents in AGENTS.values())
    assert AGENTS["weekly-review"] == AGENTS["mood-patterns"] == ("nhatky",)
    assert set(AGENTS["guided-journal"]) == set(AGENTS["reframe-thought"]) == {"dieuphoi", "nhatky"}


@pytest.mark.parametrize(("prompt", "agent", "expected"), [
    ("Nhìn lại tuần này giúp mình", "nhatky", "weekly-review"),
    ("Nhìn lại tuần này giúp mình", "dieuphoi", None),
    ("Mình hay buồn khi nào, xem mẫu cảm xúc giúp", "nhatky", "mood-patterns"),
    ("Hôm nay không biết viết gì", "dieuphoi", "guided-journal"),
    ("Giúp mình nghĩ theo cách khác về chuyện này", "dieuphoi", "reframe-thought"),
    ("Nhìn lại tuần và viết nhật ký", "nhatky", None),
    ("Không muốn nhìn lại tuần", "nhatky", None),
])
def test_resolution_table(prompt, agent, expected):
    from app.ai.skills.resolver import resolve_skill

    assert resolve_skill(prompt, None, agent) == expected


def test_manual_resolver_rejects_wrong_agent():
    from app.ai.skills.resolver import resolve_skill

    with pytest.raises(ValueError, match="skill not for agent"):
        resolve_skill("Nhìn lại tuần", "weekly-review", "hoatdong")


@pytest.mark.parametrize("manual", [None, "hangout", "weekly-review"])
def test_distress_prompt_drops_even_a_manual_skill(manual):
    from app.ai.skills.resolver import resolve_skill

    assert resolve_skill("Mình muốn chết, giúp mình nhìn lại tuần", manual, "nhatky") is None


@pytest.mark.parametrize("bad", [b"\xff\xfe", b"---\nid: hangout\nname: !execute dangerous\n---\nbody", b"---\nid: hangout\nid: learn-new-thing\n---\nbody"])
def test_registry_refuses_invalid_utf8_metadata_and_duplicate_ids(tmp_path, bad):
    from app.ai.skills.registry import ROOT, SkillRegistry
    shutil.copytree(ROOT, tmp_path / "skills")
    (tmp_path / "skills/hangout/SKILL.md").write_bytes(bad)
    registry = SkillRegistry(tmp_path / "skills")
    assert "hangout" not in registry.load()
    assert "learn-new-thing" in registry.load()
