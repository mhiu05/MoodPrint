"""Storage capabilities must work through the production proxy's document CSP."""

import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASH = "C:/Program Files/Git/bin/bash.exe" if os.name == "nt" else shutil.which("bash")


class JournalStorageDeploymentTests(unittest.TestCase):
    def origins(self, runtime):
        source = (ROOT / "deploy/aws/deploy.sh").read_text(encoding="utf-8")
        self.assertIn("journal_storage_origins() {", source)
        function = source.split("journal_storage_origins() {", 1)[1].split("\n}\n", 1)[0]
        python = f"python3() {{ {shlex.quote(Path(sys.executable).as_posix())} \"$@\"; }}\n" if os.name == "nt" else ""
        with tempfile.TemporaryDirectory() as folder:
            runtime_file = Path(folder) / "runtime.env"
            runtime_file.write_text(runtime, encoding="utf-8")
            setup = f"base={shlex.quote((ROOT / 'deploy').as_posix())}\napi_ref=moodprint-api:test\nweb_ref=moodprint-web:test\nAPP_DOMAIN=staging.example.org\n"
            script = python + setup + "journal_storage_origins() {" + function + f'\n}}\njournal_storage_origins {shlex.quote(runtime_file.as_posix())}\n'
            return subprocess.run([BASH], input=script, text=True, capture_output=True, check=False)

    def test_only_configured_storage_origins_reach_the_proxy(self):
        for url, expected in (
            ("https://project.supabase.co", "https://project.supabase.co https://project.storage.supabase.co"),
            ("https://project.storage.supabase.co", "https://project.storage.supabase.co"),
            ("https://storage.example.org/", "https://storage.example.org"),
        ):
            with self.subTest(url=url):
                result = self.origins(f"SUPABASE_URL={url}\nJOURNAL_STORAGE_KEY=synthetic-private\n")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), expected)
                self.assertNotIn("synthetic-private", result.stdout + result.stderr)

    def test_disabled_storage_stays_same_origin_and_dotenv_last_assignment_wins(self):
        for runtime in (
            "", "SUPABASE_URL=https://project.supabase.co\n",
            "SUPABASE_URL=https://project.supabase.co\nJOURNAL_STORAGE_KEY=''\n",
            "SUPABASE_URL=https://project.supabase.co\nJOURNAL_STORAGE_KEY=synthetic\nJOURNAL_STORAGE_KEY=\n",
            "JOURNAL_STORAGE_ORIGINS=https://evil.example\n",
        ):
            result = self.origins(runtime)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "")
        result = self.origins("export SUPABASE_URL = 'https://project.supabase.co/' # project\r\nJOURNAL_STORAGE_KEY=\"synthetic\"\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "https://project.supabase.co https://project.storage.supabase.co")

    def test_csp_injection_and_non_origin_urls_are_rejected_without_echoing_input(self):
        for url in (
            "http://project.supabase.co", "https://user:private@storage.example.org",
            "https://storage.example.org/path", "https://storage.example.org?secret=private",
            "https://storage.example.org#fragment", "https://storage.example.org; script-src *",
            "https://*.supabase.co", "https://storage.example.org:443",
        ):
            result = self.origins(f"SUPABASE_URL={url}\nJOURNAL_STORAGE_KEY=synthetic-private\n")
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")
            self.assertNotIn(url, result.stderr)
            self.assertNotIn("synthetic-private", result.stderr)

    def test_origins_use_the_same_dotenv_interpolation_as_the_api(self):
        result = self.origins(
            "SUPABASE_BASE_URL=https://project.supabase.co\n"
            "SUPABASE_URL=${SUPABASE_BASE_URL}\n"
            "STORAGE_CREDENTIAL=synthetic-private\n"
            "JOURNAL_STORAGE_KEY=${STORAGE_CREDENTIAL}\n"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "https://project.supabase.co https://project.storage.supabase.co")
        result = self.origins("SUPABASE_URL=https://project.supabase.co\nJOURNAL_STORAGE_KEY=${MISSING_JOURNAL_KEY_FOR_TEST:-}\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "")

    def test_caddy_allows_storage_only_for_connection_images_and_media(self):
        result = subprocess.run(
            ["docker", "run", "--rm", "-i", "--network", "none", "-e", "APP_DOMAIN=:80",
             "-e", "JOURNAL_STORAGE_ORIGINS=https://project.supabase.co https://project.storage.supabase.co",
             "caddy:2", "caddy", "adapt", "--adapter", "caddyfile", "--config", "-"],
            input=(ROOT / "deploy/Caddyfile").read_text(encoding="utf-8"), text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        config = json.loads(result.stdout)

        def policies(node):
            if isinstance(node, dict):
                for key, value in node.items():
                    if key.lower() == "content-security-policy":
                        yield from value
                    else:
                        yield from policies(value)
            elif isinstance(node, list):
                for value in node:
                    yield from policies(value)

        policy, = policies(config)
        directives = {part.strip().split()[0]: part.strip().split()[1:] for part in policy.split(";") if part.strip()}
        for directive in ("connect-src", "img-src", "media-src"):
            self.assertIn("https://project.supabase.co", directives[directive])
            self.assertIn("https://project.storage.supabase.co", directives[directive])
        for directive in ("script-src", "frame-src", "default-src"):
            self.assertNotIn("https://project.supabase.co", directives[directive])
        self.assertNotIn("*.supabase.co", policy)
        self.assertNotIn("unsafe-inline", policy)
        self.assertNotIn("unsafe-eval", policy)

    def test_compose_passes_public_origins_to_web_without_server_key(self):
        with tempfile.TemporaryDirectory() as folder:
            runtime = Path(folder) / "runtime.env"
            runtime.write_text("JOURNAL_STORAGE_KEY=synthetic-private\n", encoding="utf-8")
            origins = "https://project.supabase.co https://project.storage.supabase.co"
            result = subprocess.run(
                ["docker", "compose", "-f", str(ROOT / "deploy/compose.staging.yml"), "config", "--format", "json"],
                env={**os.environ, "API_IMAGE": "moodprint-api:test", "WEB_IMAGE": "moodprint-web:test",
                     "APP_DOMAIN": "staging.example.org", "API_ENV_FILE": runtime.as_posix(),
                     "JOURNAL_STORAGE_ORIGINS": origins}, text=True, capture_output=True, check=False,
            )
            self.assertEqual(result.returncode, 0, "Compose failed to render synthetic config")
            services = json.loads(result.stdout)["services"]
            self.assertEqual(services["web"]["environment"]["JOURNAL_STORAGE_ORIGINS"], origins)
            self.assertNotIn("synthetic-private", json.dumps(services["web"]))
            self.assertEqual(services["api"]["environment"]["JOURNAL_STORAGE_KEY"], "synthetic-private")


if __name__ == "__main__":
    unittest.main()
