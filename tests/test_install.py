import json
import tempfile
import unittest
from pathlib import Path

from pitwall import install


class EditHooksTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name, "settings.json")
        other = {"hooks": [{"type": "command", "command": "other-tool"}]}
        self.path.write_text(json.dumps({"model": "x", "hooks": {"Stop": [other]}}))

    def tearDown(self):
        self.tmp.cleanup()

    def hooks(self):
        return json.loads(self.path.read_text())["hooks"]

    def test_add_keeps_other_hooks_and_is_idempotent(self):
        install.edit_hooks(self.path, "claude", ("Stop", "SessionEnd"), add=True)
        install.edit_hooks(self.path, "claude", ("Stop", "SessionEnd"), add=True)
        hooks = self.hooks()
        self.assertEqual(len(hooks["Stop"]), 2)
        self.assertEqual(hooks["Stop"][0]["hooks"][0]["command"], "other-tool")
        self.assertIn('/bin/pitwall" hook claude Stop', hooks["Stop"][1]["hooks"][0]["command"])
        self.assertEqual(len(hooks["SessionEnd"]), 1)
        self.assertEqual(json.loads(self.path.read_text())["model"], "x")

    def test_remove_restores_the_original(self):
        install.edit_hooks(self.path, "claude", ("Stop", "SessionEnd"), add=True)
        install.edit_hooks(self.path, "claude", ("Stop", "SessionEnd"), add=False)
        self.assertEqual(self.hooks(), {"Stop": [{"hooks": [{"type": "command", "command": "other-tool"}]}]})

    def test_a_backup_is_kept_only_when_the_file_changes(self):
        install.edit_hooks(self.path, "claude", ("Stop",), add=True)
        before = self.path.read_text()
        install.edit_hooks(self.path, "claude", ("Stop",), add=True)  # a second install changes nothing
        self.assertEqual(self.path.read_text(), before)
        self.assertEqual(len(list(Path(self.tmp.name).glob("settings.json.pitwall-backup-*"))), 1)


if __name__ == "__main__":
    unittest.main()
