import unittest

from pitwall import settings
from pitwall.colours import BADGES, TAB, is_our_badge, is_our_colour, want_for


class ColourTests(unittest.TestCase):
    def test_every_signal_colour_is_dark(self):
        for name, rgb in TAB.items():
            luminance = 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
            self.assertLess(luminance, 60, name)

    def test_our_colours_old_and_new_are_recognised(self):
        self.assertTrue(is_our_colour((86, 182, 120)))  # the bright green of 0.1 to 0.2
        self.assertTrue(is_our_colour((232, 163, 61)))
        self.assertTrue(is_our_colour(TAB["done"]))
        self.assertTrue(is_our_colour((87.6, 181.2, 120.4)))  # iTerm2 rounds colours

    def test_a_users_own_colour_is_kept(self):
        self.assertFalse(is_our_colour((40, 90, 200)))

    def test_our_badges(self):
        self.assertTrue(is_our_badge(BADGES["waiting_permission"]))
        self.assertFalse(is_our_badge(r"\(session.name)"))


ALL_ON = settings.DEFAULTS


class WantTests(unittest.TestCase):
    def test_a_waiting_agent_gets_the_colour_and_the_badge(self):
        self.assertEqual(want_for({"sid": "a", "state": "waiting_permission"}, set(), ALL_ON), ("waiting", "Needs you"))

    def test_a_finished_agent_is_coloured_only_until_seen(self):
        done = {"sid": "a", "state": "done"}
        self.assertEqual(want_for(done, {"a"}, ALL_ON), ("done", None))
        self.assertEqual(want_for(done, set(), ALL_ON), (None, None))

    def test_a_working_agent_keeps_the_profile(self):
        self.assertEqual(want_for({"sid": "a", "state": "working"}, {"a"}, ALL_ON), (None, None))

    def test_colours_off_keeps_the_badge(self):
        prefs = dict(ALL_ON, tab_colours=False)
        self.assertEqual(want_for({"sid": "a", "state": "waiting_input"}, set(), prefs), (None, "Waiting"))

    def test_badges_off_keeps_the_colour(self):
        prefs = dict(ALL_ON, tab_badges=False)
        self.assertEqual(want_for({"sid": "a", "state": "waiting_input"}, set(), prefs), ("waiting", None))

    def test_both_off_puts_the_profile_back(self):
        prefs = dict(ALL_ON, tab_colours=False, tab_badges=False)
        self.assertEqual(want_for({"sid": "a", "state": "failed"}, {"a"}, prefs), (None, None))


if __name__ == "__main__":
    unittest.main()
