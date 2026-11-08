"""Single-model policy and request-shape invariants for every model call."""

import ast
import re
from dataclasses import fields
from pathlib import Path

from moodprint_agent.companion import build_companion, model_settings
from moodprint_agent.tools.registry import ToolRegistry
from moodprint_shared.config import OPENAI_MODEL, AppConfig

ROOT = Path(__file__).resolve().parents[2]
SOURCES = [ROOT / "agent" / "src", ROOT / "backend" / "app", ROOT / "shared" / "src"]
_OTHER_MODEL = re.compile(
    r"""["'](?:gpt-(?!6-luna)[\w.\-]*|o\d[\w.\-]*|text-embedding[\w.\-]*)["']"""
)


def test_every_model_setting_is_gpt_6_luna() -> None:
    agent = AppConfig().agent
    models = {f.name: getattr(agent, f.name) for f in fields(agent) if "model" in f.name}
    assert models and set(models.values()) == {OPENAI_MODEL}


def test_no_other_model_literal_in_source() -> None:
    offenders: list[str] = []
    for base in SOURCES:
        for path in base.rglob("*.py"):
            if "testing" in path.parts:
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if _OTHER_MODEL.search(line):
                    offenders.append(f"{path.relative_to(ROOT)}:{number}")
    assert offenders == []


def test_model_settings_are_private_capped_and_reasoning_only() -> None:
    settings = model_settings(AppConfig())
    assert settings.store is False
    assert settings.parallel_tool_calls is False
    assert settings.max_tokens == AppConfig().agent.max_output_tokens
    assert settings.temperature is None and settings.top_p is None
    assert settings.reasoning is not None and settings.reasoning.effort == "low"
    assert model_settings(AppConfig(), effort="medium").reasoning.effort == "medium"  # type: ignore[union-attr]


def test_companion_agent_uses_the_fixed_model_and_no_sampling_overrides() -> None:
    agent = build_companion(AppConfig(), ToolRegistry())
    assert agent.model == OPENAI_MODEL
    assert agent.model_settings.temperature is None and agent.model_settings.top_p is None


def test_phase3_defaults_are_conservative() -> None:
    cfg = AppConfig()
    assert cfg.agent.daily_token_cap_per_user == 200_000
    assert cfg.agent.proposal_ttl_s == 1800 and cfg.agent.approval_ttl_s == 900
    assert cfg.agent.analysis_allowed_mime == ("image/jpeg", "image/png", "image/webp")
    assert cfg.agent.analysis_max_image_bytes == 8_000_000
    assert cfg.agent.roleplay_max_turns == 30
    assert cfg.memory.max_context_memories == 5
    assert cfg.memory.extraction_max_candidates_per_run == 1


def test_agent_package_has_no_unreviewed_network_clients() -> None:
    """Only the model client and the budget-aware evidence fetcher may open connections."""
    banned = {"requests", "urllib3", "aiohttp", "socket"}
    for path in (ROOT / "agent" / "src").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module.split(".")[0]]
            assert not banned.intersection(names), path
