"""Shared memory: each agent starts with what the other agent saved.

Codex gets the Claude Code notes for the project. Claude Code gets the Codex memories, which
Codex keeps for all projects together. Turn it off with PITWALL_SHARED_MEMORY=0.
"""
from __future__ import annotations

import re
from pathlib import Path

MAX_CHARS = 8000
WARNING = ("They can be out of date. Check a note against the code before you rely on it. "
           "Pitwall shares these notes; nothing leaves this Mac.")


def slug(path):
    """The folder name Claude Code uses for a project under ~/.claude/projects."""
    return re.sub(r"[^A-Za-z0-9]", "-", str(path))


def _cut(text):
    return text if len(text) <= MAX_CHARS else text[:MAX_CHARS] + "\n[cut: more notes are in the folder above]"


def claude_notes(cwd, home):
    """MEMORY.md of the nearest project folder at or above cwd, with its folder."""
    path = Path(cwd)
    for folder in (path, *path.parents):
        memory = home / ".claude/projects" / slug(folder) / "memory"
        if (memory / "MEMORY.md").is_file():
            return memory, (memory / "MEMORY.md").read_text(errors="replace")
    return None, ""


def context_for(agent, cwd, home):
    """The text to add to a new session, or None when the other agent saved nothing."""
    if agent == "codex":
        folder, index = claude_notes(cwd, home)
        if not index.strip():
            return None
        return _cut(f"Claude Code saved these notes about this project. {WARNING}\n"
                    f"Each line links to a file in {folder}. Read a file when its line is relevant.\n\n{index}")
    if agent == "claude":
        files = sorted((home / ".codex/memories").glob("*.md"))
        parts = [f"## {f.stem}\n{f.read_text(errors='replace').strip()}" for f in files]
        body = "\n\n".join(p for p in parts if p.strip())
        if not body:
            return None
        return _cut(f"Codex saved these memories (for all projects, not only this one). {WARNING}\n\n{body}")
    return None
