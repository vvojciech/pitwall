"""Read an agent's transcript as a short timeline: prompts, thinking, replies and tool calls."""
from __future__ import annotations

import json
from collections import deque
from pathlib import Path

from pitwall.events import PATCH_FILE, describe, first_line, prompt_text
from pitwall.memory import slug

AGENT_TOOLS = ("Task", "Agent")


def _item(kind, text, ts=None):
    text = first_line(text, 200)
    return {"kind": kind, "text": text, "ts": ts} if text else None


def _claude(record):
    message = record.get("message") or {}
    content, ts = message.get("content"), record.get("timestamp")
    if record["type"] == "user":
        text = isinstance(content, str) and prompt_text(content)
        if text:
            yield _item("prompt", text, ts)
        return
    for block in content if isinstance(content, list) else []:
        kind = block.get("type")
        if kind == "thinking":
            yield _item("thinking", block.get("thinking"), ts)
        elif kind == "text":
            yield _item("text", block.get("text"), ts)
        elif kind == "tool_use":
            name = block.get("name")
            yield _item("agent" if name in AGENT_TOOLS else "tool", describe(name, block.get("input")), ts)


def _codex_tool(payload):
    name = payload.get("name")
    if payload.get("type") == "custom_tool_call":
        text = payload.get("input") or ""
        match = PATCH_FILE.search(text)
        code = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("//"))
        return f"{name} {match.group(1) if match else first_line(code, 80)}".strip()
    try:
        args = json.loads(payload.get("arguments") or "{}")
    except ValueError:
        args = {}
    command = args.get("command") if isinstance(args, dict) else None
    if isinstance(command, list):
        command = command[-1] if command[:2] == ["bash", "-lc"] else " ".join(command)
    return f"{name} {first_line(command, 80)}" if command else describe(name, args)


def _codex(record):
    p, ts = record.get("payload") or {}, record.get("timestamp")
    kind = p.get("type")
    if kind == "message" and p.get("role") in ("user", "assistant"):
        text = " ".join(c.get("text", "") for c in p.get("content") or [] if isinstance(c, dict))
        if p["role"] == "user" and prompt_text(text):
            yield _item("prompt", prompt_text(text), ts)
        elif p["role"] == "assistant":
            yield _item("text", text, ts)
    elif kind == "reasoning":
        # Codex encrypts its reasoning; only a summary is readable, and it is often empty.
        yield _item("thinking", " ".join(s.get("text", "") for s in p.get("summary") or []), ts)
    elif kind in ("function_call", "custom_tool_call"):
        yield _item("tool", _codex_tool(p), ts)


def parse(lines, limit=80):
    """Timeline items from transcript lines, oldest first, at most `limit` of the newest."""
    items = deque(maxlen=limit)
    for line in lines:
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if not isinstance(record, dict):
            continue
        reader = _codex if record.get("type") == "response_item" else _claude if record.get("type") in ("user", "assistant") else None
        for item in reader(record) if reader else ():
            if item:
                items.append(item)
    return list(items)


def last_reply(lines):
    """The full text of the agent's last reply in a transcript, or ''."""
    reply = ""
    for line in lines:
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if not isinstance(r, dict):
            continue
        if r.get("type") == "assistant":
            content = (r.get("message") or {}).get("content")
            texts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"] \
                if isinstance(content, list) else []
            reply = "\n".join(texts) or reply
        elif r.get("type") == "response_item":
            p = r.get("payload") or {}
            if p.get("type") == "message" and p.get("role") == "assistant":
                reply = " ".join(c.get("text", "") for c in p.get("content") or [] if isinstance(c, dict)) or reply
    return reply


def transcript_path(s, home):
    """The transcript file of a session: from the hook payload, else from the agent's own layout."""
    if s.get("transcript") and Path(s["transcript"]).is_file():
        return Path(s["transcript"])
    sid, cwd = s.get("agent_session"), s.get("cwd")
    if not sid:
        return None
    if s["agent"] == "claude" and cwd:
        path = home / ".claude/projects" / slug(cwd) / f"{sid}.jsonl"
        return path if path.is_file() else None
    return next(iter(sorted((home / ".codex/sessions").glob(f"*/*/*/rollout-*{sid}.jsonl"))), None)


def read_last_reply(s, home):
    path = transcript_path(s, home)
    if not path:
        return ""
    with open(path, errors="replace") as f:
        return last_reply(f)


def read(s, home, limit=80):
    path = transcript_path(s, home)
    if not path:
        return []
    with open(path, errors="replace") as f:
        return parse(f, limit)
