"""Agent state per iTerm2 session, driven by hook events."""
from __future__ import annotations

MAX_SNAPSHOTS = 20
WAITING = ("waiting_permission", "waiting_input")


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
        s = sessions[sid] = new_session(event)
    s["updated"] = event["ts"]
    s["cwd"] = event.get("cwd") or s["cwd"]
    s["agent_session"] = event.get("agent_session") or s["agent_session"]

    if name == "UserPromptSubmit":
        s.update(state="working", task=event.get("task") or s["task"], started=event["ts"],
                 finished=None, action=None, permission=None, error=None, redo=None)
        if event.get("snapshot"):
            s["snapshots"].append(dict(event["snapshot"], task=s["task"], ts=event["ts"]))
            del s["snapshots"][:-MAX_SNAPSHOTS]
    elif name in ("PreToolUse", "PostToolUse", "PostToolUseFailure", "SubagentStart", "SubagentStop"):
        if s["state"] != "done":  # a late sub-agent event must not revive a finished turn
            s.update(state="working", permission=None)
        s["action"] = event.get("action") or s["action"]
    elif name == "PermissionRequest":
        s.update(state="waiting_permission", permission=event.get("action"))
    elif name == "Notification":
        kind = event.get("notification_type") or ""
        message = (event.get("message") or "").lower()
        if kind == "permission_prompt" or "permission" in message:
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
