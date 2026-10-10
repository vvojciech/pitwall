import unittest

from pitwall.events import to_event
from pitwall.state import apply

ENV = {"ITERM_SESSION_ID": "w0t1p0:ABC-123"}


def ev(name, payload=None, agent="claude", ts=100.0):
    return to_event(agent, name, payload or {}, ENV, ts)


class EventTests(unittest.TestCase):
    def test_outside_iterm_gives_no_event(self):
        self.assertIsNone(to_event("claude", "Stop", {}, {}, 1.0))

    def test_session_id_is_the_iterm_uuid(self):
        self.assertEqual(ev("Stop")["sid"], "ABC-123")

    def test_prompt_keeps_the_first_line_only(self):
        e = ev("UserPromptSubmit", {"prompt": "  fix the build\nmore detail"})
        self.assertEqual(e["task"], "fix the build")

    def test_a_system_notification_is_not_a_task(self):
        self.assertIsNone(ev("UserPromptSubmit", {"prompt": "<task-notification>\n<task-id>x</task-id>"})["task"])

    def test_tool_action_names_the_file(self):
        e = ev("PreToolUse", {"tool_name": "Edit", "tool_input": {"file_path": "/a/b/app.ts"}})
        self.assertEqual(e["action"], "Edit app.ts")

    def test_tool_action_names_the_command(self):
        e = ev("PreToolUse", {"tool_name": "Bash", "tool_input": {"command": "npm test\n--x"}})
        self.assertEqual(e["action"], "Bash npm test")


class StateTests(unittest.TestCase):
    def run_events(self, *events):
        sessions = {}
        for e in events:
            apply(sessions, e)
        return sessions

    def test_prompt_starts_work(self):
        s = self.run_events(ev("UserPromptSubmit", {"prompt": "add login"}, ts=5))["ABC-123"]
        self.assertEqual((s["state"], s["task"], s["started"]), ("working", "add login", 5))

    def test_permission_request_waits_then_tool_resumes(self):
        s = self.run_events(
            ev("UserPromptSubmit", {"prompt": "x"}),
            ev("PermissionRequest", {"tool_name": "Bash", "tool_input": {"command": "rm -rf build"}}),
        )["ABC-123"]
        self.assertEqual(s["state"], "waiting_permission")
        self.assertEqual(s["permission"], "Bash rm -rf build")
        apply({"ABC-123": s}, ev("PostToolUse", {"tool_name": "Bash"}))
        self.assertEqual(s["state"], "working")
        self.assertIsNone(s["permission"])

    def test_permission_notification_also_waits(self):
        s = self.run_events(ev("Notification", {"notification_type": "permission_prompt"}))["ABC-123"]
        self.assertEqual(s["state"], "waiting_permission")

    def test_idle_notification_keeps_done(self):
        s = self.run_events(
            ev("Stop"), ev("Notification", {"notification_type": "idle_prompt"})
        )["ABC-123"]
        self.assertEqual(s["state"], "done")

    def test_idle_notification_mid_turn_waits_for_input(self):
        s = self.run_events(
            ev("UserPromptSubmit", {"prompt": "x"}),
            ev("Notification", {"message": "Claude is waiting for your input"}),
        )["ABC-123"]
        self.assertEqual(s["state"], "waiting_input")

    def test_stop_failure_fails(self):
        s = self.run_events(ev("StopFailure", {"error": "rate limit"}))["ABC-123"]
        self.assertEqual((s["state"], s["error"]), ("failed", "rate limit"))

    def test_session_end_removes_the_card(self):
        self.assertEqual(self.run_events(ev("SessionStart"), ev("SessionEnd")), {})

    def test_snapshots_stack_per_turn(self):
        snap = {"root": "/r", "tree": "t1"}
        s = self.run_events(
            ev("UserPromptSubmit", {"prompt": "one"}) | {"snapshot": snap},
            ev("UserPromptSubmit", {"prompt": "two"}) | {"snapshot": {"root": "/r", "tree": "t2"}},
        )["ABC-123"]
        self.assertEqual([x["tree"] for x in s["snapshots"]], ["t1", "t2"])
        self.assertEqual(s["snapshots"][0]["task"], "one")

    def test_a_new_agent_in_the_pane_replaces_the_card(self):
        sessions = self.run_events(ev("UserPromptSubmit", {"prompt": "x"}))
        apply(sessions, ev("SessionStart", agent="codex"))
        self.assertEqual((sessions["ABC-123"]["agent"], sessions["ABC-123"]["state"]), ("codex", "idle"))


if __name__ == "__main__":
    unittest.main()
