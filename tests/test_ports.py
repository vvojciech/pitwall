import unittest

from pitwall.devserver import is_dev_server
from pitwall.ports import listeners, parse_cwds

LSOF = """p501
cnode
f22
n*:3000
f23
n[::1]:3000
p777
cControlCe
f9
n*:7000
p900
cpython3.12
f4
n127.0.0.1:8000
"""
CWDS = """p501
fcwd
n/Users/w/code/shop
p777
fcwd
n/
p900
fcwd
n/Users/w/code/api
"""


class PortTests(unittest.TestCase):
    def test_listeners_keep_project_servers_only(self):
        found = listeners(LSOF, parse_cwds(CWDS), home="/Users/w")
        self.assertEqual([(p["port"], p["pid"], p["command"], p["project"]) for p in found],
                         [(3000, 501, "node", "shop"), (8000, 900, "python3.12", "api")])


class DevServerLogTests(unittest.TestCase):
    def test_the_log_is_inside_the_project_and_hidden_from_git(self):
        import os, subprocess, tempfile
        from pitwall.devserver import log_path
        with tempfile.TemporaryDirectory() as tmp:
            root = os.path.realpath(tmp)
            subprocess.run(["git", "init", "-q", root], check=True)
            os.makedirs(os.path.join(root, "web"))
            log = log_path(os.path.join(root, "web"), "20261010-120000")
            self.assertEqual(str(log), os.path.join(root, ".pitwall", "dev-web-20261010-120000.log"))
            log.write_text("x")
            status = subprocess.run(["git", "-C", root, "status", "--porcelain"], capture_output=True, text=True).stdout
            self.assertEqual(status, "")
            log_path(root, "20261010-120001")  # a second log does not add the exclude line twice
            exclude = open(os.path.join(root, ".git", "info", "exclude")).read()
            self.assertEqual(exclude.count("/.pitwall/"), 1)

    def test_outside_git_the_log_goes_to_the_pitwall_folder(self):
        import tempfile
        from pitwall import config
        from pitwall.devserver import log_path
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(log_path(tmp, "t").parent, config.HOME / "logs")


class DevServerTests(unittest.TestCase):
    def test_dev_servers_match(self):
        for command in ("npm run dev", "pnpm dev", "cd web && yarn dev", "npx next dev -p 3001", "vite",
                        "bun run start", "rails s", "python manage.py runserver", "make dev"):
            self.assertTrue(is_dev_server(command), command)

    def test_other_commands_do_not(self):
        for command in ("npm test", "npm run build", "npm run dev -- --help", "grep dev file", "npm run dev && npm test",
                        "echo npm run dev", "vitest", "next build"):
            self.assertFalse(is_dev_server(command), command)


if __name__ == "__main__":
    unittest.main()
