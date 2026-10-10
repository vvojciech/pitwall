import unittest

from pitwall.handoff import build, failure_message, launch_command

SESSION = {"agent": "claude", "cwd": "/work/shop", "task": "Fix the login redirect"}
TIMELINE = [{"kind": "prompt", "text": "Fix the login redirect"}, {"kind": "tool", "text": "Edit auth.ts"}]
FAILURE = {"command": "npm test", "status": 1, "cwd": "/work/shop", "output": "FAIL auth.test.ts\n1 failed"}


class HandoffTests(unittest.TestCase):
    def test_review_says_not_to_edit(self):
        text = build(SESSION, "review", TIMELINE, "diff --git a/auth.ts", [FAILURE])
        self.assertIn("Do not edit", text)
        self.assertIn("Fix the login redirect", text)
        self.assertIn("- tool: Edit auth.ts", text)
        self.assertIn("diff --git a/auth.ts", text)
        self.assertIn("$ npm test", text)

    def test_a_huge_diff_is_cut(self):
        text = build(SESSION, "continue", [], "x" * 200_000, [])
        self.assertLess(len(text), 60_000)
        self.assertIn("cut", text)

    def test_no_diff_says_so(self):
        self.assertIn("No snapshot", build(SESSION, "continue", [], None, []))

    def test_launch_command_quotes_the_prompt(self):
        self.assertEqual(launch_command("codex", "/work/my shop", "/h/x.md"),
                         "cd '/work/my shop' && codex 'Read the hand-off in /h/x.md and follow its instructions.'")

    def test_failure_message(self):
        text = failure_message(FAILURE)
        self.assertIn("exit 1", text)
        self.assertIn("1 failed", text)


if __name__ == "__main__":
    unittest.main()
