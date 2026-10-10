import unittest

from pitwall.events import to_event
from pitwall.questions import keys, menu_ready, parse, problem
from pitwall.state import apply

ENV = {"ITERM_SESSION_ID": "w0t1p0:ABC-123"}
ASK = {"questions": [
    {"question": "Which colour?", "header": "Colour", "multiSelect": False,
     "options": [{"label": "Red", "description": "Warm"}, {"label": "Blue", "description": "Cool"}]},
    {"question": "Which sizes?", "header": "Sizes", "multiSelect": True,
     "options": [{"label": "S"}, {"label": "M"}, {"label": "L"}]},
]}
COLOUR = parse({"questions": ASK["questions"][:1]})
SIZES = parse({"questions": ASK["questions"][1:]})
BOTH = parse(ASK)


def ev(name, payload, ts=100.0):
    return to_event("claude", name, payload, ENV, ts)


class ParseTests(unittest.TestCase):
    def test_keeps_what_the_card_shows(self):
        self.assertEqual(BOTH[0], {"question": "Which colour?", "header": "Colour", "multi": False,
                                   "options": [{"label": "Red", "description": "Warm"},
                                               {"label": "Blue", "description": "Cool"}]})
        self.assertTrue(BOTH[1]["multi"])

    def test_bad_input_gives_nothing(self):
        for bad in (None, "x", {}, {"questions": "x"}, {"questions": [{"question": "No options"}]}):
            self.assertIsNone(parse(bad))

    def test_more_than_nine_options_cannot_be_typed(self):
        many = {"questions": [{"question": "q", "options": [{"label": str(i)} for i in range(10)]}]}
        self.assertIsNone(parse(many))


class KeyTests(unittest.TestCase):
    def test_one_single_question_is_one_digit(self):
        self.assertEqual(keys(COLOUR, [[1]]), ["2"])

    def test_multi_select_toggles_then_moves_on(self):
        self.assertEqual(keys(SIZES, [[0, 2]]), ["1", "3", "\t"])

    def test_several_questions(self):
        self.assertEqual(keys(BOTH, [[0], [1]]), ["1", "2", "\t"])


class ProblemTests(unittest.TestCase):
    def test_good_picks(self):
        self.assertIsNone(problem(BOTH, [[1], [0, 2]]))

    def test_bad_picks(self):
        for picks in ([[0]], [[0, 1], [0]], [[], [0]], [[0], []], [[5], [0]], [[0], [0, 0]], [["0"], [0]],
                      [[True], [0]], "x", None):
            self.assertIsNotNone(problem(BOTH, picks), picks)


SCREEN = """\
←  ☐ Colour  ☐ Sizes  ✔ Submit  →

Which colour?

❯ 1. Red
     Warm
  2. Blue
"""


class MenuTests(unittest.TestCase):
    def test_fresh_menu(self):
        self.assertTrue(menu_ready(SCREEN, BOTH))

    def test_part_answered_or_moved_menu(self):
        self.assertFalse(menu_ready(SCREEN.replace("☐ Colour", "☒ Colour"), BOTH))
        self.assertFalse(menu_ready(SCREEN.replace("❯ 1. Red", "  1. Red").replace("  2. Blue", "❯ 2. Blue"), BOTH))
        self.assertFalse(menu_ready(SCREEN.replace("Which colour?", "Which sizes?"), BOTH))


class StateTests(unittest.TestCase):
    def setUp(self):
        self.sessions = {}
        apply(self.sessions, ev("UserPromptSubmit", {"prompt": "go"}))

    def test_a_question_is_not_a_permission(self):
        apply(self.sessions, ev("PreToolUse", {"tool_name": "AskUserQuestion", "tool_input": ASK}))
        s = apply(self.sessions, ev("PermissionRequest", {"tool_name": "AskUserQuestion", "tool_input": ASK}))
        self.assertEqual(s["state"], "waiting_input")
        self.assertEqual(len(s["questions"]), 2)
        self.assertIsNone(s["permission"])
        s = apply(self.sessions, ev("Notification", {"notification_type": "permission_prompt", "message": "permission"}))
        self.assertEqual(s["state"], "waiting_input")

    def test_the_answer_clears_the_questions(self):
        apply(self.sessions, ev("PermissionRequest", {"tool_name": "AskUserQuestion", "tool_input": ASK}))
        s = apply(self.sessions, ev("PostToolUse", {"tool_name": "AskUserQuestion", "tool_input": ASK}))
        self.assertIsNone(s.get("questions"))
        self.assertEqual(s["state"], "working")

    def test_a_stop_clears_the_questions(self):
        apply(self.sessions, ev("PermissionRequest", {"tool_name": "AskUserQuestion", "tool_input": ASK}))
        self.assertIsNone(apply(self.sessions, ev("Stop", {}))["questions"])


if __name__ == "__main__":
    unittest.main()
