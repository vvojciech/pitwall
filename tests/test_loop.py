import unittest

from pitwall.loop import new_loop, on_stop, verdict


class VerdictTests(unittest.TestCase):
    def test_the_last_verdict_wins(self):
        self.assertEqual(verdict("Earlier I said CHANGES NEEDED, but now: APPROVED"), "approved")
        self.assertEqual(verdict("**APPROVED** if not for this. CHANGES NEEDED"), "changes")

    def test_no_verdict_counts_as_changes(self):
        self.assertEqual(verdict("Looks mostly fine."), "changes")

    def test_a_negated_approval_is_not_one(self):
        self.assertEqual(verdict("NOT APPROVED. Fix the test."), "changes")


class LoopTests(unittest.TestCase):
    def setUp(self):
        self.loop = new_loop("R", "codex", max_rounds=2, auto=False)

    def test_changes_go_to_the_writer(self):
        to, text = on_stop(self.loop, "reviewer", "1. auth.ts:12 misses a null check. CHANGES NEEDED", lambda: "")
        self.assertEqual(to, "writer")
        self.assertIn("auth.ts:12", text)
        self.assertIn("round 1 of 2", text)
        self.assertEqual(self.loop["phase"], "fixing")

    def test_the_writers_fix_goes_back_to_the_reviewer_with_the_diff(self):
        on_stop(self.loop, "reviewer", "CHANGES NEEDED", lambda: "")
        to, text = on_stop(self.loop, "writer", "Fixed.", lambda: "diff --git a/auth.ts")
        self.assertEqual((to, self.loop["round"], self.loop["phase"]), ("reviewer", 2, "reviewing"))
        self.assertIn("diff --git a/auth.ts", text)
        self.assertIn("APPROVED or CHANGES NEEDED", text)

    def test_approval_ends_the_loop(self):
        self.assertEqual(on_stop(self.loop, "reviewer", "All good. APPROVED", lambda: ""), (None, None))
        self.assertEqual(self.loop["phase"], "approved")

    def test_the_round_limit_ends_the_loop(self):
        on_stop(self.loop, "reviewer", "CHANGES NEEDED", lambda: "")
        on_stop(self.loop, "writer", "Fixed.", lambda: "d")
        on_stop(self.loop, "reviewer", "CHANGES NEEDED", lambda: "")
        self.assertEqual(on_stop(self.loop, "writer", "Fixed again.", lambda: "d"), (None, None))
        self.assertEqual(self.loop["phase"], "limit")

    def test_a_stop_out_of_turn_is_ignored(self):
        self.assertEqual(on_stop(self.loop, "writer", "chatting", lambda: ""), (None, None))
        self.assertEqual(self.loop["phase"], "reviewing")


if __name__ == "__main__":
    unittest.main()
