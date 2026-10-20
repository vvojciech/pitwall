import unittest

from pitwall.usage import claude_limits, windows_left

NOW = 1_791_760_000


def snap(five=None, week=None):
    w = lambda p: p and {"used_percentage": p[0], "resets_at": p[1]}
    return {"five_hour": w(five), "seven_day": w(week)}


class ClaudeLimitsTests(unittest.TestCase):
    def test_idle_session_with_old_limits_does_not_win(self):
        # An idle session re-renders its status line with the limits of its last reply.
        fresh = snap(five=(3, NOW + 3600), week=(84, NOW + 86400))
        stale = snap(five=None, week=(69, NOW + 86400))
        out = claude_limits([fresh, stale], NOW)
        self.assertEqual(out["five_hour"]["used"], 3)
        self.assertEqual(out["week"], {"used": 84, "resets_at": NOW + 86400, "window": 604800})

    def test_a_newer_window_beats_a_higher_use_in_an_older_one(self):
        out = claude_limits([snap(five=(33, NOW - 60)), snap(five=(2, NOW + 600))], NOW)
        self.assertEqual(out["five_hour"]["used"], 2)

    def test_an_expired_window_shows_nothing(self):
        out = claude_limits([snap(five=(33, NOW - 60), week=(10, NOW + 60))], NOW)
        self.assertIsNone(out["five_hour"])
        self.assertEqual(out["week"]["used"], 10)

    def test_no_limits_gives_none(self):
        self.assertIsNone(claude_limits([{}, None], NOW))


class WindowsLeftTests(unittest.TestCase):
    def test_counts_the_five_hour_windows_until_the_week_resets(self):
        # The current window, then five more in the 25 hours after it ends.
        limits = {"five_hour": {"resets_at": NOW + 3600}, "week": {"resets_at": NOW + 3600 + 25 * 3600}}
        self.assertEqual(windows_left(limits), 6)

    def test_a_missing_window_gives_none(self):
        self.assertIsNone(windows_left({"five_hour": None, "week": {"resets_at": NOW}}))
        self.assertIsNone(windows_left(None))


if __name__ == "__main__":
    unittest.main()
