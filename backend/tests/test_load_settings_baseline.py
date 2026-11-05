"""Standalone synthetic servers must not inherit new production feature defaults."""

import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "module,enabled",
    [
        ("tests.chat_load_server", ("ai_enabled", "semantic_memory_enabled")),
        ("tests.social_load_server", ("activities_enabled",)),
    ],
)
def test_standalone_load_servers_pin_only_their_explicit_features(module, enabled):
    from app.core.config import FEATURE_FLAGS

    # Remove pytest's inherited false env, otherwise it would conceal the bug.
    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in {name.upper() for name in FEATURE_FLAGS}
    }
    environment["TEST_DATABASE_URL"] = (
        "postgresql+psycopg://localhost/moodprint_fixture_config_test"
    )
    code = """
import importlib, sys
from app.core.config import Settings
Settings.model_config["env_file"] = None
from tests.settings_baseline import ALL_FEATURES_OFF
fixture = importlib.import_module(sys.argv[1])
settings = fixture.settings if hasattr(fixture, "settings") else fixture.app.state.settings
expected = dict(ALL_FEATURES_OFF)
expected.update({name: True for name in sys.argv[2:]})
wrong = [name for name, value in expected.items() if getattr(settings, name) != value]
assert not wrong, "Unexpected fixture features: " + ", ".join(wrong)
"""
    result = subprocess.run(
        [sys.executable, "-c", code, module, *enabled],
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
