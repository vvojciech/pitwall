"""How full each agent's context window is.

Claude Code passes it to the status line, which Pitwall's wrapper saves per session in
~/.pitwall/status/<session id>.json. Codex writes it into its transcript as token_count events.
"""
from __future__ import annotations

import json
import re

from pitwall import timeline

SESSION_ID = re.compile(r"^[A-Za-z0-9-]+$")
TAIL_BYTES = 200_000  # the newest token_count is near the end of a Codex transcript
_codex_cache = {}  # path -> (mtime, result)


def from_claude(status):
    w = status.get("context_window") or {}
    if w.get("used_percentage") is None:
        return None
    usage = w.get("current_usage") or {}
    tokens = sum(usage.get(k) or 0 for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
    return {"used": round(w["used_percentage"]), "size": w.get("context_window_size"), "tokens": tokens or None}


def from_codex(lines):
    found = None
    for line in lines:
        if '"token_count"' not in line:
            continue
        try:
            info = (json.loads(line).get("payload") or {}).get("info") or {}
        except ValueError:
            continue
        last, size = (info.get("last_token_usage") or {}).get("total_tokens"), info.get("model_context_window")
        if last and size:
            found = {"used": round(100 * last / size), "size": size, "tokens": last}
    return found


def for_session(s, pitwall_home, home):
    """The context fill of one agent, or None when it is not known yet."""
    sid = s.get("agent_session") or ""
    if not SESSION_ID.match(sid):
        return None
    if s.get("agent") == "claude":
        try:
            return from_claude(json.loads((pitwall_home / "status" / f"{sid}.json").read_text()))
        except (OSError, ValueError):
            return None
    path = timeline.transcript_path(s, home)
    if not path:
        return None
    mtime = path.stat().st_mtime
    hit = _codex_cache.get(path)
    if hit and hit[0] == mtime:
        return hit[1]
    with open(path, "rb") as f:
        f.seek(max(0, path.stat().st_size - TAIL_BYTES))
        result = from_codex(f.read().decode(errors="replace").splitlines())
    _codex_cache[path] = (mtime, result)
    return result
