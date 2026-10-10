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

    def test_pasted_text_is_unwrapped(self):
        # The closing tag repeats the id, as Claude Code writes it.
        raw = '\n\n<pasted_content id="0435">\nThis command failed in /repo (exit 1):\n$ ls\n</pasted_content id="0435">\n'
        self.assertEqual(ev("UserPromptSubmit", {"prompt": raw})["task"], "This command failed in /repo (exit 1):")

    def test_typed_text_around_a_paste_comes_first(self):
        raw = 'Fix this\n<pasted_content id="1">\nTraceback\n</pasted_content>'
        self.assertEqual(ev("UserPromptSubmit", {"prompt": raw})["task"], "Fix this")

    def test_prompt_text_helper(self):
        from pitwall.events import prompt_text
        self.assertIsNone(prompt_text("<local-command-stdout>x</local-command-stdout>"))
        self.assertEqual(prompt_text("<b>bold</b> is html"), "<b>bold</b> is html")

    def test_a_system_notification_is_not_a_task(self):
        self.assertIsNone(ev("UserPromptSubmit", {"prompt": "<task-notification>\n<task-id>x</task-id>"})["task"])

    def test_stop_carries_background_work(self):
        tasks = [{"id": "b1", "type": "shell", "status": "running", "description": "Dev server",
                  "command": "npm run dev " + "x" * 300},
                 {"id": "b2", "type": "subagent", "status": "pending", "description": "Search callers"}]
        e = ev("Stop", {"background_tasks": tasks, "session_crons": [{"id": "c1"}]})
        self.assertEqual([t["type"] for t in e["background"]], ["shell", "subagent"])
        self.assertLessEqual(len(e["background"][0]["command"]), 120)
        self.assertEqual(e["crons"], 1)
        self.assertNotIn("background", ev("Stop", {}))

    def test_tool_events_carry_the_full_path_and_kind(self):
        e = ev("PostToolUse", {"tool_name": "Edit", "tool_input": {"file_path": "/a/src/app.ts"}})
        self.assertEqual((e["path"], e["touch"]), ("/a/src/app.ts", "edit"))
        e = ev("PreToolUse", {"tool_name": "Read", "tool_input": {"file_path": "/a/README.md"}})
        self.assertEqual(e["touch"], "read")
        self.assertNotIn("path", ev("PreToolUse", {"tool_name": "Bash", "tool_input": {"command": "ls"}}))

    def test_codex_patches_name_their_files(self):
        e = ev("PreToolUse", {"tool_name": "apply_patch", "cwd": "/w",
                              "tool_input": {"input": "*** Update File: src/a.ts\n*** Add File: src/b.ts\n"}}, agent="codex")
        self.assertEqual((e["paths"], e["touch"]), (["/w/src/a.ts", "/w/src/b.ts"], "edit"))

    def test_tool_action_names_the_file(self):
        e = ev("PreToolUse", {"tool_name": "Edit", "tool_input": {"file_path": "/a/b/app.ts"}})
        self.assertEqual(e["action"], "Edit app.ts")

    def test_tool_action_names_the_command(self):
        e = ev("PreToolUse", {"tool_name": "Bash", "tool_input": {"command": "npm test\n--x"}})
        self.assertEqual(e["action"], "Bash npm test")


class LayoutOrderTests(unittest.TestCase):
    def test_cards_follow_windows_tabs_and_panes(self):
        from pitwall.state import layout_order
        cards = [{"sid": s} for s in ("C", "A", "D", "B")]
        windows = [[["A", "B"], ["C"]], [["D"]]]  # window > tab > panes
        self.assertEqual([c["sid"] for c in layout_order(cards, windows)], ["A", "B", "C", "D"])

    def test_unknown_panes_go_last(self):
        from pitwall.state import layout_order
        self.assertEqual([c["sid"] for c in layout_order([{"sid": "X"}, {"sid": "A"}], [[["A"]]])], ["A", "X"])


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

    def test_touched_files_reset_each_turn_and_edit_wins_over_read(self):
        read = {"tool_name": "Read", "tool_input": {"file_path": "/a/x.ts"}}
        edit = {"tool_name": "Edit", "tool_input": {"file_path": "/a/x.ts"}}
        s = self.run_events(ev("UserPromptSubmit", {"prompt": "one"}), ev("PreToolUse", read),
                            ev("PostToolUse", edit), ev("PreToolUse", read))["ABC-123"]
        self.assertEqual((s["touched"], s["current"]), ({"/a/x.ts": "edit"}, "/a/x.ts"))
        apply({"ABC-123": s}, ev("UserPromptSubmit", {"prompt": "two"}))
        self.assertEqual((s["touched"], s["current"]), ({}, None))

    def test_a_new_agent_in_the_pane_replaces_the_card(self):
        sessions = self.run_events(ev("UserPromptSubmit", {"prompt": "x"}))
        apply(sessions, ev("SessionStart", agent="codex"))
        self.assertEqual((sessions["ABC-123"]["agent"], sessions["ABC-123"]["state"]), ("codex", "idle"))

    def test_background_work_is_kept_until_the_next_report(self):
        work = [{"id": "b1", "type": "shell", "status": "running", "description": "Dev server"}]
        sessions = self.run_events(ev("Stop", {"background_tasks": work}))
        s = sessions["ABC-123"]
        apply(sessions, ev("UserPromptSubmit", {"prompt": "next"}))
        self.assertEqual(len(s["background"]), 1)  # a new prompt does not end background work
        apply(sessions, ev("Stop", {"background_tasks": []}))
        self.assertEqual(s["background"], [])

    def test_a_name_stays_with_the_pane(self):
        sessions = self.run_events(ev("SessionStart"))
        sessions["ABC-123"]["name"] = "Checkout"
        apply(sessions, ev("SessionStart", agent="codex"))
        self.assertEqual(sessions["ABC-123"]["name"], "Checkout")


if __name__ == "__main__":
    unittest.main()
