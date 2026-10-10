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
