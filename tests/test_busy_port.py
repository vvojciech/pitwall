import unittest

from pitwall.ports import busy_port, holders

LSOF = """p501
cnode
n*:3000
p900
cpython3
n127.0.0.1:8000
"""


class BusyPortTests(unittest.TestCase):
    def test_node_eaddrinuse(self):
        self.assertEqual(busy_port("Error: listen EADDRINUSE: address already in use :::3000"), 3000)

    def test_python_and_vite_messages(self):
        self.assertEqual(busy_port("OSError: [Errno 48] Address already in use (127.0.0.1:8000)"), 8000)
        self.assertEqual(busy_port("Port 5173 is in use, trying another one..."), 5173)
        self.assertEqual(busy_port("Error: Port 4000 is already in use"), 4000)

    def test_rails_and_go(self):
        self.assertEqual(busy_port("Address already in use - bind(2) for \"127.0.0.1\" port 3000 (Errno::EADDRINUSE)"), 3000)
        self.assertEqual(busy_port("listen tcp :8080: bind: address already in use"), 8080)

    def test_the_port_comes_from_the_command_when_the_error_has_none(self):
        error = "OSError: [Errno 48] Address already in use"
        self.assertEqual(busy_port(error, "python3 -m http.server 8798"), 8798)
        self.assertEqual(busy_port(error, "npx serve --port 4100"), 4100)
        self.assertEqual(busy_port(error, "PORT=3001 npm start"), 3001)
        self.assertEqual(busy_port(error, "hugo server -p 1313"), 1313)
        self.assertIsNone(busy_port(error, "make run"))

    def test_unrelated_output(self):
        self.assertIsNone(busy_port("Tests: 1 failed, 11 passed\nport 3000 is fine"))

    def test_holder_of_a_port(self):
        self.assertEqual(holders(LSOF, 8000), [{"pid": 900, "command": "python3"}])
        self.assertEqual(holders(LSOF, 9999), [])


if __name__ == "__main__":
    unittest.main()
