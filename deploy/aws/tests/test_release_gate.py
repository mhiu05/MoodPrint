import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from release_gate import render_gate


class ReleaseGateTests(unittest.TestCase):
    def test_gate_preserves_api_routing_and_exempts_only_health_and_test_header(self):
        source = (Path(__file__).resolve().parents[2] / 'Caddyfile').read_text()
        result = render_gate(source, 'release-test-token-that-is-at-least-32-characters')
        self.assertIn('not path /api/v1/health/live /api/v1/health/ready', result)
        self.assertIn('not header X-MoodPrint-Release-Test', result)
        self.assertIn('handle @releaseGate', result)
        self.assertIn('reverse_proxy api:8001', result)
        self.assertIn('Retry-After', result)
        self.assertIn('503', result)

    def test_rejects_config_injection_or_missing_domain_anchor(self):
        for token in ['short', 'x' * 32 + '\nrespond 200', 'x' * 32 + '"']:
            with self.assertRaises(ValueError):
                render_gate('{$APP_DOMAIN} {\n}\n', token)
        with self.assertRaises(ValueError):
            render_gate('example.org {\n}\n', 'x' * 32)


if __name__ == '__main__':
    unittest.main()
