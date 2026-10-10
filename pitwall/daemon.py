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
from pitwall.features import Features
from pitwall.http import reply, serve
from pitwall.state import apply, discover, layout_order
from pitwall.status import NativeStatus

WEB = Path(__file__).parent / "web"
STATIC = {"/app.css": "text/css; charset=utf-8", "/app.js": "text/javascript; charset=utf-8",
          "/features.js": "text/javascript; charset=utf-8", "/races.js": "text/javascript; charset=utf-8",
          "/usage.js": "text/javascript; charset=utf-8", "/activity.js": "text/javascript; charset=utf-8",
          "/map.js": "text/javascript; charset=utf-8", "/cards.js": "text/javascript; charset=utf-8"}
PAGES = {"/": "index.html", "/activity": "activity.html"}
BUSY = ("working", "waiting_permission")
SCAN_SECONDS = 5


class Daemon:
    def __init__(self, app, token, port):
        self.app, self.token, self.port = app, token, port
        self.tabs = iterm.Tabs(app)
        self.status = NativeStatus()
        self.sessions = self.load()
        self.unseen = set()
        self.focused = None

    def url(self, page=""):
        return f"http://127.0.0.1:{self.port}/{page}?t={self.token}"

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
        self.status.write(s)

    def on_focus(self, sid):
        self.focused = sid
        if sid in self.unseen:
            self.unseen.discard(sid)
            s = self.sessions.get(sid)
            if s:
                asyncio.get_running_loop().create_task(self.tabs.show(s, self.unseen))

    async def handle(self, method, path, query, headers, body):
        if method == "GET" and path in STATIC:
            return reply(200, (WEB / path[1:]).read_bytes(), STATIC[path])
        if path in PAGES and method == "GET":
            if not hmac.compare_digest(query.get("t", ""), self.token):
                return reply(403, {"error": "bad token"})
            return reply(200, (WEB / PAGES[path]).read_bytes(), "text/html; charset=utf-8")
        if not hmac.compare_digest(headers.get("x-pitwall-token", ""), self.token):
            return reply(403, {"error": "bad token"})
        data = json.loads(body) if body else {}
        if path == "/api/event" and method == "POST":
            s = apply(self.sessions, data)
            if s:
                self.changed(s)
            else:
                self.save()
            if s and data["event"] == "Stop":
                asyncio.get_running_loop().create_task(self.features.loops.on_stop(s, data.get("last_message")))
            return reply(200, {"ok": True})
        routed = await self.features.route(method, path, query, data)
        if routed:
            return routed
        if path == "/api/state":
            return reply(200, await self.state())
        if path == "/api/open" and method == "POST":  # the activity page, in the default browser
            subprocess.Popen(["open", self.url("activity")])
            return reply(200, {"ok": True})
        s = self.sessions.get(data.get("sid") or query.get("sid", ""))
        session = s and self.app.get_session_by_id(s["sid"])
        if not session:
            return reply(404, {"error": "That agent's tab is gone."})
        if path == "/api/rename":
            await self.rename(s, session, data.get("name"))
            return reply(200, {"ok": True})
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

    async def state(self):
        cards = []
        for sid, s in list(self.sessions.items()):
            session = self.app.get_session_by_id(sid)
            if session is None:  # the scan removes cards; layout data can lag for a moment
                continue
            card = {k: v for k, v in s.items() if k != "snapshots"}
            writer = self.features.loops.writer_of(sid)
            tab = session.tab
            card.update(title=session.name, focused=sid == self.focused, unseen=sid in self.unseen,
                        can_undo=bool(s["snapshots"]), can_redo=bool(s.get("redo")),
                        reviews=writer and os.path.basename(writer.get("cwd") or ""),
                        tab_name=tab and await tab.async_get_variable("titleOverride") or None)
            cards.append(card)
        layout = [[[p.session_id for p in t.sessions] for t in w.tabs] for w in self.app.terminal_windows]
        return {"now": time.time(), "sessions": layout_order(cards, layout), "failures": self.features.failure_cards()}

    async def rename(self, s, session, name):
        """Name an agent's card and its iTerm2 tab. An empty name goes back to the defaults."""
        name = " ".join((name or "").split())[:60]
        s["name"] = name or None
        if session.tab:
            await session.tab.async_set_title(name)  # "" lets iTerm2 title the tab again
        self.save()

    async def scan(self):
        """Add agents that fired no hook yet, and remove agents that quit without a SessionEnd."""
        panes = []
        for window in self.app.terminal_windows:
            for tab in window.tabs:
                for session in tab.sessions:
                    panes.append({"sid": session.session_id,
                                  "job": await session.async_get_variable("jobName"),
                                  "cwd": await session.async_get_variable("path")})
        before = set(self.sessions)
        added = discover(self.sessions, panes, time.time())
        for sid in before - set(self.sessions):
            self.unseen.discard(sid)
            await self.tabs.show({"sid": sid, "state": "idle"}, self.unseen)
        for sid in added:
            self.changed(self.sessions[sid])
        if added or before != set(self.sessions):
            self.save()

    async def scan_forever(self):
        while True:
            try:
                await self.scan()
            except Exception as e:  # noqa: BLE001  a failed scan must not stop the daemon
                print(f"pitwall: scan failed: {e}", flush=True)
            await asyncio.sleep(SCAN_SECONDS)


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
    daemon.features = Features(daemon, connection)
    await daemon.features.watch_commands()
    config.write_private(config.DAEMON_FILE, json.dumps({"port": port, "token": token, "pid": os.getpid()}))
    if os.environ.get("PITWALL_NO_TOOLBELT") != "1":  # a test daemon must not take over the panel
        await iterm2.tool.async_register_web_view_tool(connection, "Pitwall", "com.vvojciech.pitwall", False, daemon.url())
    for s in daemon.sessions.values():
        await daemon.tabs.show(s, daemon.unseen)
        daemon.status.write(s)
    asyncio.get_running_loop().create_task(daemon.scan_forever())
    print(f"pitwall: listening on 127.0.0.1:{port}", flush=True)
    async with iterm2.FocusMonitor(connection) as monitor:
        daemon.on_focus(focused_session(app, iterm2.FocusUpdate()))
        while True:
            update = await monitor.async_get_next_update()
            daemon.on_focus(focused_session(app, update))


def iterm_running():
    out = subprocess.run(["ps", "-axo", "comm="], capture_output=True, text=True).stdout
    return any(line.endswith("/MacOS/iTerm2") for line in out.splitlines())


def trim_log(path, limit=1_000_000, keep=200_000):
    """Keep the log small: launchd appends to it forever."""
    try:
        if path.stat().st_size > limit:
            tail = path.read_bytes()[-keep:]
            path.write_bytes(tail[tail.find(b"\n") + 1:])
    except OSError:
        pass


if __name__ == "__main__":
    trim_log(config.LOG_FILE)
    # Wait for iTerm2: asking it for an API cookie would launch it.
    while not iterm_running():
        time.sleep(5)
    try:
        iterm2.run_forever(main)
    finally:
        config.DAEMON_FILE.unlink(missing_ok=True)
    sys.exit(1)  # iTerm2 quit; launchd starts the daemon again
