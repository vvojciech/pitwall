import asyncio
import json
import sys
import types
import unittest
from unittest import mock

_iterm2 = sys.modules.setdefault("iterm2", types.ModuleType("iterm2"))  # the scan and the event route need no iterm2 calls
for _name in ("Color", "LocalWriteOnlyProfile"):
    if not hasattr(_iterm2, _name):
        setattr(_iterm2, _name, lambda *args, **kwargs: args)
from pitwall.daemon import Daemon  # noqa: E402


class FakeSession:
    def __init__(self, sid, job_pid):
        self.session_id, self.vars = sid, {"jobName": "claude", "path": "/repo", "jobPid": job_pid}

    async def async_get_variable(self, name):
        return self.vars.get(name)


class FakeApp:
    def __init__(self, sessions):
        tab = types.SimpleNamespace(sessions=sessions)
        self.terminal_windows = [types.SimpleNamespace(tabs=[tab])]


class FakeTabs:
    async def show(self, s, unseen):
        pass


class DaemonReboundTests(unittest.TestCase):
    def daemon(self):
        d = object.__new__(Daemon)
        d.app = FakeApp([FakeSession("NEW1", 300), FakeSession("NEW2", 500)])
        d.token, d.sessions, d.unseen, d.focused = "t", {}, set(), None
        d.live, d.owners = set(), {}
        d.tabs, d.status = FakeTabs(), mock.Mock()
        return d

    def test_an_event_with_an_id_iterm_dropped_updates_the_card_of_the_tab_running_its_agent(self):
        async def run():
            d = self.daemon()
            with mock.patch("pitwall.daemon.config.write_private"):
                await d.scan()
                event = {"sid": "OLD", "agent_pid": 300, "agent": "claude", "event": "UserPromptSubmit", "ts": 2, "cwd": "/repo", "task": "fix it"}
                body = json.dumps(event).encode()
                await d.handle("POST", "/api/event", {}, {"x-pitwall-token": "t"}, body)
            return d.sessions
        sessions = asyncio.run(run())
        self.assertEqual((sorted(sessions), sessions["NEW1"]["state"], sessions["NEW1"]["task"]), (["NEW1", "NEW2"], "working", "fix it"))


if __name__ == "__main__":
    unittest.main()
