"""Agent state per iTerm2 session, driven by hook events."""
from __future__ import annotations

from pitwall import schedules

MAX_SNAPSHOTS = 20
WAITING = ("waiting_permission", "waiting_input")


AGENTS = ("claude", "codex")
MISSING_SCANS = 2  # iTerm2's layout data can miss a pane for a moment; wait for a second scan


def agent_of(job):
    """'claude', 'codex' or None for a pane's job name, such as 'claude' or 'codex-x86'."""
    job = (job or "").rsplit("/", 1)[-1].lower()
    return next((a for a in AGENTS if job.startswith(a)), None)


def layout_order(cards, windows):
    """Sort cards as iTerm2 shows them: window by window, tab by tab, pane by pane.

    `windows` is a list of windows, each a list of tabs, each a list of session ids.
    """
    rank = {}
    for window in windows:
        for tab in window:
            for sid in tab:
                rank.setdefault(sid, len(rank))
    return sorted(cards, key=lambda c: rank.get(c["sid"], len(rank)))


def is_shell(job):
    """True when the pane is back at a shell prompt. Other jobs, such as node, can be an agent."""
    return (job or "").rsplit("/", 1)[-1].lstrip("-") in ("zsh", "bash", "fish", "sh", "login", "nu")


def discover(sessions, panes, ts):
    """Sync the cards with a scan of all panes. Returns the sids of new cards."""
    added = []
    seen = {p["sid"] for p in panes}
    for p in panes:
        agent = agent_of(p.get("job"))
        if agent and p["sid"] not in sessions:
            sessions[p["sid"]] = new_session({"sid": p["sid"], "agent": agent, "cwd": p.get("cwd"), "ts": ts})
            added.append(p["sid"])
        elif p["sid"] in sessions and is_shell(p.get("job")):
            del sessions[p["sid"]]  # the agent quit without a SessionEnd
    for sid in [sid for sid in sessions if sid not in seen]:
        sessions[sid]["missing"] = sessions[sid].get("missing", 0) + 1
        if sessions[sid]["missing"] >= MISSING_SCANS:
            del sessions[sid]
    for sid in seen & set(sessions):
        sessions[sid]["missing"] = 0
    return added


def rebound(event, owners, live):
    """Point an event from a tab id iTerm2 no longer has at the live tab running the same agent.

    iTerm2 gives every tab a new id when it restarts and keeps the running jobs, so an agent started
    before the restart still reports its old id. `owners` maps each live pane's job pid to its id.
    """
    if not live or event.get("sid") in live or not event.get("agent_pid"):
        return event
    sid = owners.get(event["agent_pid"])
    return dict(event, sid=sid) if sid else event


def pane_owners(panes):
    """{job pid: pane id} of the live panes, for rebound."""
    return {p["job_pid"]: p["sid"] for p in panes if p.get("job_pid")}


def new_session(event):
    return {
        "sid": event["sid"],
        "agent": event["agent"],
        "agent_session": event.get("agent_session"),
        "cwd": event.get("cwd"),
        "state": "idle",
        "task": None,
        "started": None,
        "finished": None,
        "action": None,
        "permission": None,
        "questions": None,
        "error": None,
        "updated": event["ts"],
        "snapshots": [],
        "redo": None,
    }


def apply(sessions, event):
    """Apply one event to the sessions dict. Returns the changed session, or None."""
    sid, name = event["sid"], event["event"]
    if name == "SessionEnd":
        sessions.pop(sid, None)
        return None

    s = sessions.get(sid)
    if s is None or (name == "SessionStart" and s["agent"] != event["agent"]):
        kept = s and s.get("name")  # a name belongs to the pane, not to one agent run
        s = sessions[sid] = new_session(event)
        s["name"] = kept
    s["updated"] = event["ts"]
    s["cwd"] = event.get("cwd") or s["cwd"]
    s["agent_session"] = event.get("agent_session") or s["agent_session"]
    s["transcript"] = event.get("transcript") or s.get("transcript")
    if "background" in event:  # only some events report it; keep the last report until the next
        s["background"] = event["background"]
    schedules.apply(s, event)

    # Questions from AskUserQuestion stay up while Claude waits for the answer, and go with the next event.
    if name not in ("PermissionRequest", "Notification"):
        s["questions"] = event.get("questions") if name == "PreToolUse" else None

    if name == "UserPromptSubmit":
        s.update(state="working", task=event.get("task") or s["task"], started=event["ts"],
                 finished=None, action=None, permission=None, error=None, redo=None, touched={}, current=None)
        if event.get("snapshot"):
            s["snapshots"].append(dict(event["snapshot"], task=s["task"], ts=event["ts"]))
            del s["snapshots"][:-MAX_SNAPSHOTS]
    elif name in ("PreToolUse", "PostToolUse", "PostToolUseFailure", "SubagentStart", "SubagentStop"):
        if s["state"] != "done":  # a late sub-agent event must not revive a finished turn
            s.update(state="working", permission=None)
        s["action"] = event.get("action") or s["action"]
        touched = s.setdefault("touched", {})
        paths = event.get("paths") or ([event["path"]] if event.get("path") else [])
        for path in paths if event.get("touch") in ("read", "edit") else []:
            if event["touch"] == "edit" or path not in touched:  # an edit outranks a read
                touched[path] = event["touch"]
            s["current"] = path
    elif name == "PermissionRequest" and (event.get("questions") or s.get("questions")):
        s.update(state="waiting_input", permission=None, questions=event.get("questions") or s["questions"])
    elif name == "PermissionRequest":
        s.update(state="waiting_permission", permission=event.get("action"))
    elif name == "Notification":
        kind = event.get("notification_type") or ""
        message = (event.get("message") or "").lower()
        if s.get("questions"):
            s["state"] = "waiting_input"
        elif kind == "permission_prompt" or "permission" in message:
            s["state"] = "waiting_permission"
        elif s["state"] not in ("done", "idle", "failed"):
            s["state"] = "waiting_input"
    elif name == "Stop":
        s.update(state="done", finished=event["ts"], permission=None)
    elif name == "StopFailure":
        s.update(state="failed", finished=event["ts"], permission=None, error=event.get("error"))
    elif name == "Interrupt":
        s.update(state="idle", permission=None)
    return s
