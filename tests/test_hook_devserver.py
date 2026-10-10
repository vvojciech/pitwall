import io
import json
import unittest
from contextlib import redirect_stdout
from unittest import mock

from pitwall import hook

EVENT = {"sid": "A", "cwd": "/work/shop"}


def run(command, env=None):
    payload = {"tool_name": "Bash", "tool_input": {"command": command}}
    out = io.StringIO()
    with mock.patch.object(hook, "post", return_value={"log": "/h/shop.log"}) as post, \
            mock.patch.dict("os.environ", env or {}), redirect_stdout(out):
        hook.move_dev_server({"port": 1, "token": "t"}, EVENT, payload)
    return post, out.getvalue()


class DevServerHookTests(unittest.TestCase):
    def test_a_dev_server_is_moved_and_claude_is_told_where_the_log_is(self):
        post, out = run("npm run dev")
        post.assert_called_once()
        decision = json.loads(out)["hookSpecificOutput"]
        self.assertEqual(decision["permissionDecision"], "deny")
        self.assertIn("tail -n 40 /h/shop.log", decision["permissionDecisionReason"])

    def test_other_commands_pass(self):
        post, out = run("npm test")
        post.assert_not_called()
        self.assertEqual(out, "")

    def test_it_can_be_turned_off(self):
        post, out = run("npm run dev", {"PITWALL_DEV_TABS": "0"})
        post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
