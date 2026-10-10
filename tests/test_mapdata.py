import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from pitwall import mapdata, snapshot


def git(root, *args):
    return subprocess.run(["git", "-C", root, *args], check=True, capture_output=True, text=True).stdout


class MapDataTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = os.path.realpath(self.tmp.name)
        git(self.root, "init", "-q")
        git(self.root, "config", "user.email", "t@t")
        git(self.root, "config", "user.name", "t")
        Path(self.root, "a.py").write_text("x = 1\n")
        Path(self.root, "b.py").write_text("y = 1\n")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "init")
        Path(self.root, "a.py").write_text("x = 2\n")  # changed before the agent's prompt
        self.s = {"cwd": self.root, "agent": "claude", "state": "working", "touched": {}, "current": None,
                  "snapshots": [snapshot.take(self.root)]}
        Path(self.root, "b.py").write_text("y = 2\nz = 3\n")  # the agent's turn, through a shell command
        Path(self.root, "c.py").write_text("new\n")

    def tearDown(self):
        self.tmp.cleanup()

    def files(self, graph):
        return sorted(n["id"] for n in graph["nodes"] if n["kind"] == "file")

    def test_this_turn_is_since_the_prompt(self):
        g = mapdata.map_for(self.s, "turn")
        self.assertEqual(self.files(g), ["b.py", "c.py"])
        self.assertEqual((g["stats"]["added"], g["stats"]["removed"]), (3, 1))

    def test_uncommitted_is_since_the_last_commit(self):
        g = mapdata.map_for(self.s, "uncommitted")
        self.assertEqual(self.files(g), ["a.py", "b.py", "c.py"])

    def test_uncommitted_ignores_files_that_were_only_read(self):
        Path(self.root, "z.py").write_text("q = 1\n")
        git(self.root, "add", "z.py")
        git(self.root, "commit", "-qm", "z")
        self.s["touched"] = {f"{self.root}/z.py": "read"}
        mapdata._files.clear()  # the file list is cached; z.py is new
        self.assertNotIn("z.py", self.files(mapdata.map_for(self.s, "uncommitted")))

    def test_without_a_snapshot_this_turn_shows_only_what_the_hooks_saw(self):
        self.s["snapshots"] = []
        self.s["touched"] = {f"{self.root}/a.py": "read"}
        self.assertEqual(self.files(mapdata.map_for(self.s, "turn")), ["a.py"])


if __name__ == "__main__":
    unittest.main()
