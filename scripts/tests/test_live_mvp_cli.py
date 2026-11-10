"""The opt-in live acceptance CLI must support help without reading owner settings."""

import os
import subprocess
import sys
from pathlib import Path


def test_live_mvp_filename_entrypoint_works_outside_repository(tmp_path):
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, str(root / "scripts/live_mvp_check.py"), "--help"],
        cwd=tmp_path,
        env={**os.environ, "APP_ENV": "test"},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "--group" in result.stdout
