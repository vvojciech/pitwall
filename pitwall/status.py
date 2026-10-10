"""The native iTerm2 tab status (dot, status text, detail line) for an agent's state.

The colours match iTerm2's own Claude Code integration (cc-status), so both look the same.
"""
from __future__ import annotations

import asyncio

IT2 = "/Applications/iTerm.app/Contents/Resources/utilities/it2"
MAX_DETAIL = 60
# Write after iTerm2's own cc-status hook, which sets the same status without a detail line.
DELAY = 0.4


def _short(text):
    text = (text or "").strip()
    return text if len(text) <= MAX_DETAIL else text[:MAX_DETAIL - 1] + "…"


def native_status(s):
    """Return (status, dot colour, detail) for a session dict."""
    state, task = s["state"], s.get("task") or ""
    if state == "working":
        return "working", "#5f87ff", _short(s.get("action") or task)
    if state == "waiting_permission":
        return "waiting", "#ff9500", _short(f"Allow? {s['permission']}" if s.get("permission") else "Needs permission")
    if state == "waiting_input":
        return "waiting", "#ff9500", "Waiting for you"
    if state == "done":
        return "idle", "#00d75f", _short(f"Done: {task}" if task else "Done")
    if state == "failed":
        return "idle", "#ff5f5f", _short(f"Failed: {s.get('error') or 'agent stopped'}")
    return "idle", "#888888", _short(task)


class NativeStatus:
    """Writes the tab status through iTerm2's it2 tool, one pending write per session."""

    def __init__(self):
        self.pending = {}

    def write(self, s):
        task = self.pending.pop(s["sid"], None)
        if task:
            task.cancel()
        self.pending[s["sid"]] = asyncio.get_running_loop().create_task(self._write(s["sid"], native_status(s)))

    async def _write(self, sid, status):
        await asyncio.sleep(DELAY)
        state, dot, detail = status
        proc = await asyncio.create_subprocess_exec(
            IT2, "session", "set-status", "--session", sid, "--status", state, "--dot-color", dot,
            "--detail", detail, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        await proc.wait()
        self.pending.pop(sid, None)
