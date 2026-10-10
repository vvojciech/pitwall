import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from pitwall import race


def git(root, *args):
    return subprocess.run(["git", "-C", root, *args], check=True, capture_output=True, text=True).stdout


class RaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = os.path.realpath(self.tmp.name)
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.email", "t@t")
        git(self.repo, "config", "user.name", "t")
        Path(self.repo, "app.py").write_text("print('v1')\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "init")

    def tearDown(self):
        self.tmp.cleanup()

    def test_create_makes_one_worktree_per_agent_hidden_from_git_status(self):
        entries = race.create(self.repo, "r1", ["claude", "codex"])
        self.assertEqual([e["agent"] for e in entries], ["claude", "codex"])
        for e in entries:
            self.assertTrue(Path(e["worktree"], "app.py").is_file())
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")

    def test_two_of_the_same_agent_get_their_own_worktrees(self):
        entries = race.create(self.repo, "r2", ["claude", "claude"])
        self.assertNotEqual(entries[0]["worktree"], entries[1]["worktree"])

    def test_stat_diff_and_apply_include_new_files(self):
        claude, codex = race.create(self.repo, "r3", ["claude", "codex"])
        Path(claude["worktree"], "app.py").write_text("print('v2')\n")
        Path(claude["worktree"], "new.py").write_text("x = 1\n")
        self.assertEqual(race.stat(claude), {"files": 2, "added": 2, "removed": 1})
        self.assertEqual(race.stat(codex), {"files": 0, "added": 0, "removed": 0})
        self.assertIn("+x = 1", race.diff(claude))

        self.assertIsNone(race.apply(self.repo, claude))
        self.assertEqual(Path(self.repo, "app.py").read_text(), "print('v2')\n")
        self.assertEqual(Path(self.repo, "new.py").read_text(), "x = 1\n")
        self.assertEqual(git(self.repo, "diff", "--cached", "--name-only"), "")  # nothing staged

    def test_apply_reports_a_conflict(self):
        (claude,) = race.create(self.repo, "r4", ["claude"])
        Path(claude["worktree"], "app.py").write_text("print('agent')\n")
        Path(self.repo, "app.py").write_text("print('mine')\n")
        self.assertIn("app.py", race.apply(self.repo, claude))
        self.assertEqual(Path(self.repo, "app.py").read_text(), "print('mine')\n")

    def test_clean_up_removes_worktrees_and_branches(self):
        entries = race.create(self.repo, "r5", ["claude", "codex"])
        race.clean_up(self.repo, entries)
        for e in entries:
            self.assertFalse(Path(e["worktree"]).exists())
        self.assertNotIn("pitwall-race", git(self.repo, "branch"))


if __name__ == "__main__":
    unittest.main()
