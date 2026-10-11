import json
import os
import subprocess
import tempfile
import time
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

    def test_wrapper_keeps_one_status_per_session(self):
        for sid in ("aaa-111", "bbb-222"):
            subprocess.run(["bash", str(REPO / "bin/pitwall-statusline")],
                           input=json.dumps({"session_id": sid, "context_window": {"used_percentage": 5}}),
                           capture_output=True, text=True, env=dict(os.environ, PITWALL_HOME=str(self.home)))
        self.assertEqual(sorted(p.name for p in (self.home / "status").iterdir()), ["aaa-111.json", "bbb-222.json"])

    def test_an_idle_session_gets_the_newest_limits(self):
        (self.home / "statusline-command").write_text("cat")
        reset = int(time.time()) + 3600
        run = lambda sid, limits: subprocess.run(
            ["bash", str(REPO / "bin/pitwall-statusline")], input=json.dumps({"session_id": sid, "rate_limits": limits}),
            capture_output=True, text=True, env=dict(os.environ, PITWALL_HOME=str(self.home))).stdout
        run("busy-1", {"five_hour": {"used_percentage": 4, "resets_at": reset},
                       "seven_day": {"used_percentage": 84, "resets_at": reset}})
        out = json.loads(run("idle-2", {"seven_day": {"used_percentage": 69, "resets_at": reset}}))
        self.assertEqual(out["session_id"], "idle-2")
        self.assertEqual(out["rate_limits"], {"five_hour": {"used_percentage": 4, "resets_at": reset},
                                              "seven_day": {"used_percentage": 84, "resets_at": reset}})

    def test_a_strange_session_id_is_not_used_as_a_file_name(self):
        subprocess.run(["bash", str(REPO / "bin/pitwall-statusline")], input='{"session_id":"../../evil"}',
                       capture_output=True, text=True, env=dict(os.environ, PITWALL_HOME=str(self.home)))
        self.assertFalse((self.home / "status").exists() and any((self.home / "status").iterdir()))

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
