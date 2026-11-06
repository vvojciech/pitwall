import unittest

from pitwall.state import apply, pane_owners, rebound

PANES = [{"sid": "NEW1", "job_pid": 300}, {"sid": "NEW2", "job_pid": 500}, {"sid": "SHELL", "job_pid": None}]
LIVE = {"NEW1", "NEW2"}
OWNERS = pane_owners(PANES)


class ReboundTests(unittest.TestCase):
    def test_an_event_from_an_id_iterm_dropped_goes_to_the_tab_running_its_agent(self):
        event = {"sid": "OLD", "agent_pid": 300, "event": "Stop"}
        self.assertEqual(rebound(event, OWNERS, LIVE)["sid"], "NEW1")

    def test_an_event_from_a_live_tab_keeps_its_id(self):
        event = {"sid": "NEW2", "agent_pid": 300, "event": "Stop"}
        self.assertEqual(rebound(event, OWNERS, LIVE)["sid"], "NEW2")

    def test_an_event_that_matches_nothing_is_left_alone(self):
        self.assertEqual(rebound({"sid": "OLD", "event": "Stop"}, OWNERS, LIVE)["sid"], "OLD")
        self.assertEqual(rebound({"sid": "OLD", "agent_pid": 1, "event": "Stop"}, OWNERS, LIVE)["sid"], "OLD")

    def test_nothing_is_rebound_before_the_first_scan(self):
        event = {"sid": "OLD", "agent_pid": 300, "event": "Stop"}
        self.assertEqual(rebound(event, {}, set())["sid"], "OLD")

    def test_a_rebound_event_updates_the_card_of_the_live_tab(self):
        sessions = {}
        apply(sessions, {"sid": "NEW1", "agent": "claude", "event": "SessionStart", "ts": 1, "cwd": "/repo"})
        event = rebound({"sid": "OLD", "agent_pid": 300, "agent": "claude", "event": "UserPromptSubmit", "ts": 2, "cwd": "/repo", "task": "fix it"}, OWNERS, LIVE)
        apply(sessions, event)
        self.assertEqual((set(sessions), sessions["NEW1"]["state"], sessions["NEW1"]["task"]), ({"NEW1"}, "working", "fix it"))
