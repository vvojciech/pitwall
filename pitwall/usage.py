"""Collect activity for the last days and the plan limits, with a cache per transcript file."""
from __future__ import annotations

import json
import time
from datetime import date, timedelta
from pathlib import Path

from pitwall import config
from pitwall.activity import codex_limits, summarize

CACHE = config.HOME / "activity-cache.json"
STATUS = config.HOME / "claude-status.json"
TAIL_BYTES = 400_000  # Codex limits are near the end of its newest transcript
KEEP_DAYS = 30  # the longest range the activity page shows


def _files(home, since):
    for agent, pattern in (("claude", ".claude/projects/*/*.jsonl"), ("codex", ".codex/sessions/*/*/*/*.jsonl")):
        for path in home.glob(pattern):
            try:
                stat = path.stat()
            except OSError:
                continue
            if stat.st_mtime >= since:
                yield agent, path, stat


def activity(home, days=7):
    """Rows for the last `days` days, newest transcripts re-read only when they changed."""
    try:
        cache = json.loads(CACHE.read_text())
    except (OSError, ValueError):
        cache = {}
    first = (date.today() - timedelta(days=days - 1)).isoformat()
    oldest = time.time() - KEEP_DAYS * 86400
    cache = {k: v for k, v in cache.items() if v["stamp"][0] >= oldest}  # other callers read other ranges
    rows, changed = [], False
    for agent, path, stat in _files(home, time.time() - days * 86400):
        key, stamp = str(path), [stat.st_mtime, stat.st_size]
        entry = cache.get(key)
        if not entry or entry["stamp"] != stamp:
            with open(path, errors="replace") as f:
                entry = cache[key] = {"stamp": stamp, "rows": summarize(f, agent)}
            changed = True
        rows += [r for r in entry["rows"] if r["day"] >= first]
    if changed:
        config.write_private(CACHE, json.dumps(cache))
    return rows


def claude_limits(snapshots, now):
    """The newest Claude limits across the `rate_limits` of all sessions, or None.

    An idle session re-renders its status line with the limits of its last reply, so no one
    snapshot is current. Use only grows inside a window, so the latest reset, then the highest
    use, is the newest value. A window that has reset gives None: its new use is not known yet.
    """
    def newest(key, window):
        seen = [w for s in snapshots if isinstance(s, dict) and isinstance(w := s.get(key), dict)
                and w.get("used_percentage") is not None and w.get("resets_at")]
        if not seen:
            return None
        w = max(seen, key=lambda w: (w["resets_at"], w["used_percentage"]))
        return {"used": w["used_percentage"], "resets_at": w["resets_at"], "window": window} if w["resets_at"] > now else None

    # Claude's windows are fixed; the status line does not send their length.
    out = {"five_hour": newest("five_hour", 5 * 3600), "week": newest("seven_day", 7 * 86400)}
    return out if any(out.values()) else None


def limits(home):
    """Plan limits per agent: {claude: {...}, codex: {...}}; a missing source gives None."""
    out = {"claude": None, "codex": None}
    snapshots, seen = [], 0
    for path in [STATUS, *(config.HOME / "status").glob("*.json")]:
        try:
            snapshots.append(json.loads(path.read_text()).get("rate_limits"))
            seen = max(seen, path.stat().st_mtime)
        except (OSError, ValueError, AttributeError):
            pass
    claude = claude_limits(snapshots, time.time())
    if claude:
        out["claude"] = dict(claude, seen=seen)
    newest = max(home.glob(".codex/sessions/*/*/*/*.jsonl"), key=lambda p: p.stat().st_mtime, default=None)
    if newest:
        with open(newest, "rb") as f:
            f.seek(max(0, newest.stat().st_size - TAIL_BYTES))
            found = codex_limits(f.read().decode(errors="replace").splitlines())
        if found:
            out["codex"] = dict(found, seen=newest.stat().st_mtime)
    return out


def installed(home):
    """The agents on this Mac, by their home folder; the panel draws only these."""
    return [a for a in ("claude", "codex") if (home / f".{a}").is_dir()]


def report(home, days=7):
    rows = activity(home, days)
    today = date.today().isoformat()
    total = lambda key, rs: sum(r[key] for r in rs)
    today_rows = [r for r in rows if r["day"] == today]
    return {"days": days, "rows": rows, "limits": limits(home), "agents": installed(home),
            "today": {k: total(k, today_rows) for k in ("active", "prompts", "tokens", "files", "commands")}}
