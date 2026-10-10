import asyncio
import os
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path

sys.modules.setdefault("iterm2", types.ModuleType("iterm2"))  # loops.py needs no iterm2 calls
from pitwall.loops import Loops  # noqa: E402


class FakeSession:
    def __init__(self, sid):
        self.session_id, self.typed = sid, []


class FakeApp:
    def __init__(self):
        self.panes = {}

    def get_session_by_id(self, sid):
        return self.panes.get(sid)


class FakeDaemon:
    def __init__(self, app):
        self.app, self.sessions, self.saved = app, {}, 0

    def save(self):
        self.saved += 1

    def changed(self, s):
        pass


class FakeFeatures:
    def __init__(self, daemon):
        self.d, self.launched = daemon, []

    def handoff_text(self, s, mode):
        return f"review hand-off ({mode})"

    async def launch(self, near, agent, cwd, text, name):
        self.launched.append((agent, text))
        self.d.app.panes["R"] = FakeSession("R")
        return "/h/review.md", "R"

    async def paste(self, session, text):
        session.typed.append(text)


def session(sid, cwd, state="done"):
    return {"sid": sid, "agent": "claude", "cwd": cwd, "state": state, "snapshots": [], "updated": 1}


class LoopRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = os.path.realpath(self.tmp.name)
        for args in (["init", "-q"], ["config", "user.email", "t@t"], ["config", "user.name", "t"]):
            subprocess.run(["git", "-C", self.repo, *args], check=True)
        Path(self.repo, "auth.ts").write_text("v1\n")
        app = FakeApp()
        app.panes["W"] = FakeSession("W")
        self.d = FakeDaemon(app)
        self.f = FakeFeatures(self.d)
        self.loops = Loops(self.f)
        self.writer = self.d.sessions["W"] = session("W", self.repo)

    def tearDown(self):
        self.tmp.cleanup()

    def run_async(self, coro):
        return asyncio.run(coro)

    def test_a_full_round_with_manual_send(self):
        self.run_async(self.loops.start(self.writer, "codex", 2, auto=False))
        self.assertEqual(self.f.launched, [("codex", "review hand-off (review)")])
        reviewer = self.d.sessions["R"] = session("R", self.repo)

        self.run_async(self.loops.on_stop(reviewer, "auth.ts:1 is wrong. CHANGES NEEDED"))
        loop = self.writer["loop"]
        self.assertEqual((loop["phase"], loop["pending"]["to"]), ("fixing", "writer"))
        self.assertEqual(self.d.app.panes["W"].typed, [])  # manual mode waits for Send

        self.assertIsNone(self.run_async(self.loops.send(self.writer)))
        self.assertIn("auth.ts:1 is wrong", self.d.app.panes["W"].typed[0])

        Path(self.repo, "auth.ts").write_text("v2\n")  # the writer's fix
        self.run_async(self.loops.on_stop(self.writer, "Fixed."))
        self.assertEqual((loop["phase"], loop["round"], loop["pending"]["to"]), ("reviewing", 2, "reviewer"))
        self.assertIn("+v2", loop["pending"]["text"])

        self.run_async(self.loops.send(self.writer))
        self.run_async(self.loops.on_stop(reviewer, "All fixed. APPROVED"))
        self.assertEqual(loop["phase"], "approved")

    def test_auto_send_and_the_busy_guard(self):
        self.run_async(self.loops.start(self.writer, "claude", 3, auto=True))
        reviewer = self.d.sessions["R"] = session("R", self.repo)
        self.writer["state"] = "working"  # the writer started something else meanwhile
        self.run_async(self.loops.on_stop(reviewer, "CHANGES NEEDED"))
        self.assertEqual(self.d.app.panes["W"].typed, [])
        self.assertIsNotNone(self.writer["loop"]["pending"])
        self.writer["state"] = "done"
        self.run_async(self.loops.on_stop(self.writer, "Finished the other thing."))  # its turn ends
        self.assertEqual(len(self.d.app.panes["W"].typed), 1)
        self.assertIsNone(self.writer["loop"]["pending"])
        self.assertEqual(self.writer["loop"]["phase"], "fixing")


if __name__ == "__main__":
    unittest.main()
