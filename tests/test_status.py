import unittest

from pitwall.status import native_status


def s(state, **kw):
    return dict({"state": state, "task": "Fix the login redirect", "action": None, "permission": None, "error": None}, **kw)


class NativeStatusTests(unittest.TestCase):
    def test_working_shows_the_last_action(self):
        self.assertEqual(native_status(s("working", action="Edit auth.ts")), ("working", "#5f87ff", "Edit auth.ts"))

    def test_working_without_an_action_shows_the_task(self):
        self.assertEqual(native_status(s("working"))[2], "Fix the login redirect")

    def test_permission_names_the_command(self):
        self.assertEqual(native_status(s("waiting_permission", permission="Bash npm run build")),
                         ("waiting", "#ff9500", "Allow? Bash npm run build"))

    def test_done_and_failed_are_idle_with_their_own_dot(self):
        self.assertEqual(native_status(s("done")), ("idle", "#00d75f", "Done: Fix the login redirect"))
        self.assertEqual(native_status(s("failed", error="API Error: 529")), ("idle", "#ff5f5f", "Failed: API Error: 529"))

    def test_detail_is_short(self):
        self.assertLessEqual(len(native_status(s("working", action="x" * 300))[2]), 60)


if __name__ == "__main__":
    unittest.main()
