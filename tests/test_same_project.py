import os
import subprocess
import tempfile
import unittest

from pitwall.snapshot import same_project


class SameProjectTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = os.path.realpath(self.tmp.name)
        self.repo = os.path.join(self.home, "shop")
        os.makedirs(os.path.join(self.repo, "src"))
        subprocess.run(["git", "init", "-q", self.repo], check=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_subfolder_of_the_same_repo_matches(self):
        self.assertTrue(same_project(os.path.join(self.repo, "src"), self.repo))

    def test_a_parent_folder_outside_the_repo_does_not(self):
        self.assertFalse(same_project(self.home, self.repo))

    def test_folders_outside_any_repo_never_match(self):
        self.assertFalse(same_project(self.home, self.home))


if __name__ == "__main__":
    unittest.main()
