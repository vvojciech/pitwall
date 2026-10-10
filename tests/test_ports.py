import unittest

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


if __name__ == "__main__":
    unittest.main()
