"""The proxy must allow Turnstile when either registered or guest Auth needs it."""
import os
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASH = "C:/Program Files/Git/bin/bash.exe" if os.name == "nt" else shutil.which("bash")


class CaptchaDeploymentTests(unittest.TestCase):
    def test_runtime_auth_flags_choose_only_the_fixed_turnstile_origin(self):
        source = (ROOT / "deploy/aws/deploy.sh").read_text(encoding="utf-8")
        function = source.split("captcha_origin() {", 1)[1].split("\n}\n", 1)[0]
        cases = (
            ("AUTH_CAPTCHA_ENABLED=true\nGUEST_AUTH_ENABLED=false\n", "https://challenges.cloudflare.com"),
            ("AUTH_CAPTCHA_ENABLED=false\nGUEST_AUTH_ENABLED=true\n", "https://challenges.cloudflare.com"),
            ("AUTH_CAPTCHA_ENABLED=false\nGUEST_AUTH_ENABLED=false\n", ""),
            ("GUEST_CAPTCHA_ORIGIN=https://evil.example\n", ""),
            ('AUTH_CAPTCHA_ENABLED="true"\n', "https://challenges.cloudflare.com"),
            ("AUTH_CAPTCHA_ENABLED='true' # enabled\n", "https://challenges.cloudflare.com"),
            ("AUTH_CAPTCHA_ENABLED=true # enabled\n", "https://challenges.cloudflare.com"),
            ("AUTH_CAPTCHA_ENABLED=TRUE\r\n", "https://challenges.cloudflare.com"),
            ("AUTH_CAPTCHA_ENABLED=true\nAUTH_CAPTCHA_ENABLED=false\n", ""),
            ("export GUEST_AUTH_ENABLED = yes\n", "https://challenges.cloudflare.com"),
        )
        for runtime, expected in cases:
            with self.subTest(runtime=runtime):
                script = "captcha_origin() {" + function + '\n}\ncaptcha_origin <(printf \'%s\' "$RUNTIME_CONTENT")\n'
                result = subprocess.run([BASH], input=script, text=True, capture_output=True,
                                        env={**os.environ, "RUNTIME_CONTENT": runtime})
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), expected)


if __name__ == "__main__":
    unittest.main()
