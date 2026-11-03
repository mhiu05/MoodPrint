import shutil

import pytest


def test_registry_is_closed_and_loads_trusted_offline_workflows():
    from app.ai.skills.registry import SkillRegistry
    registry = SkillRegistry()
    assert set(registry.load()) == {"hangout", "learn-new-thing"}
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


@pytest.mark.parametrize("bad", [b"\xff\xfe", b"---\nid: hangout\nname: !execute dangerous\n---\nbody", b"---\nid: hangout\nid: learn-new-thing\n---\nbody"])
def test_registry_refuses_invalid_utf8_metadata_and_duplicate_ids(tmp_path, bad):
    from app.ai.skills.registry import ROOT, SkillRegistry
    shutil.copytree(ROOT, tmp_path / "skills")
    (tmp_path / "skills/hangout/SKILL.md").write_bytes(bad)
    registry = SkillRegistry(tmp_path / "skills")
    assert "hangout" not in registry.load()
    assert "learn-new-thing" in registry.load()
