"""The hook command. Claude Code and Codex run it on every hook event.

It must never break the agent: it always exits 0, and it prints only the SessionStart context.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request

from pitwall import config, settings, snapshot
from pathlib import Path

from pitwall.events import to_event
from pitwall.memory import context_for
from pitwall.state import agent_of


def post(daemon, path, body, timeout=1.5):
    req = urllib.request.Request(
        f"http://127.0.0.1:{daemon['port']}{path}", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "X-Pitwall-Token": daemon["token"]})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read() or b"{}")


def parse_ps(text):
    """{pid: (ppid, command)} from `ps -axo pid=,ppid=,comm=`."""
    table = {}
    for line in text.splitlines():
        parts = line.split(None, 2)
        if len(parts) == 3:
            table[int(parts[0])] = (int(parts[1]), parts[2])
    return table


def agent_depth(table, pid):
    """How many agent processes are above pid. Two or more means an agent runs inside an agent."""
    depth, seen = 0, set()
    while pid in table and pid not in seen:
        seen.add(pid)
        parent, command = table[pid]
        depth += bool(agent_of(command))
        pid = parent
    return depth


def agent_pid(table, pid):
    """The pid of the nearest agent process above pid: the job iTerm2 reports for its tab."""
    seen = set()
    while pid in table and pid not in seen:
        seen.add(pid)
        parent, command = table[pid]
        if agent_of(command):
            return pid
        pid = parent
    return None


def process_table():
    out = subprocess.run(["ps", "-axo", "pid=,ppid=,comm="], capture_output=True, text=True).stdout
    return parse_ps(out)


def nested(table=None):
    return agent_depth(table if table is not None else process_table(), os.getpid()) >= 2


def share_memory(agent, payload, prefs):
    """On SessionStart, print the other agent's notes as context for this session."""
    if os.environ.get("PITWALL_SHARED_MEMORY") == "0" or not prefs["shared_memory"] or not payload.get("cwd"):
        return
    text = context_for(agent, payload["cwd"], Path.home())
    if text:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}}))


def run(agent, name):
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
        prefs = settings.current()
        if name == "SessionStart":
            share_memory(agent, payload, prefs)
        daemon = config.read_daemon()
        event = to_event(agent, name, payload, os.environ, time.time())
        if not daemon or not event:
            return
        table = process_table()
        # An agent run inside another agent's pane (claude -p in a script) shares its tab id.
        if nested(table):
            return
        # iTerm2 gives every tab a new id when it restarts, but an agent started before keeps the
        # old one in ITERM_SESSION_ID. Its process stays, so the service matches on its pid.
        event["agent_pid"] = agent_pid(table, os.getpid())
        if name == "UserPromptSubmit" and event.get("cwd") and prefs["undo"]:
            event["snapshot"] = snapshot.take(event["cwd"])
        post(daemon, "/api/event", event)
    except Exception:  # noqa: BLE001  a status hook must not fail the agent
        pass
