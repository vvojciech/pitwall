"""Turn a Claude Code or Codex hook payload into a Pitwall event."""
from __future__ import annotations

import os
import re

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


PASTED = re.compile(r"<pasted_content[^>]*>(.*?)</pasted_content[^>]*>", re.S)  # the closing tag repeats the id
# Records that agents write as "user" messages but no person typed.
SYSTEM_TAGS = ("<task-notification", "<local-command", "<command-name", "<command-message", "<command-args",
               "<system-reminder", "<bash-input", "<bash-stdout", "<bash-stderr", "<user-prompt-submit-hook",
               "<environment_context", "<user_instructions", "<turn_aborted", "# AGENTS.md")


def prompt_text(raw):
    """What a person typed or pasted, or None for a system record.

    Claude Code wraps pasted text in <pasted_content> tags; the text inside is the prompt.
    """
    text = PASTED.sub(lambda m: m.group(1), raw or "").strip()
    return None if not text or text.startswith(SYSTEM_TAGS) else text


READ_TOOLS = {"Read", "NotebookRead"}
EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
PATCH_FILE = re.compile(r"\*\*\* (?:Update|Add|Delete) File: (.+)")


MAX_BACKGROUND = 20


def _background(task):
    """One background task, trimmed to what the panel shows."""
    out = {k: first_line(str(task.get(k) or ""), 120) for k in ("type", "status", "description")}
    if task.get("command"):
        out["command"] = first_line(str(task["command"]), 120)
    return out


def touched_files(tool, tool_input, cwd):
    """For the code map: {path, touch} for a file tool, {paths, touch} for a Codex patch, else {}."""
    tool_input = tool_input if isinstance(tool_input, dict) else {}
    if tool in READ_TOOLS or tool in EDIT_TOOLS:
        path = tool_input.get("file_path") or tool_input.get("notebook_path")
        return {"path": path, "touch": "edit" if tool in EDIT_TOOLS else "read"} if path else {}
    if tool == "apply_patch":
        text = " ".join(v for v in tool_input.values() if isinstance(v, str))
        paths = [os.path.join(cwd or "", p.strip()) for p in PATCH_FILE.findall(text)]
        return {"paths": paths, "touch": "edit"} if paths else {}
    return {}


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
        # Background-task notifications arrive as prompts too; prompt_text drops them.
        text = prompt_text(payload.get("prompt"))
        event["task"] = first_line(text) if text else None
    tool = payload.get("tool_name")
    if tool:
        event["action"] = describe(tool, payload.get("tool_input"))
        event.update(touched_files(tool, payload.get("tool_input"), event["cwd"]))
    if name == "Notification":
        event["notification_type"] = payload.get("notification_type")
        event["message"] = first_line(payload.get("message"))
    # Claude Code reports in-flight background work (shells, sub-agents, monitors) and scheduled
    # wake-ups, so "done" can be told apart from "paused while background work runs".
    if isinstance(payload.get("background_tasks"), list):
        event["background"] = [_background(t) for t in payload["background_tasks"][:MAX_BACKGROUND] if isinstance(t, dict)]
    if isinstance(payload.get("session_crons"), list):
        event["crons"] = len(payload["session_crons"])
    if name == "Stop":
        # The full reply, for review loops. Claude Code sends it; Codex may not.
        event["last_message"] = (payload.get("last_assistant_message") or "")[:20000]
    if name == "StopFailure":
        event["error"] = first_line(payload.get("error") or payload.get("message") or "Agent stopped with an error")
    return event
