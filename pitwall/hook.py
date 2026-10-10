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

from pitwall import config, snapshot
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


def nested():
    out = subprocess.run(["ps", "-axo", "pid=,ppid=,comm="], capture_output=True, text=True).stdout
    return agent_depth(parse_ps(out), os.getpid()) >= 2


def share_memory(agent, payload):
    """On SessionStart, print the other agent's notes as context for this session."""
    if os.environ.get("PITWALL_SHARED_MEMORY") == "0" or not payload.get("cwd"):
        return
    text = context_for(agent, payload["cwd"], Path.home())
    if text:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}}))


def run(agent, name):
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
        if name == "SessionStart":
            share_memory(agent, payload)
        daemon = config.read_daemon()
        event = to_event(agent, name, payload, os.environ, time.time())
        # An agent run inside another agent's pane (claude -p in a script) shares its tab id.
        if not daemon or not event or nested():
            return
        if name == "UserPromptSubmit" and event.get("cwd"):
            event["snapshot"] = snapshot.take(event["cwd"])
        post(daemon, "/api/event", event)
    except Exception:  # noqa: BLE001  a status hook must not fail the agent
        pass
