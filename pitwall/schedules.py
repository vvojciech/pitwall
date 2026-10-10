"""Scheduled prompts of a Claude Code session: /loop wake-ups, CronCreate jobs and reminders.

Claude Code keeps them in the session's memory and reports the list in hook payloads, without a
next fire time. This module reads the 5-field cron expressions (local time) and builds the rows
the panel shows.
"""
from __future__ import annotations

from datetime import datetime, timedelta

GRACE = 15 * 60  # Claude Code fires a recurring job up to 15 minutes late
EXPIRY = 7 * 86400  # and deletes it 7 days after it was made
HORIZON = timedelta(days=366)
# (low, high) for minute, hour, day of month, month, day of week (0 and 7 are Sunday)
RANGES = ((0, 59), (0, 23), (1, 31), (1, 12), (0, 7))


def _field(text, low, high):
    values = set()
    for part in text.split(","):
        span, _, step = part.partition("/")
        step = int(step) if step else 1
        if span == "*":
            start, end = low, high
        elif "-" in span:
            start, end = (int(x) for x in span.split("-", 1))
        else:
            start = end = int(span)
        if step < 1 or start > end or start < low or end > high:
            raise ValueError(part)
        values.update(range(start, end + 1, step))
    return values


def parse(expr):
    """(minutes, hours, days, months, weekdays, any_day, any_weekday), or None when invalid."""
    parts = (expr or "").split()
    if len(parts) != 5:
        return None
    try:
        fields = [_field(text, low, high) for text, (low, high) in zip(parts, RANGES)]
    except ValueError:
        return None
    fields[4] = {d % 7 for d in fields[4]}
    return (*fields, parts[2] == "*", parts[4] == "*")


def _day_matches(day, days, weekdays, any_day, any_weekday):
    in_month, in_week = day.day in days, (day.weekday() + 1) % 7 in weekdays
    if any_day or any_weekday:
        return in_month and in_week
    return in_month or in_week  # cron: when both are restricted, either one is enough


def next_fire(expr, after):
    """Epoch seconds of the first match strictly after `after`, or None."""
    fields = parse(expr)
    if not fields:
        return None
    minutes, hours, days, months, weekdays, any_day, any_weekday = fields
    t = datetime.fromtimestamp(after).replace(second=0, microsecond=0) + timedelta(minutes=1)
    end = t + HORIZON
    while t < end:
        if t.month not in months:
            t = (t.replace(day=1, hour=0, minute=0) + timedelta(days=32)).replace(day=1)
        elif not _day_matches(t, days, weekdays, any_day, any_weekday):
            t = t.replace(hour=0, minute=0) + timedelta(days=1)
        elif t.hour not in hours:
            t = t.replace(minute=0) + timedelta(hours=1)
        elif t.minute not in minutes:
            t += timedelta(minutes=1)
        else:
            return t.timestamp()
    return None


def _row(job, now):
    prompt = job.get("prompt") or ""
    loop = prompt.startswith("/loop")
    kind = "loop" if loop else "repeats" if job.get("recurring") else "once"
    nxt = job.get("at") or next_fire(job.get("schedule"), max(job.get("first_seen") or 0,
                                                              job.get("last_fired") or 0, now - GRACE))
    return {"id": job["id"], "kind": kind, "text": prompt[len("/loop"):].strip() if loop else prompt,
            "next": nxt, "human": job.get("human") or job.get("schedule") or "", "reason": job.get("reason"),
            "expires": (job.get("first_seen") or now) + EXPIRY if job.get("recurring") else None,
            "stopping": bool(job.get("stopping"))}


def view(session, now):
    """The session's jobs as panel rows, soonest first. Rows without a countdown go last."""
    rows = [_row(j, now) for j in (session.get("schedules") or {}).values()]
    return sorted(rows, key=lambda r: (r["next"] is None, r["next"] or 0))
