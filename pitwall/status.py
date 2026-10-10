"""The native iTerm2 tab status (dot, status text, detail line) for agents without iTerm2's own hook.

iTerm2's Claude Code integration (cc-status) already writes this status for Claude, so Pitwall
writes it only for other agents. The colours match cc-status, so all tabs look the same.
"""
from __future__ import annotations

import asyncio

IT2 = "/Applications/iTerm.app/Contents/Resources/utilities/it2"
MAX_DETAIL = 60
IDLE, GREY, WORKING, WAITING, RED = "#00d75f", "#888888", "#ff9500", "#5f87ff", "#ff5f5f"


def _short(text):
    text = (text or "").strip()
    return text if len(text) <= MAX_DETAIL else text[:MAX_DETAIL - 1] + "…"


def native_status(s):
    """Return (status, dot colour, text colour, detail), or None when iTerm2 handles the agent."""
    if s.get("agent") == "claude":
        return None
    state, task = s["state"], s.get("task") or ""
    if state == "working":
        return "working", WORKING, WORKING, _short(s.get("action") or task)
    if state == "waiting_permission":
        return "waiting", WAITING, WAITING, _short(f"Allow? {s['permission']}" if s.get("permission") else "Needs permission")
    if state == "waiting_input":
        return "waiting", WAITING, WAITING, "Waiting for you"
    if state == "done":
        return "idle", IDLE, GREY, _short(f"Done: {task}" if task else "Done")
    if state == "failed":
        return "idle", RED, GREY, _short(f"Failed: {s.get('error') or 'agent stopped'}")
    return "idle", IDLE, GREY, _short(task)


class NativeStatus:
    """Writes the tab status through iTerm2's it2 tool."""

    def write(self, s):
        status = native_status(s)
        if status:
            asyncio.get_running_loop().create_task(self._write(s["sid"], status))

    async def _write(self, sid, status):
        state, dot, text, detail = status
        proc = await asyncio.create_subprocess_exec(
            IT2, "session", "set-status", "--session", sid, "--status", state, "--dot-color", dot,
            "--text-color", text, "--detail", detail,
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        await proc.wait()
