"""The hook command. Claude Code and Codex run it on every hook event.

It must never break the agent: it prints nothing and always exits 0.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request

from pitwall import config, snapshot
from pitwall.events import to_event


def post(daemon, path, body, timeout=1.5):
    req = urllib.request.Request(
        f"http://127.0.0.1:{daemon['port']}{path}", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "X-Pitwall-Token": daemon["token"]})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read() or b"{}")


def run(agent, name):
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
        daemon = config.read_daemon()
        event = to_event(agent, name, payload, os.environ, time.time())
        if not daemon or not event:
            return
        if name == "UserPromptSubmit" and event.get("cwd"):
            event["snapshot"] = snapshot.take(event["cwd"])
        post(daemon, "/api/event", event)
    except Exception:  # noqa: BLE001  a status hook must not fail the agent
        pass
