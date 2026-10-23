"""Collect activity for the last days and the plan limits, with a cache per transcript file."""
from __future__ import annotations

import json
import math
import sys
import time
from datetime import date, timedelta
from pathlib import Path

from pitwall import config
from pitwall.activity import codex_limits, summarize

CACHE = config.HOME / "activity-cache.json"
LIMITS_SEEN = config.HOME / "limits-seen.json"
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


def newest_rate_limits(snapshots, now):
    """The newest value of each window across the `rate_limits` of all sessions, in Claude's format.

    `snapshots` are (changed, rate_limits) pairs: `changed` is when that session's limits last
    changed. An idle session re-renders its status line with the limits of its last reply, so no
    one snapshot is current, and a limit reset drops the use but keeps the reset time. So the
    latest reset, then the latest change, is the newest value. A window that has reset is left
    out: its new use is not known yet.
    """
    out = {}
    for changed, s in snapshots:
        for key, w in (s.items() if isinstance(s, dict) else ()):
            if not isinstance(w, dict) or w.get("used_percentage") is None or not w.get("resets_at"):
                continue
            if key not in out or (w["resets_at"], changed) > out[key][0]:
                out[key] = (w["resets_at"], changed), w
    return {k: w for k, (_, w) in out.items() if w["resets_at"] > now}


def claude_limits(snapshots, now):
    """The newest Claude limits in the panel's format, or None."""
    r = newest_rate_limits(snapshots, now)
    # Claude's windows are fixed; the status line does not send their length.
    pick = lambda w, window: w and {"used": w["used_percentage"], "resets_at": w["resets_at"], "window": window}
    out = {"five_hour": pick(r.get("five_hour"), 5 * 3600), "week": pick(r.get("seven_day"), 7 * 86400)}
    return out if any(out.values()) else None


def windows_left(limits):
    """The 5-hour windows still to come before the weekly limit resets, the current one included."""
    five, week = (limits or {}).get("five_hour"), (limits or {}).get("week")
    if not (five and week and five.get("resets_at") and week.get("resets_at")):
        return None
    return max(0, math.ceil((week["resets_at"] - five["resets_at"]) / (5 * 3600))) + 1


def claude_snapshots():
    """(changed, rate_limits) of every saved Claude session status line, and the newest save time.

    A file's time moves on every render, so keep when its limits last changed in LIMITS_SEEN.
    """
    try:
        known = json.loads(LIMITS_SEEN.read_text())
    except (OSError, ValueError):
        known = {}
    snapshots, seen, now_known = [], 0, {}
    for path in (config.HOME / "status").glob("*.json"):
        try:
            limits, mtime = json.loads(path.read_text()).get("rate_limits"), path.stat().st_mtime
        except (OSError, ValueError, AttributeError):
            continue
        prior = known.get(path.name)
        changed = prior[1] if prior and prior[0] == limits else mtime
        now_known[path.name] = [limits, changed]
        snapshots.append((changed, limits))
        seen = max(seen, mtime)
    if now_known != known:
        try:
            config.write_private(LIMITS_SEEN, json.dumps(now_known))
        except OSError:
            pass  # another status line wrote it at the same time; the next read retries
    return snapshots, seen


def limits(home):
    """Plan limits per agent: {claude: {...}, codex: {...}}; a missing source gives None."""
    out = {"claude": None, "codex": None}
    snapshots, seen = claude_snapshots()
    claude = claude_limits(snapshots, time.time())
    if claude:
        out["claude"] = dict(claude, seen=seen, windows_left=windows_left(claude))
    newest = max(home.glob(".codex/sessions/*/*/*/*.jsonl"), key=lambda p: p.stat().st_mtime, default=None)
    if newest:
        with open(newest, "rb") as f:
            f.seek(max(0, newest.stat().st_size - TAIL_BYTES))
            found = codex_limits(f.read().decode(errors="replace").splitlines())
        if found:
            out["codex"] = dict(found, seen=newest.stat().st_mtime, windows_left=windows_left(found))
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


if __name__ == "__main__":
    # The status line wrapper: read Claude Code's status line input, print it with the newest limits.
    raw = sys.stdin.read()
    merged = newest_rate_limits(claude_snapshots()[0], time.time())
    sys.stdout.write(json.dumps(dict(json.loads(raw), rate_limits=merged), separators=(",", ":")) if merged else raw)
