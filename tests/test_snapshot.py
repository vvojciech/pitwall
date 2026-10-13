import os
import subprocess
import tempfile
import time
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

    def test_a_same_size_edit_in_the_index_second_is_seen(self):
        # "Racy git": the file changes with its size and mtime equal to what the index recorded.
        index = os.path.join(self.root, ".git", "index")
        stamp = os.stat(index).st_mtime
        self.write("keep.txt", "v9")  # same size as "v1"
        os.utime(Path(self.root, "keep.txt"), (stamp, stamp))
        time.sleep(1.1)  # the snapshot runs in a later second than the index write
        snap = snapshot.take(self.root)
        files = git(self.root, "ls-tree", "-r", snap["tree"], "keep.txt").split()
        self.assertEqual(git(self.root, "cat-file", "-p", files[2]), "v9")

    def test_restore_keeps_the_staged_index(self):
        self.write("keep.txt", "staged")
        git(self.root, "add", "keep.txt")
        snap = snapshot.take(self.root)
        self.write("keep.txt", "agent")
        snapshot.restore(snap["root"], snap["tree"])
        self.assertEqual(self.read("keep.txt"), "staged")
        self.assertEqual(git(self.root, "diff", "--cached", "--name-only").split(), ["keep.txt"])
        self.assertEqual(git(self.root, "stash", "list"), "")

    def test_live_drops_snapshots_of_a_removed_folder(self):
        kept = snapshot.take(self.root)
        gone = {"root": os.path.join(self.root, "removed-worktree"), "tree": kept["tree"]}
        self.assertEqual(snapshot.live([gone, kept]), [kept])

    def test_take_works_from_a_subfolder(self):
        self.write("sub/a.txt", "a")
        snap = snapshot.take(os.path.join(self.root, "sub"))
        self.assertEqual(snap["root"], self.root)

    def test_diff_ignores_a_configured_external_diff_tool(self):
        # A user's diff.external (difft, say) is not on the service's PATH and prints no patch.
        git(self.root, "config", "diff.external", "no-such-diff-tool")
        snap = snapshot.take(self.root)
        self.write("keep.txt", "v2")
        patch = snapshot.diff(snap["root"], snap["tree"])
        self.assertIn("-v1", patch)
        self.assertIn("+v2", patch)


if __name__ == "__main__":
    unittest.main()
