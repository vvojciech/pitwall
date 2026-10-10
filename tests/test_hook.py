import unittest

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


if __name__ == "__main__":
    unittest.main()
