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

from pitwall import config, handoff, mapdata, ports, snapshot, timeline, usage
from pitwall.http import reply
from pitwall.loops import Loops
from pitwall.races import Races
from pitwall.snapshot import repo_root, same_project

HANDOFFS = config.HOME / "handoffs"
LOGS = config.HOME / "logs"
IGNORED_EXITS = (0, 130, 141, 143)  # success, Ctrl+C, broken pipe, terminated
OUTPUT_LINES = 40


def _paste(text):
    """Bracketed paste, so a multi-line message arrives as one prompt."""
    return f"\x1b[200~{text}\x1b[201~"


class Features:
    def __init__(self, daemon, connection):
        self.d, self.conn = daemon, connection
        self.failures = deque(maxlen=8)
        self.next_id = 1
        self.loops = Loops(self)
        self.races = Races(self)

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
        output = "\n".join(l.string.replace("\x00", " ") for l in lines).rstrip()
        port = ports.busy_port(output, prompt.command)
        self.failures.append({"id": self.next_id, "pane": sid, "command": prompt.command.strip(),
                              "status": message.command_end.status, "cwd": prompt.working_directory or "",
                              "output": output, "ts": time.time(),
                              "busy": port and await asyncio.to_thread(ports.holder_of, port)})
        self.next_id += 1

    def failure_cards(self):
        out = []
        for f in self.failures:
            agent = self.agent_for(f["cwd"])
            out.append(dict(f, agent_sid=agent and agent["sid"], agent=agent and agent["agent"],
                            project=os.path.basename((repo_root(f["cwd"]) or f["cwd"]).rstrip("/"))))
        return out[::-1]

    def agent_for(self, cwd):
        matches = [s for s in self.d.sessions.values() if s.get("cwd") and same_project(s["cwd"], cwd)]
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
        return str(path), new.session_id

    async def paste(self, session, text):
        """Type a message into an agent as one prompt, then submit it."""
        await session.async_send_text(_paste(text))
        await asyncio.sleep(0.2)  # let the agent finish reading the paste before Enter
        await session.async_send_text("\r")

    # Routes --------------------------------------------------------------------------------

    async def route(self, method, path, query, data):
        """Handle a feature route. Returns None when the path is not one of these."""
        if path.startswith("/api/race"):
            return await self.races.route(method, path, query, data)
        if path == "/api/activity":
            days = min(max(int(query.get("days") or 7), 1), 30)
            return reply(200, await asyncio.to_thread(usage.report, Path.home(), days))
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
        if path.startswith("/api/loop/"):
            return await self.loop_route(path, s, data)
        if path in ("/api/timeline", "/api/handoff", "/api/map") and not s:
            return reply(404, {"error": "That agent's tab is gone."})
        if path == "/api/map":
            mode = "uncommitted" if query.get("mode") == "uncommitted" else "turn"
            return reply(200, await asyncio.to_thread(mapdata.map_for, s, mode))
        if path == "/api/timeline":
            return reply(200, {"items": await asyncio.to_thread(timeline.read, s, Path.home(), 60)})
        if path == "/api/handoff" and method == "GET":
            return reply(200, {"text": await asyncio.to_thread(self.handoff_text, s, query.get("mode", "continue"))})
        if path == "/api/handoff":
            to = "codex" if data.get("to") == "codex" else "claude"
            await self.launch(s["sid"], to, s["cwd"], data["text"], f"handoff-{os.path.basename(s['cwd'])}")
            return reply(200, {"ok": True})
        return None

    async def loop_route(self, path, s, data):
        if not s:
            return reply(404, {"error": "That agent's tab is gone."})
        if path == "/api/loop/start":
            if s["state"] in ("working", "waiting_permission"):
                return reply(409, {"error": "Start the loop when the agent finishes its turn."})
            reviewer = "codex" if data.get("reviewer") == "codex" else "claude"
            rounds = min(max(int(data.get("rounds") or 3), 1), 10)
            await self.loops.start(s, reviewer, rounds, bool(data.get("auto")))
        elif not s.get("loop"):
            return reply(409, {"error": "No review loop on this agent."})
        elif path == "/api/loop/send":
            error = await self.loops.send(s)
            if error:
                return reply(409, {"error": error})
        elif path == "/api/loop/stop":
            self.loops.stop(s)
        elif path == "/api/loop/close":
            s.pop("loop", None)
            self.d.save()
        return reply(200, {"ok": True})

    def handoff_text(self, s, mode):
        first = s["snapshots"][0] if s["snapshots"] else None
        diff = snapshot.diff(first["root"], first["tree"]) if first else None
        failures = [f for f in self.failures if same_project(f["cwd"], s["cwd"])]
        return handoff.build(s, mode if mode in handoff.MODES else "continue",
                             timeline.read(s, Path.home(), 30), diff, failures)

    async def failure_route(self, path, data):
        f = next((f for f in self.failures if f["id"] == data.get("id")), None)
        if f is None:
            return reply(404, {"error": "That failure is gone."})
        if path == "/api/failures/dismiss":
            self.failures.remove(f)
            return reply(200, {"ok": True})
        if path == "/api/failures/free-port":
            busy = f.get("busy")
            now = busy and await asyncio.to_thread(ports.holder_of, busy["port"])
            if not now or now["pid"] != busy["pid"]:
                f["busy"] = None
                return reply(409, {"error": "That process no longer holds the port. Run the command again."})
            os.kill(busy["pid"], signal.SIGTERM)
            f["busy"] = None
            return reply(200, {"ok": True})
        if path == "/api/failures/send":
            agent = self.agent_for(f["cwd"])
            session = agent and self.d.app.get_session_by_id(agent["sid"])
            if not session:
                return reply(409, {"error": "No agent works in this project."})
            if agent["state"] in ("working", "waiting_permission"):
                return reply(409, {"error": "The agent is busy. Send it when its turn ends."})
            await self.paste(session, handoff.failure_message(f))
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
