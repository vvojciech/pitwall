import asyncio
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

# The daemon needs only iterm2.Color at import time. Other tests may have put a bare stub in already.
stub = sys.modules.setdefault("iterm2", types.ModuleType("iterm2"))
if not hasattr(stub, "Color"):
    stub.Color = lambda *rgb: rgb
from pitwall import daemon as daemon_mod, settings  # noqa: E402


class FakeTabs:
    def __init__(self):
        self.shown = []

    async def show(self, s, unseen):
        self.shown.append(s["sid"])


def make_daemon():
    d = daemon_mod.Daemon.__new__(daemon_mod.Daemon)
    d.token, d.sessions, d.unseen, d.update = "tok", {"a": {"sid": "a", "state": "done"}}, set(), {"behind": 2}
    d.tabs = FakeTabs()
    d.features = types.SimpleNamespace(failures=[{"id": 1}])
    d.check_updates = mock.AsyncMock()
    return d


class SettingsRouteTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        patcher = mock.patch.object(settings, "FILE", Path(self.dir.name) / "settings.json")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.dir.cleanup)

    def call(self, d, method, body=None, token="tok"):
        raw = json.dumps(body).encode() if body is not None else b""
        status, _, out = asyncio.run(d.handle(method, "/api/settings", {}, {"x-pitwall-token": token}, raw))
        return status, json.loads(out)

    def test_get_lists_the_features(self):
        status, data = self.call(make_daemon(), "GET")
        self.assertEqual(status, 200)
        self.assertEqual(len(data["features"]), len(settings.FEATURES))

    def test_a_request_without_the_token_is_refused(self):
        status, _ = self.call(make_daemon(), "POST", {"ports": False}, token="nope")
        self.assertEqual(status, 403)
        self.assertTrue(settings.current()["ports"])

    def test_post_saves_and_reapplies_the_tabs(self):
        d = make_daemon()
        status, data = self.call(d, "POST", {"tab_colours": False})
        self.assertEqual(status, 200)
        self.assertFalse(next(f for f in data["features"] if f["key"] == "tab_colours")["on"])
        self.assertFalse(settings.current()["tab_colours"])
        self.assertEqual(d.tabs.shown, ["a"])

    def test_failed_commands_off_drops_the_list(self):
        d = make_daemon()
        self.call(d, "POST", {"failed_commands": False})
        self.assertEqual(d.features.failures, [])

    def test_update_check_off_hides_the_update_and_on_checks_again(self):
        d = make_daemon()
        self.call(d, "POST", {"update_check": False})
        self.assertIsNone(d.update)

        async def turn_on():
            await d.apply_settings({"update_check": True})
            await asyncio.sleep(0)
        asyncio.run(turn_on())
        d.check_updates.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
