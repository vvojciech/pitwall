"""The Pitwall daemon: holds agent state, serves the sidebar, and acts on iTerm2.

Run it with the venv that has the `iterm2` package: python -m pitwall.daemon
"""
from __future__ import annotations

import asyncio
import hmac
import json
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path

import iterm2

from pitwall import config, iterm, snapshot
from pitwall.http import reply, serve
from pitwall.state import apply

PAGE = (Path(__file__).parent / "web" / "index.html").read_bytes()
ORDER = {"waiting_permission": 0, "waiting_input": 1, "failed": 2, "working": 3, "done": 4, "idle": 5}
BUSY = ("working", "waiting_permission")


class Daemon:
    def __init__(self, app, token, port):
        self.app, self.token, self.port = app, token, port
        self.tabs = iterm.Tabs(app)
        self.sessions = self.load()
        self.unseen = set()
        self.focused = None

    def url(self, view="sidebar"):
        return f"http://127.0.0.1:{self.port}/?view={view}&t={self.token}"

    def load(self):
        try:
            return json.loads(config.STATE_FILE.read_text())
        except (OSError, ValueError):
            return {}

    def save(self):
        config.write_private(config.STATE_FILE, json.dumps(self.sessions))

    def changed(self, s):
        if s["state"] in ("done", "failed") and s["sid"] != self.focused:
            self.unseen.add(s["sid"])
        elif s["state"] not in ("done", "failed"):
            self.unseen.discard(s["sid"])
        self.save()
        asyncio.get_running_loop().create_task(self.tabs.show(s, self.unseen))

    def on_focus(self, sid):
        self.focused = sid
        if sid in self.unseen:
            self.unseen.discard(sid)
            s = self.sessions.get(sid)
            if s:
                asyncio.get_running_loop().create_task(self.tabs.show(s, self.unseen))

    async def handle(self, method, path, query, headers, body):
        if path == "/" and method == "GET":
            ok = hmac.compare_digest(query.get("t", ""), self.token)
            return reply(200, PAGE, "text/html; charset=utf-8") if ok else reply(403, {"error": "bad token"})
        if not hmac.compare_digest(headers.get("x-pitwall-token", ""), self.token):
            return reply(403, {"error": "bad token"})
        data = json.loads(body) if body else {}
        if path == "/api/event" and method == "POST":
            s = apply(self.sessions, data)
            if s:
                self.changed(s)
            else:
                self.save()
            return reply(200, {"ok": True})
        if path == "/api/state":
            return reply(200, await self.state(query.get("screen") == "1"))
        if path == "/api/mission" and method == "POST":
            subprocess.Popen(["open", self.url("mission")])
            return reply(200, {"ok": True})
        s = self.sessions.get(data.get("sid") or query.get("sid", ""))
        session = s and self.app.get_session_by_id(s["sid"])
        if not session:
            return reply(404, {"error": "That agent's tab is gone."})
        if path == "/api/focus":
            await iterm.focus(self.app, session)
            return reply(200, {"ok": True})
        if path == "/api/respond":
            if s["state"] != "waiting_permission":
                return reply(409, {"error": "The agent is not waiting for permission."})
            error = await iterm.answer(session, bool(data.get("allow")))
            if error:
                return reply(409, {"error": error})
            s.update(state="working" if data.get("allow") else "waiting_input", permission=None)
            self.changed(s)
            return reply(200, {"ok": True})
        if path.startswith("/api/undo") or path == "/api/redo":
            return await self.undo(s, path, method)
        return reply(404, {"error": "not found"})

    async def undo(self, s, path, method):
        if s["state"] in BUSY:
            return reply(409, {"error": "Wait for the agent to finish its turn."})
        if path == "/api/redo":
            if not s.get("redo"):
                return reply(409, {"error": "Nothing to redo."})
            redo = s["redo"]
            await asyncio.to_thread(snapshot.restore, redo["root"], redo["tree"])
            s["snapshots"].append(redo["snap"])
            s["redo"] = None
        else:
            if not s["snapshots"]:
                return reply(409, {"error": "No snapshot for this agent yet. Snapshots work in git repositories."})
            snap = s["snapshots"][-1]
            if method == "GET":
                files = await asyncio.to_thread(snapshot.preview, snap["root"], snap["tree"])
                return reply(200, {"task": snap.get("task"), "files": files})
            current = await asyncio.to_thread(snapshot.restore, snap["root"], snap["tree"])
            s["redo"] = dict(current, snap=s["snapshots"].pop())
        s["action"] = None
        self.save()
        return reply(200, {"ok": True})

    async def state(self, with_screen):
        cards = []
        for sid, s in list(self.sessions.items()):
            session = self.app.get_session_by_id(sid)
            if session is None:
                del self.sessions[sid]
                continue
            card = {k: v for k, v in s.items() if k != "snapshots"}
            card.update(title=session.name, focused=sid == self.focused, unseen=sid in self.unseen,
                        can_undo=bool(s["snapshots"]), can_redo=bool(s.get("redo")))
            if with_screen:
                card["screen"] = await iterm.screen_text(session, 14)
            cards.append(card)
        cards.sort(key=lambda c: (ORDER.get(c["state"], 9), -c["updated"]))
        return {"now": time.time(), "sessions": cards}


def focused_session(app, update):
    if update.active_session_changed:
        return update.active_session_changed.session_id
    tab = update.selected_tab_changed and app.get_tab_by_id(update.selected_tab_changed.tab_id)
    if tab and tab.current_session:
        return tab.current_session.session_id
    window = app.current_terminal_window
    tab = window and window.current_tab
    return tab and tab.current_session and tab.current_session.session_id


async def main(connection):
    app = await iterm2.async_get_app(connection)
    token = secrets.token_urlsafe(24)
    daemon = None
    server, port = await serve(lambda *a: daemon.handle(*a))
    daemon = Daemon(app, token, port)
    config.write_private(config.DAEMON_FILE, json.dumps({"port": port, "token": token, "pid": os.getpid()}))
    await iterm2.tool.async_register_web_view_tool(connection, "Pitwall", "com.vvojciech.pitwall", False, daemon.url())

    @iterm2.RPC
    async def pitwall_mission_control():
        subprocess.Popen(["open", daemon.url("mission")])

    await pitwall_mission_control.async_register(connection)
    for s in daemon.sessions.values():
        await daemon.tabs.show(s, daemon.unseen)
    print(f"pitwall: listening on 127.0.0.1:{port}", flush=True)
    async with iterm2.FocusMonitor(connection) as monitor:
        daemon.on_focus(focused_session(app, iterm2.FocusUpdate()))
        while True:
            update = await monitor.async_get_next_update()
            daemon.on_focus(focused_session(app, update))


def iterm_running():
    out = subprocess.run(["ps", "-axo", "comm="], capture_output=True, text=True).stdout
    return any(line.endswith("/MacOS/iTerm2") for line in out.splitlines())


if __name__ == "__main__":
    # Wait for iTerm2: asking it for an API cookie would launch it.
    while not iterm_running():
        time.sleep(5)
    try:
        iterm2.run_forever(main)
    finally:
        config.DAEMON_FILE.unlink(missing_ok=True)
    sys.exit(1)  # iTerm2 quit; launchd starts the daemon again
