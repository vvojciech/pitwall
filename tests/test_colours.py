import unittest

from pitwall.colours import BADGES, TAB, is_our_badge, is_our_colour


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


if __name__ == "__main__":
    unittest.main()
