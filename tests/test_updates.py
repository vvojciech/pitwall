import subprocess
import tempfile
import unittest
from pathlib import Path

from pitwall import updates


def git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


class CheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.origin, self.app, self.dev = root / "origin.git", root / "app", root / "dev"
        git(root, "init", "-q", "--bare", "-b", "main", str(self.origin))
        git(root, "clone", "-q", str(self.origin), str(self.dev))
        for cwd in (self.dev,):
            git(cwd, "config", "user.email", "t@t"), git(cwd, "config", "user.name", "t")
        git(self.dev, "commit", "-q", "--allow-empty", "-m", "one")
        git(self.dev, "tag", "v0.1.0")
        git(self.dev, "push", "-q", "--tags", "origin", "main")
        git(root, "clone", "-q", str(self.origin), str(self.app))

    def tearDown(self):
        self.tmp.cleanup()

    def test_up_to_date(self):
        self.assertEqual(updates.check(self.app), {"behind": 0, "latest": "v0.1.0"})

    def test_new_commits_and_tag_upstream(self):
        git(self.dev, "commit", "-q", "--allow-empty", "-m", "two")
        git(self.dev, "commit", "-q", "--allow-empty", "-m", "three")
        git(self.dev, "tag", "v0.2.0")
        git(self.dev, "push", "-q", "--tags", "origin", "main")
        self.assertEqual(updates.check(self.app), {"behind": 2, "latest": "v0.2.0"})

    def test_no_remote_gives_none(self):
        git(self.app, "remote", "remove", "origin")
        self.assertIsNone(updates.check(self.app))

    def test_not_a_repository_gives_none(self):
        self.assertIsNone(updates.check(Path(self.tmp.name)))


if __name__ == "__main__":
    unittest.main()
