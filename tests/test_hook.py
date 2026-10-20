import io
import json
import unittest
from contextlib import redirect_stdout
from unittest import mock

from pitwall import hook, settings
from pitwall.hook import agent_depth, parse_ps

PS = """\
    1     0 /sbin/launchd
  100     1 /Applications/iTerm.app/Contents/MacOS/iTerm2
  200   100 -zsh
  300   200 claude
  310   300 /bin/zsh
  320   310 /opt/homebrew/Caskroom/claude-code@latest/2.1.283/claude
  330   320 /bin/sh
  400   300 /bin/sh
"""


class AgentDepthTests(unittest.TestCase):
    def test_a_hook_of_the_top_agent_has_depth_one(self):
        self.assertEqual(agent_depth(parse_ps(PS), 400), 1)

    def test_a_hook_of_a_nested_agent_has_depth_two(self):
        self.assertEqual(agent_depth(parse_ps(PS), 330), 2)

    def test_a_loop_in_the_table_ends(self):
        self.assertEqual(agent_depth({5: (6, "claude"), 6: (5, "claude")}, 5), 2)


def prefs(**off):
    return dict(settings.DEFAULTS, **{k: False for k in off})


class SettingsInHookTests(unittest.TestCase):
    def run_hook(self, name, payload, current):
        posted = []
        with mock.patch.object(hook.settings, "current", return_value=current), \
                mock.patch.object(hook.config, "read_daemon", return_value={"port": 1, "token": "t"}), \
                mock.patch.object(hook, "nested", return_value=False), \
                mock.patch.object(hook, "post", side_effect=lambda d, p, e: posted.append(e)), \
                mock.patch.object(hook.snapshot, "take", return_value={"tree": "abc"}) as take, \
                mock.patch.object(hook, "context_for", return_value="notes"), \
                mock.patch.dict("os.environ", {"ITERM_SESSION_ID": "w0t0p0:ABC"}), \
                mock.patch("sys.stdin", io.StringIO(json.dumps(payload))), \
                redirect_stdout(io.StringIO()) as out:
            hook.run("claude", name)
        return posted, take, out.getvalue()

    def test_a_prompt_takes_a_snapshot_when_undo_is_on(self):
        posted, take, _ = self.run_hook("UserPromptSubmit", {"cwd": "/repo", "prompt": "fix it"}, prefs())
        take.assert_called_once_with("/repo")
        self.assertEqual(posted[0]["snapshot"], {"tree": "abc"})

    def test_a_prompt_takes_no_snapshot_when_undo_is_off(self):
        posted, take, _ = self.run_hook("UserPromptSubmit", {"cwd": "/repo", "prompt": "fix it"}, prefs(undo=1))
        take.assert_not_called()
        self.assertNotIn("snapshot", posted[0])

    def test_shared_memory_is_printed_when_on(self):
        _, _, out = self.run_hook("SessionStart", {"cwd": "/repo"}, prefs())
        self.assertIn("notes", out)

    def test_shared_memory_is_not_printed_when_off(self):
        posted, _, out = self.run_hook("SessionStart", {"cwd": "/repo"}, prefs(shared_memory=1))
        self.assertEqual(out, "")
        self.assertEqual(len(posted), 1)  # the card still gets the event


if __name__ == "__main__":
    unittest.main()
