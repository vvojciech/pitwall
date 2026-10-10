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

    def test_codex_interrupt_hook_fits_its_3_second_limit(self):
        install.edit_hooks(self.path, "codex", ("Stop", "Interrupt"), add=True)
        hooks = json.loads(self.path.read_text())["hooks"]
        timeout = lambda event: [h["timeout"] for e in hooks[event] if install.is_ours(e) for h in e["hooks"]]
        self.assertEqual(timeout("Interrupt"), [3])
        self.assertEqual(timeout("Stop"), [10])

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


class FreshMacTests(unittest.TestCase):
    def test_doctor_runs_without_claude_or_codex(self):
        from contextlib import redirect_stdout
        from io import StringIO
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp, "nothing")
            out = StringIO()
            with mock.patch.object(install, "CLAUDE", missing / ".claude/settings.json"), \
                    mock.patch.object(install, "CODEX", missing / ".codex/hooks.json"), redirect_stdout(out):
                install.doctor()  # must not raise
        self.assertNotIn("Claude Code hooks", out.getvalue())


if __name__ == "__main__":
    unittest.main()
