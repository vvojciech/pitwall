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


def limits(home):
    """Plan limits per agent: {claude: {...}, codex: {...}}; a missing source gives None."""
    out = {"claude": None, "codex": None}
    try:
        status = json.loads(STATUS.read_text())
        r = status.get("rate_limits") or {}
        pick = lambda w: w and {"used": w.get("used_percentage"), "resets_at": w.get("resets_at")}
        if r:
            out["claude"] = {"five_hour": pick(r.get("five_hour")), "week": pick(r.get("seven_day")),
                             "seen": STATUS.stat().st_mtime}
    except (OSError, ValueError, AttributeError):
        pass
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
