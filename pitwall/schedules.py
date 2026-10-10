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


def _is_loop(job):
    return (job.get("prompt") or "").startswith("/loop")


def _time_wakeup(s):
    """A /loop wake-up reaches Pitwall as a tool call and as a one-shot job; join the two."""
    wake = s.get("wakeup")
    for job in s["schedules"].values():
        if wake and not job.get("recurring") and job.get("prompt") == wake["prompt"]:
            job.update(at=wake["at"], reason=wake["reason"])


def apply(s, event):
    """Update the session's jobs from one event. The list at each Stop is the authority."""
    jobs, ts = s.setdefault("schedules", {}), event["ts"]
    if isinstance(event.get("crons"), list):  # hooks before 0.7 sent a count
        jobs = s["schedules"] = {c["id"]: dict(jobs.get(c["id"], {}), **c) for c in event["crons"]}
    if event.get("cron_add"):
        job = event["cron_add"]
        jobs[job["id"]] = dict(jobs.get(job["id"], {}), **job)
    if event.get("cron_del"):
        jobs.pop(event["cron_del"], None)
    wake = event.get("wakeup")
    if wake and wake["stop"]:
        s["wakeup"] = None
        for key in [k for k, job in jobs.items() if _is_loop(job)]:
            del jobs[key]
    elif wake:
        s["wakeup"] = wake
    for job in jobs.values():
        job.setdefault("first_seen", ts)
    _time_wakeup(s)
    fired = event["event"] == "UserPromptSubmit" and event.get("prompt_line")
    for key, job in list(jobs.items()) if fired else ():
        if job.get("prompt") == fired:
            if job.get("recurring"):
                job["last_fired"] = ts
            else:
                del jobs[key]


MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def describe(expr):
    """Plain words for the common cron shapes. Claude Code's own label is raw for one-shot jobs."""
    parts = (expr or "").split()
    if len(parts) != 5 or not parse(expr):
        return expr or ""
    minute, hour, day, month, weekday = parts
    num = str.isdigit
    if parts == ["*"] * 5:
        return "Every minute"
    if minute.startswith("*/") and parts[1:] == ["*"] * 4:
        return f"Every {minute[2:]} minutes"
    if num(minute) and parts[1:] == ["*"] * 4:
        return f"Every hour at :{int(minute):02d}"
    if not (num(minute) and num(hour)):
        return expr
    clock = f"{int(hour):02d}:{int(minute):02d}"
    if (day, month, weekday) == ("*", "*", "*"):
        return f"Every day at {clock}"
    if (day, month, weekday) == ("*", "*", "1-5"):
        return f"Weekdays at {clock}"
    if num(day) and num(month) and weekday == "*":
        return f"Once, {int(day)} {MONTHS[int(month) - 1]} at {clock}"
    return expr


def stop_message(job):
    """What Pitwall types into the tab to stop a job. Claude Code has no outside API for it."""
    text = f"Cancel the scheduled job {job['id']} with CronDelete."
    if _is_loop(job):
        text += " It drives a /loop: also call ScheduleWakeup with stop: true, and do not schedule it again."
    return text + " Reply with one short line."


def _row(job, now):
    prompt = job.get("prompt") or ""
    loop = prompt.startswith("/loop")
    kind = "loop" if loop else "repeats" if job.get("recurring") else "once"
    nxt = job.get("at") or next_fire(job.get("schedule"), max(job.get("first_seen") or 0,
                                                              job.get("last_fired") or 0, now - GRACE))
    schedule = job.get("schedule") or ""
    human = "One wake-up, timed by Claude" if job.get("at") else \
        job["human"] if job.get("human") and job["human"] != schedule else describe(schedule)
    return {"id": job["id"], "kind": kind, "text": prompt[len("/loop"):].strip() if loop else prompt,
            "next": nxt, "human": human, "reason": job.get("reason"),
            "expires": (job.get("first_seen") or now) + EXPIRY if job.get("recurring") else None,
            "stopping": bool(job.get("stopping"))}


def view(session, now):
    """The session's jobs as panel rows, soonest first. Rows without a countdown go last."""
    rows = [_row(j, now) for j in (session.get("schedules") or {}).values()]
    return sorted(rows, key=lambda r: (r["next"] is None, r["next"] or 0))
