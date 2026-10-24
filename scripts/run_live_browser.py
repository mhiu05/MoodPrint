"""Run live browser checks against evals.server and Vite already listening on loopback."""

import base64
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def main():
    values = dotenv_values(ROOT / "backend/.env")
    environment = {**os.environ}
    audio = ROOT / "docs/plans/validation-artifacts/live-ai/voice-synthetic.wav"
    if not audio.exists():
        audio = Path(tempfile.gettempdir()) / "moodprint-live-voice.wav"
    if audio.exists():
        environment["MOODPRINT_TEST_AUDIO"] = str(audio)
    for actor in ("A", "B"):
        prefix = f"MOODPRINT_TEST_{actor}_"
        password = values.get(prefix + "PASSWORD")
        if values.get(prefix + "PASSWORD_B64"):
            password = base64.b64decode(values[prefix + "PASSWORD_B64"]).decode()
        if not values.get(prefix + "EMAIL") or not password:
            raise ValueError("Two configured synthetic accounts are required")
        environment.update({prefix + "EMAIL": values[prefix + "EMAIL"], prefix + "PASSWORD": password})
    return subprocess.run(["node", "node_modules/@playwright/test/cli.js", "test", "--config", "playwright.live.config.ts", *sys.argv[1:]],
                          cwd=ROOT / "frontend", env=environment, timeout=510, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
