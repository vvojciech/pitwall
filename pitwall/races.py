"""Runs agent races in iTerm2: one tab, one split per agent, each agent in its own worktree."""
from __future__ import annotations

import asyncio
import json
import os
import re
import shlex
import time

from pitwall import config, race
from pitwall.http import reply
from pitwall.iterm import focus, screen_text
from pitwall.snapshot import repo_root

RACES_FILE = config.HOME / "races.json"
MAX_DIFF = 60_000
# Each agent asks once whether to trust a new folder. (question, cursor on the option we skip to, keys)
TRUST = {
    "claude": (re.compile(r"Yes, I trust this folder"), re.compile(r"❯\s*No, exit"), "\x1b[B\r"),
    "codex": (re.compile(r"Trust this folder\?"), re.compile(r"›\s*1\. Trust and continue"), "\r"),
}


async def trust_question(app, entry):
    """True when the agent in this entry shows its trust question with the default cursor."""
    pane = app.get_session_by_id(entry.get("sid", ""))
    if pane is None or entry["agent"] not in TRUST:
        return False
    question, cursor, _ = TRUST[entry["agent"]]
    text = await screen_text(pane, 40)
    return bool(question.search(text) and cursor.search(text))


class Races:
    def __init__(self, features):
        self.f, self.d = features, features.d
        try:
            self.races = json.loads(RACES_FILE.read_text())
        except (OSError, ValueError):
            self.races = []

    def save(self):
        config.write_private(RACES_FILE, json.dumps(self.races))

    def projects(self):
        """Repositories the current agents work in, for the race form. Race worktrees are left out."""
        roots = {repo_root(s["cwd"]) for s in self.d.sessions.values()
                 if s.get("cwd") and f"/{race.WORKTREES}/race-" not in s["cwd"]}
        return sorted(r for r in roots if r)

    async def start(self, repo, task, agents):
        race_id = time.strftime("%m%d-%H%M%S")
        entries = await asyncio.to_thread(race.create, repo, race_id, agents)
        tab = await self.d.app.current_terminal_window.async_create_tab()
        await tab.async_set_title(f"race: {task[:40]}")
        panes = [tab.current_session]
        for _ in entries[1:]:
            panes.append(await panes[-1].async_split_pane(vertical=True))
        for entry, pane in zip(entries, panes):
            entry["sid"] = pane.session_id
            await pane.async_send_text(f"cd {shlex.quote(entry['worktree'])} && {entry['agent']} {shlex.quote(task)}\r")
        self.races.append({"id": race_id, "repo": repo, "task": task, "entries": entries, "started": time.time()})
        self.save()

    async def asking_trust(self):
        """(race id, entry index) pairs whose agent waits for a trust answer."""
        found = set()
        for r in self.races:
            for n, e in enumerate(r["entries"]):
                s = self.d.sessions.get(e.get("sid", ""))
                if (not s or s["state"] == "idle") and await trust_question(self.d.app, e):
                    found.add((r["id"], n))
        return found

    def view(self, trust):
        out = []
        for r in self.races:
            entries = []
            for n, e in enumerate(r["entries"]):
                s = self.d.sessions.get(e.get("sid", ""))
                exists = os.path.isdir(e["worktree"])
                state = "trust" if (r["id"], n) in trust else s["state"] if s else "starting"
                entries.append({"n": n, "agent": e["agent"], "state": state,
                                "applied": e.get("applied", False), "stat": race.stat(e) if exists else None})
            out.append({"id": r["id"], "task": r["task"], "project": os.path.basename(r["repo"]), "entries": entries})
        return out

    async def route(self, method, path, query, data):
        if path == "/api/races":
            trust = await self.asking_trust()
            return reply(200, {"races": await asyncio.to_thread(self.view, trust), "projects": self.projects()})
        if path == "/api/race/start":
            repo = repo_root(data.get("repo") or "")
            agents = [a for a in data.get("agents", []) if a in ("claude", "codex")][:4]
            task = (data.get("task") or "").strip()
            if not repo or len(agents) < 2 or not task:
                return reply(400, {"error": "Choose a git project, a task and at least two agents."})
            await self.start(repo, task, agents)
            return reply(200, {"ok": True})
        r = next((r for r in self.races if r["id"] == (data.get("id") or query.get("id"))), None)
        if r is None:
            return reply(404, {"error": "That race is gone."})
        if path == "/api/race/clean":
            for e in r["entries"]:
                pane = self.d.app.get_session_by_id(e.get("sid", ""))
                if pane:
                    await pane.async_close(force=True)
            await asyncio.to_thread(race.clean_up, r["repo"], r["entries"])
            self.races.remove(r)
            self.save()
            return reply(200, {"ok": True})
        entry = r["entries"][int(data.get("n", query.get("n", 0)))]
        if path == "/api/race/trust":
            if not await trust_question(self.d.app, entry):
                return reply(409, {"error": "The trust question is not on screen. Open the race tab to answer."})
            await self.d.app.get_session_by_id(entry["sid"]).async_send_text(TRUST[entry["agent"]][2])
            return reply(200, {"ok": True})
        if path == "/api/race/show":
            pane = self.d.app.get_session_by_id(entry.get("sid", ""))
            if pane is None:
                return reply(404, {"error": "That agent's pane is gone."})
            await focus(self.d.app, pane)
            return reply(200, {"ok": True})
        if path == "/api/race/diff":
            text = await asyncio.to_thread(race.diff, entry)
            return reply(200, {"diff": text if len(text) <= MAX_DIFF else text[:MAX_DIFF] + "\n[cut]"})
        if path == "/api/race/apply":
            error = await asyncio.to_thread(race.apply, r["repo"], entry)
            if error:
                return reply(409, {"error": f"Not applied: {error}"})
            entry["applied"] = True
            self.save()
            return reply(200, {"ok": True})
        return None
