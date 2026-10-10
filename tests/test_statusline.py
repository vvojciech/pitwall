import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from pitwall import install

REPO = Path(__file__).resolve().parent.parent


class StatusLineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.settings = self.home / "settings.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_wrapper_saves_input_and_runs_the_original(self):
        (self.home / "statusline-command").write_text("cat | wc -c | tr -d ' '")
        out = subprocess.run(["bash", str(REPO / "bin/pitwall-statusline")], input='{"rate_limits":{}}',
                             capture_output=True, text=True, env=dict(os.environ, PITWALL_HOME=str(self.home)))
        self.assertEqual(out.stdout.strip(), "18")
        self.assertEqual(json.loads((self.home / "claude-status.json").read_text()), {"rate_limits": {}})

    def test_wrap_and_unwrap_keep_the_original(self):
        self.settings.write_text(json.dumps({"statusLine": {"type": "command", "command": "bash ~/s.sh"}, "x": 1}))
        install.wrap_statusline(self.settings, self.home, add=True)
        install.wrap_statusline(self.settings, self.home, add=True)  # twice is safe
        data = json.loads(self.settings.read_text())
        self.assertIn("pitwall-statusline", data["statusLine"]["command"])
        self.assertEqual((self.home / "statusline-command").read_text(), "bash ~/s.sh")
        install.wrap_statusline(self.settings, self.home, add=False)
        self.assertEqual(json.loads(self.settings.read_text()),
                         {"statusLine": {"type": "command", "command": "bash ~/s.sh"}, "x": 1})

    def test_no_status_line_before_means_none_after(self):
        self.settings.write_text("{}")
        install.wrap_statusline(self.settings, self.home, add=True)
        self.assertIn("pitwall-statusline", json.loads(self.settings.read_text())["statusLine"]["command"])
        install.wrap_statusline(self.settings, self.home, add=False)
        self.assertEqual(json.loads(self.settings.read_text()), {})


if __name__ == "__main__":
    unittest.main()
