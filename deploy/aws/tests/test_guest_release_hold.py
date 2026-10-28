import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from release_hold import release_held


class GuestReleaseHoldTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'deploy').mkdir()
        self.marker = self.root / 'deploy/guest-experience.release-hold'

    def test_marker_blocks_release(self):
        self.marker.write_text('Owner approval required.', encoding='utf-8')
        self.assertTrue(release_held(self.root))

    def test_absent_marker_preserves_release_path(self):
        self.assertFalse(release_held(self.root))

    def test_nonregular_or_uninspectable_marker_fails_closed(self):
        self.marker.mkdir()
        self.assertTrue(release_held(self.root))
        self.marker.rmdir()
        with patch.object(Path, 'lstat', side_effect=PermissionError('injected')):
            self.assertTrue(release_held(self.root))
        try:
            self.marker.symlink_to(self.root / 'missing')
        except OSError:
            pass  # Windows can require an additional symlink privilege.
        else:
            self.assertTrue(release_held(self.root))

    def cli(self, output):
        environment = {**os.environ, 'GITHUB_OUTPUT': str(output)}
        return subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parents[1] / 'release_hold.py'),
             '--root', str(self.root)], env=environment, capture_output=True, text=True,
            check=False,
        )

    def test_cli_writes_runner_output_and_errors_cannot_enable_release(self):
        output = self.root / 'output'
        self.assertEqual(self.cli(output).returncode, 0)
        self.assertEqual(output.read_text().splitlines(), ['held=false'])
        self.marker.touch()
        self.assertEqual(self.cli(output).returncode, 0)
        self.assertEqual(output.read_text().splitlines(), ['held=false', 'held=true'])
        self.assertNotEqual(self.cli(self.root / 'missing/output').returncode, 0)
        self.assertNotEqual(self.cli(self.root).returncode, 0)


if __name__ == '__main__':
    unittest.main()
