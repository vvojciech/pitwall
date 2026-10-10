import unittest

from pitwall.state import apply, discover


def found(sid, job, cwd="/p/app"):
    return {"sid": sid, "job": job, "cwd": cwd}


class DiscoverTests(unittest.TestCase):
    def test_a_running_agent_without_hooks_gets_an_idle_card(self):
        sessions = {}
        changed = discover(sessions, [found("A", "claude"), found("B", "zsh"), found("C", "codex")], 50.0)
        self.assertEqual(sorted(sessions), ["A", "C"])
        self.assertEqual((sessions["A"]["agent"], sessions["A"]["state"], sessions["A"]["cwd"]), ("claude", "idle", "/p/app"))
        self.assertEqual(sessions["C"]["agent"], "codex")
        self.assertEqual(sorted(changed), ["A", "C"])

    def test_a_card_goes_when_its_agent_quits(self):
        sessions = {}
        apply(sessions, {"sid": "A", "agent": "claude", "event": "Stop", "ts": 1.0})
        discover(sessions, [found("A", "zsh")], 2.0)
        self.assertEqual(sessions, {})

    def test_a_tracked_agent_is_left_alone(self):
        sessions = {}
        apply(sessions, {"sid": "A", "agent": "claude", "event": "UserPromptSubmit", "ts": 1.0, "task": "x"})
        self.assertEqual(discover(sessions, [found("A", "claude")], 2.0), [])
        self.assertEqual(sessions["A"]["state"], "working")

    def test_codex_running_under_node_keeps_its_card(self):
        sessions = {}
        apply(sessions, {"sid": "A", "agent": "codex", "event": "UserPromptSubmit", "ts": 1.0, "task": "x"})
        discover(sessions, [found("A", "node")], 2.0)
        self.assertIn("A", sessions)

    def test_a_pane_missing_from_one_scan_keeps_its_card(self):
        sessions = {}
        discover(sessions, [found("A", "claude")], 1.0)
        discover(sessions, [], 2.0)
        self.assertIn("A", sessions)
        discover(sessions, [], 3.0)
        self.assertNotIn("A", sessions)

    def test_a_pane_that_comes_back_resets_the_count(self):
        sessions = {}
        discover(sessions, [found("A", "claude")], 1.0)
        discover(sessions, [], 2.0)
        discover(sessions, [found("A", "claude")], 3.0)
        discover(sessions, [], 4.0)
        self.assertIn("A", sessions)

    def test_a_job_name_with_a_version_still_counts(self):
        sessions = {}
        discover(sessions, [found("A", "claude-2.1.283")], 1.0)
        self.assertIn("A", sessions)


if __name__ == "__main__":
    unittest.main()
