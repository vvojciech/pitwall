"""Hand-off messages: one agent's work, written for another agent to pick up."""
from __future__ import annotations

import os
import shlex

MAX_DIFF = 40_000
AGENT_NAMES = {"claude": "Claude Code", "codex": "Codex"}
MODES = {
    "continue": "Continue this work where the previous agent stopped. Check the current files first, "
                "because the notes below can be behind them.",
    "review": "Review this work. Do not edit any file. List the problems by severity, with file and line, "
              "and say APPROVED or CHANGES NEEDED at the end.",
    "second": "Give a second opinion on the approach. Do not edit any file. Say what you would do "
              "differently, and why.",
}


def failure_message(f):
    return (f"This command failed in {f['cwd']} (exit {f['status']}):\n\n$ {f['command']}\n{f['output']}\n\n"
            "Find the cause and fix it.")


def build(s, mode, timeline, diff, failures):
    """The hand-off text for session s. `diff` is None when there is no snapshot."""
    parts = [f"# Hand-off from {AGENT_NAMES.get(s['agent'], s['agent'])} in {os.path.basename(s['cwd'] or '')}",
             MODES[mode], f"Project folder: {s['cwd']}", "## Task", s.get("task") or "(no prompt recorded)"]
    if timeline:
        parts += ["## Recent activity (oldest first)", "\n".join(f"- {i['kind']}: {i['text']}" for i in timeline)]
    parts.append("## What changed since the first prompt")
    if diff is None:
        parts.append("No snapshot: the project is not a git repository, or Pitwall saw no prompt. Run git status.")
    elif not diff.strip():
        parts.append("Nothing changed.")
    else:
        cut = diff if len(diff) <= MAX_DIFF else diff[:MAX_DIFF] + "\n[cut: run git diff for the rest]"
        parts.append(f"```diff\n{cut}\n```")
    if failures:
        parts += ["## Failed commands", "\n\n".join(failure_message(f) for f in failures)]
    return "\n\n".join(parts) + "\n"


def launch_command(agent, cwd, path):
    prompt = f"Read the hand-off in {path} and follow its instructions."
    return f"cd {shlex.quote(cwd)} && {agent} {shlex.quote(prompt)}"
