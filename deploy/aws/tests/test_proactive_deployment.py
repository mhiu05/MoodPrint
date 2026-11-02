"""Exercise rendered runtime settings and the deployment health gate without a daemon."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
BASH = ("C:/Program Files/Git/bin/bash.exe" if os.name == "nt" else shutil.which("bash"))


class ProactiveDeploymentTests(unittest.TestCase):
    def test_runtime_file_controls_worker_even_with_conflicting_shell_flag(self):
        with tempfile.TemporaryDirectory() as folder:
            runtime = Path(folder) / "runtime.env"
            for enabled in ("true", "false"):
                with self.subTest(enabled=enabled):
                    runtime.write_text(f"PROACTIVE_WORKER_ENABLED={enabled}\n", encoding="utf-8")
                    env = {**os.environ, "API_IMAGE": "moodprint-api:test",
                           "WEB_IMAGE": "moodprint-web:test", "APP_DOMAIN": "staging.example.org",
                           "API_ENV_FILE": runtime.as_posix(),
                           "PROACTIVE_WORKER_ENABLED": "false" if enabled == "true" else "true"}
                    result = subprocess.run(
                        ["docker", "compose", "-f", str(ROOT / "deploy/compose.staging.yml"),
                         "config", "--format", "json"], env=env, capture_output=True, text=True,
                        check=True,
                    )
                    services = json.loads(result.stdout)["services"]
                    self.assertEqual(services["proactive"]["environment"]["PROACTIVE_WORKER_ENABLED"], enabled)
                    self.assertEqual(services["proactive"]["environment"]["DATABASE_POOL_SIZE"], "2")
                    self.assertEqual(services["proactive"]["environment"]["DATABASE_POOL_OVERFLOW"], "0")

    def health_gate(self, services, worker_health="healthy", config_status=0):
        # Execute the actual function against process boundaries; do not duplicate its logic.
        source = (ROOT / "deploy/aws/deploy.sh").read_text(encoding="utf-8")
        function = source.split("check_health() {", 1)[1].split('\nif "${compose[@]}"', 1)[0]
        script = r'''
set -euo pipefail
compose=(docker compose)
active=unused
APP_DOMAIN=staging.example.org
docker() {
  if [[ "$1" == inspect ]]; then
    if [[ "${*: -1}" == proactive ]]; then printf '%s' "$WORKER_HEALTH"; else printf healthy; fi
  elif [[ " $* " == *" config --services "* ]]; then
    printf '%s\n' "$SERVICES"
    return "$CONFIG_STATUS"
  elif [[ " $* " == *" ps -q "* ]]; then
    printf '%s' "${*: -1}"
  else
    return 2
  fi
}
curl() { return 0; }
sleep() { :; }
''' + "\ncheck_health() {" + function + "\ncheck_health\n"
        return subprocess.run([BASH], input=script, capture_output=True, text=True,
                              env={**os.environ, "SERVICES": services, "WORKER_HEALTH": worker_health,
                                   "CONFIG_STATUS": str(config_status)})

    def test_unhealthy_worker_fails_release_health_gate(self):
        self.assertNotEqual(self.health_gate("api\nweb\nproactive", "unhealthy").returncode, 0)

    def test_healthy_worker_passes_release_health_gate(self):
        result = self.health_gate("api\nweb\nproactive")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_legacy_api_web_compose_still_passes_release_health_gate(self):
        result = self.health_gate("api\nweb", "missing")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_failed_service_discovery_fails_closed(self):
        self.assertNotEqual(self.health_gate("", config_status=1).returncode, 0)


if __name__ == "__main__":
    unittest.main()
