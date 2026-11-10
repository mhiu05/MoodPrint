import json
import os
import subprocess
import sys
from pathlib import Path


def test_approval_resumes_in_separate_python_process_without_auth(tmp_path: Path) -> None:
    worker = Path(__file__).with_name("_approval_process.py")
    env = dict(os.environ)
    env.pop("OPENAI_API_KEY", None)
    env["APP_ENV"] = "test"
    for stage in ("start", "resume"):
        result = subprocess.run(
            [sys.executable, str(worker), stage, str(tmp_path)],
            env=env,
            capture_output=True,
            text=True,
            timeout=45,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        if stage == "start":
            assert not (tmp_path / "executed.txt").exists()
            assert "process-auth-canary" not in (tmp_path / "checkpoint.json").read_text(
                encoding="utf-8"
            )
    assert (tmp_path / "executed.txt").read_text(encoding="utf-8") == "synthetic persisted note"
    start = json.loads((tmp_path / "start.json").read_text(encoding="utf-8"))
    resumed = json.loads((tmp_path / "resume.json").read_text(encoding="utf-8"))
    assert start[-1]["data"]["status"] == "awaiting_approval"
    assert resumed[-1]["data"]["status"] == "completed"
    assert resumed[0]["seq"] > start[-1]["seq"]
