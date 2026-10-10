"""Turn a Claude Code or Codex hook payload into a Pitwall event."""
from __future__ import annotations

import os

# Tool inputs that best name what a tool call does, in order of preference.
TARGET_KEYS = ("file_path", "path", "notebook_path", "command", "pattern", "url", "query", "description")


def first_line(text, limit=120):
    line = (text or "").strip().split("\n", 1)[0].strip()
    return line[:limit]


def describe(tool, tool_input):
    """Short label for a tool call, such as 'Edit app.ts' or 'Bash npm test'."""
    if not tool:
        return None
    tool_input = tool_input if isinstance(tool_input, dict) else {}
    for key in TARGET_KEYS:
        value = tool_input.get(key)
        if isinstance(value, str) and value.strip():
            if key.endswith("path"):
                value = os.path.basename(value.rstrip("/")) or value
            return f"{tool} {first_line(value, 80)}"
    return tool


def to_event(agent, name, payload, env, ts):
    """Return the event dict, or None when the agent does not run in iTerm2."""
    iterm_id = env.get("ITERM_SESSION_ID", "")
    if ":" not in iterm_id:
        return None
    event = {
        "sid": iterm_id.split(":", 1)[1],
        "agent": agent,
        "event": name,
        "ts": ts,
        "cwd": payload.get("cwd") or env.get("PWD"),
        "agent_session": payload.get("session_id"),
        "transcript": payload.get("transcript_path"),
    }
    if name == "UserPromptSubmit":
        prompt = first_line(payload.get("prompt"))
        # Claude Code submits background-task notifications as prompts; they are not a task.
        event["task"] = None if prompt.startswith("<") else prompt
    tool = payload.get("tool_name")
    if tool:
        event["action"] = describe(tool, payload.get("tool_input"))
    if name == "Notification":
        event["notification_type"] = payload.get("notification_type")
        event["message"] = first_line(payload.get("message"))
    if name == "StopFailure":
        event["error"] = first_line(payload.get("error") or payload.get("message") or "Agent stopped with an error")
    return event
