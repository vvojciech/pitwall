"""Timeline, hand-off, failed commands, ports and dev server tabs: the daemon's extra routes."""
from __future__ import annotations

import asyncio
import os
import shlex
import signal
import subprocess
import time
from collections import deque
from pathlib import Path

import iterm2

from pitwall import config, handoff, ports, snapshot, timeline
from pitwall.http import reply

HANDOFFS = config.HOME / "handoffs"
LOGS = config.HOME / "logs"
IGNORED_EXITS = (0, 130, 141, 143)  # success, Ctrl+C, broken pipe, terminated
OUTPUT_LINES = 40


def _paste(text):
    """Bracketed paste, so a multi-line message arrives as one prompt."""
    return f"\x1b[200~{text}\x1b[201~"


def _same_project(a, b):
    a, b = (a or "").rstrip("/") + "/", (b or "").rstrip("/") + "/"
    return a.startswith(b) or b.startswith(a)


class Features:
    def __init__(self, daemon, connection):
        self.d, self.conn = daemon, connection
        self.failures = deque(maxlen=8)
        self.next_id = 1

    # Failed commands -----------------------------------------------------------------------

    async def watch_commands(self):
        mode = iterm2.PromptMonitor.Mode.COMMAND_END.value
        await iterm2.notifications.async_subscribe_to_prompt_notification(self.conn, self._on_prompt, None, [mode])

    async def _on_prompt(self, _connection, message):
        if message.WhichOneof("event") != "command_end" or message.command_end.status in IGNORED_EXITS:
            return
        sid = message.session
        session = self.d.app.get_session_by_id(sid)
        if session is None or sid in self.d.sessions:
            return  # agent panes report their own failures
        prompt = await iterm2.async_get_prompt_by_id(self.conn, sid, message.unique_prompt_id) \
            if message.unique_prompt_id else await iterm2.async_get_last_prompt(self.conn, sid)
        if not prompt or not prompt.command:
            return
        end = prompt.output_range.end.y
        first = max(prompt.output_range.start.y, end - OUTPUT_LINES)
        lines = await session.async_get_contents(first, end - first) if end > first else []
        self.failures.append({"id": self.next_id, "pane": sid, "command": prompt.command.strip(),
                              "status": message.command_end.status, "cwd": prompt.working_directory or "",
                              "output": "\n".join(l.string for l in lines).rstrip(), "ts": time.time()})
        self.next_id += 1

    def failure_cards(self):
        out = []
        for f in self.failures:
            agent = self.agent_for(f["cwd"])
            out.append(dict(f, agent_sid=agent and agent["sid"], agent=agent and agent["agent"],
                            project=os.path.basename(f["cwd"].rstrip("/"))))
        return out[::-1]

    def agent_for(self, cwd):
        matches = [s for s in self.d.sessions.values() if s.get("cwd") and _same_project(s["cwd"], cwd)]
        return max(matches, key=lambda s: s["updated"], default=None)

    # Launching agents ----------------------------------------------------------------------

    async def launch(self, near_sid, agent, cwd, text, name):
        HANDOFFS.mkdir(parents=True, exist_ok=True)
        path = HANDOFFS / f"{name}-{time.strftime('%Y%m%d-%H%M%S')}.md"
        path.write_text(text)
        near = self.d.app.get_session_by_id(near_sid)
        if near is None:
            window = self.d.app.current_terminal_window
            new = (await window.async_create_tab()).current_session
        else:
            new = await near.async_split_pane(vertical=True)
        await new.async_send_text(handoff.launch_command(agent, cwd, str(path)) + "\r")
        return str(path)

    # Routes --------------------------------------------------------------------------------

    async def route(self, method, path, query, data):
        """Handle a feature route. Returns None when the path is not one of these."""
        if path == "/api/ports":
            return reply(200, {"ports": await asyncio.to_thread(ports.scan, str(Path.home()))})
        if path == "/api/ports/stop":
            listed = {p["pid"] for p in await asyncio.to_thread(ports.scan, str(Path.home()))}
            if int(data["pid"]) not in listed:
                return reply(409, {"error": "That process is no longer listening."})
            os.kill(int(data["pid"]), signal.SIGTERM)
            return reply(200, {"ok": True})
        if path == "/api/ports/open":
            subprocess.Popen(["open", f"http://localhost:{int(data['port'])}"])
            return reply(200, {"ok": True})
        if path.startswith("/api/failures/"):
            return await self.failure_route(path, data)
        if path == "/api/devserver":
            return reply(200, await self.dev_server(data))
        s = self.d.sessions.get(data.get("sid") or query.get("sid", ""))
        if path in ("/api/timeline", "/api/handoff") and not s:
            return reply(404, {"error": "That agent's tab is gone."})
        if path == "/api/timeline":
            return reply(200, {"items": await asyncio.to_thread(timeline.read, s, Path.home(), 60)})
        if path == "/api/handoff" and method == "GET":
            return reply(200, {"text": await asyncio.to_thread(self.handoff_text, s, query.get("mode", "continue"))})
        if path == "/api/handoff":
            to = "codex" if data.get("to") == "codex" else "claude"
            await self.launch(s["sid"], to, s["cwd"], data["text"], f"handoff-{os.path.basename(s['cwd'])}")
            return reply(200, {"ok": True})
        return None

    def handoff_text(self, s, mode):
        first = s["snapshots"][0] if s["snapshots"] else None
        diff = snapshot.diff(first["root"], first["tree"]) if first else None
        failures = [f for f in self.failures if _same_project(f["cwd"], s["cwd"])]
        return handoff.build(s, mode if mode in handoff.MODES else "continue",
                             timeline.read(s, Path.home(), 30), diff, failures)

    async def failure_route(self, path, data):
        f = next((f for f in self.failures if f["id"] == data.get("id")), None)
        if f is None:
            return reply(404, {"error": "That failure is gone."})
        if path == "/api/failures/dismiss":
            self.failures.remove(f)
            return reply(200, {"ok": True})
        if path == "/api/failures/send":
            agent = self.agent_for(f["cwd"])
            session = agent and self.d.app.get_session_by_id(agent["sid"])
            if not session:
                return reply(409, {"error": "No agent works in this project."})
            if agent["state"] in ("working", "waiting_permission"):
                return reply(409, {"error": "The agent is busy. Send it when its turn ends."})
            await session.async_send_text(_paste(handoff.failure_message(f)))
            await asyncio.sleep(0.2)
            await session.async_send_text("\r")
        else:  # /api/failures/fix
            to = "codex" if data.get("to") == "codex" else "claude"
            await self.launch(f["pane"], to, f["cwd"] or str(Path.home()), handoff.failure_message(f), "fix")
        self.failures.remove(f)
        return reply(200, {"ok": True})

    # Dev server tabs -----------------------------------------------------------------------

    async def dev_server(self, data):
        """Run an agent's dev server in a new tab beside its pane. Returns the log path for the agent."""
        near = self.d.app.get_session_by_id(data.get("sid", ""))
        window = near.window if near else self.d.app.current_terminal_window
        LOGS.mkdir(parents=True, exist_ok=True)
        cwd, command = data["cwd"], data["command"].rstrip("& ")
        log = LOGS / f"{os.path.basename(cwd)}-{time.strftime('%Y%m%d-%H%M%S')}.log"
        tab = await window.async_create_tab()
        await tab.async_set_title(f"dev: {os.path.basename(cwd)}")
        await tab.current_session.async_send_text(
            f"cd {shlex.quote(cwd)} && {command} 2>&1 | tee {shlex.quote(str(log))}\r")
        if near:
            await near.async_activate(select_tab=True, order_window_front=False)
        return {"log": str(log)}
