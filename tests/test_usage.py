import unittest

from pitwall.usage import claude_limits

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


if __name__ == "__main__":
    unittest.main()
