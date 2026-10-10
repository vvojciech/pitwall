import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from pitwall import snapshot


def git(root, *args):
    return subprocess.run(["git", "-C", root, *args], check=True, capture_output=True, text=True).stdout


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = os.path.realpath(self.tmp.name)
        git(self.root, "init", "-q")
        git(self.root, "config", "user.email", "t@t")
        git(self.root, "config", "user.name", "t")
        self.write("keep.txt", "v1")
        self.write(".gitignore", "ignored/\n")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "init")

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, rel, text):
        p = Path(self.root, rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def read(self, rel):
        return Path(self.root, rel).read_text()

    def test_outside_git_gives_none(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(snapshot.take(d))

    def test_undo_restores_edits_deletes_and_new_files(self):
        self.write("untracked.txt", "mine")
        snap = snapshot.take(os.path.join(self.root))
        # The agent's turn.
        self.write("keep.txt", "v2")
        os.remove(Path(self.root, "untracked.txt"))
        self.write("src/new.ts", "agent file")
        self.write("ignored/cache.bin", "x")

        changes = snapshot.preview(snap["root"], snap["tree"])
        self.assertEqual(sorted(changes), [("delete", "src/new.ts"), ("restore", "keep.txt"), ("restore", "untracked.txt")])

        redo = snapshot.restore(snap["root"], snap["tree"])
        self.assertEqual(self.read("keep.txt"), "v1")
        self.assertEqual(self.read("untracked.txt"), "mine")
        self.assertFalse(Path(self.root, "src").exists())
        self.assertEqual(self.read("ignored/cache.bin"), "x")

        snapshot.restore(redo["root"], redo["tree"])
        self.assertEqual(self.read("keep.txt"), "v2")
        self.assertEqual(self.read("src/new.ts"), "agent file")

    def test_restore_keeps_the_staged_index(self):
        self.write("keep.txt", "staged")
        git(self.root, "add", "keep.txt")
        snap = snapshot.take(self.root)
        self.write("keep.txt", "agent")
        snapshot.restore(snap["root"], snap["tree"])
        self.assertEqual(self.read("keep.txt"), "staged")
        self.assertEqual(git(self.root, "diff", "--cached", "--name-only").split(), ["keep.txt"])
        self.assertEqual(git(self.root, "stash", "list"), "")

    def test_take_works_from_a_subfolder(self):
        self.write("sub/a.txt", "a")
        snap = snapshot.take(os.path.join(self.root, "sub"))
        self.assertEqual(snap["root"], self.root)


if __name__ == "__main__":
    unittest.main()
