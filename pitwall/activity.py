"""Activity per day, project and agent, read from the transcripts Claude Code and Codex keep.

Also reads the plan limits: Codex writes them into its transcripts; Claude Code passes them to
the status line, which Pitwall's status line wrapper saves to ~/.pitwall/claude-status.json.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime

from pitwall.events import prompt_text

IDLE_GAP = 300  # seconds; a longer pause between two records is not active time
EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
PATCH_FILE = re.compile(r"\*\*\* (?:Update|Add|Delete) File: (.+)")


def _when(ts):
    """(epoch seconds, local day) for an ISO timestamp, or None."""
    try:
        t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None
    return t.timestamp(), t.astimezone().date().isoformat()


def project_of(cwd):
    """The repository folder name; worktrees count toward their repository."""
    repo = (cwd or "").split("/.claude/worktrees/")[0].rstrip("/")
    return os.path.basename(repo) or "unknown"


class _Days:
    def __init__(self, agent):
        self.agent, self.rows, self.last = agent, {}, None

    def row(self, day, project):
        key = (day, project)
        if key not in self.rows:
            self.rows[key] = {"day": day, "project": project, "agent": self.agent, "active": 0, "prompts": 0,
                              "tokens": 0, "files": set(), "commands": 0}
        return self.rows[key]

    def tick(self, when, project):
        """Count the time since the previous record as active, if the pause was short."""
        if when is None:
            return None
        epoch, day = when
        if self.last is not None and 0 < epoch - self.last <= IDLE_GAP:
            self.row(day, project)["active"] += round(epoch - self.last)
        self.last = max(epoch, self.last or 0)
        return self.row(day, project)

    def result(self):
        return [dict(r, files=len(r["files"])) for r in self.rows.values()]


def _claude(records, days):
    seen = set()
    for r in records:
        if r.get("type") not in ("user", "assistant"):
            continue
        row = days.tick(_when(r.get("timestamp")), project_of(r.get("cwd")))
        message = r.get("message") or {}
        content = message.get("content")
        if row is None:
            continue
        if r["type"] == "user":
            if isinstance(content, str):
                typed = prompt_text(content) is not None
            else:
                kinds = {b.get("type") for b in content or [] if isinstance(b, dict)}
                typed = "text" in kinds and "tool_result" not in kinds
            if typed and not r.get("isMeta") and not r.get("isSidechain"):
                row["prompts"] += 1
            continue
        if message.get("id") not in seen:  # one message can be written as several records
            seen.add(message.get("id"))
            u = message.get("usage") or {}
            row["tokens"] += sum(u.get(k) or 0 for k in ("input_tokens", "cache_creation_input_tokens",
                                                        "cache_read_input_tokens", "output_tokens"))
        for b in content if isinstance(content, list) else []:
            if isinstance(b, dict) and b.get("type") == "tool_use":
                if b.get("name") == "Bash":
                    row["commands"] += 1
                elif b.get("name") in EDIT_TOOLS:
                    row["files"].add((b.get("input") or {}).get("file_path"))


def _codex(records, days):
    project, total = "unknown", 0
    for r in records:
        p = r.get("payload") or {}
        if r.get("type") == "session_meta":
            project = project_of(p.get("cwd"))
        row = days.tick(_when(r.get("timestamp")), project)
        if row is None:
            continue
        kind = p.get("type")
        if r.get("type") == "response_item" and kind == "message" and p.get("role") == "user":
            text = " ".join(c.get("text", "") for c in p.get("content") or [] if isinstance(c, dict))
            if prompt_text(text):
                row["prompts"] += 1
        elif kind in ("function_call", "custom_tool_call"):
            files = PATCH_FILE.findall(p.get("input") or "") if p.get("name") == "apply_patch" else []
            row["files"].update(files)
            row["commands"] += 0 if files else 1
        elif kind == "token_count":
            now = ((p.get("info") or {}).get("total_token_usage") or {}).get("total_tokens")
            if isinstance(now, int) and now >= total:
                row["tokens"] += now - total
                total = now


def summarize(lines, agent):
    """Rows of {day, project, agent, active, prompts, tokens, files, commands} for one transcript."""
    records = []
    for line in lines:
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if isinstance(r, dict):
            records.append(r)
    days = _Days(agent)
    (_codex if agent == "codex" else _claude)(records, days)
    return days.result()


def codex_limits(lines):
    """The newest Codex plan limits in a transcript: {five_hour, week} with used percent and reset time."""
    found = None
    for line in lines:
        if '"rate_limits"' not in line:
            continue
        try:
            limits = (json.loads(line).get("payload") or {}).get("rate_limits")
        except ValueError:
            continue
        if limits:
            found = limits
    if not found:
        return None
    pick = lambda w, default: w and {"used": w.get("used_percent"), "resets_at": w.get("resets_at"),
                                     "window": (w.get("window_minutes") or default) * 60}
    return {"five_hour": pick(found.get("primary"), 300), "week": pick(found.get("secondary"), 10080),
            "credits": found.get("credits")}
