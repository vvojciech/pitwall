"""Agent races: one task, several agents, each in its own git worktree. Compare, apply one, clean up."""
from __future__ import annotations

import os
import subprocess

from pitwall.snapshot import _git, _write_tree, exclude

WORKTREES = ".claude/worktrees"


def create(repo, race_id, agents):
    """Make one worktree and branch per agent, from HEAD. Returns the entries."""
    exclude(repo, f"/{WORKTREES}/")
    base = _git(repo, "rev-parse", "HEAD^{tree}").strip()
    entries = []
    for n, agent in enumerate(agents, 1):
        name = f"race-{race_id}-{n}-{agent}"
        worktree = os.path.join(repo, WORKTREES, name)
        _git(repo, "worktree", "add", "-q", "-b", f"pitwall-{name}", worktree, "HEAD")
        entries.append({"agent": agent, "worktree": worktree, "branch": f"pitwall-{name}", "base": base})
    return entries


def stat(entry):
    """Files, added and removed lines since the race started, new files included."""
    out = _git(entry["worktree"], "diff", "--numstat", entry["base"], _write_tree(entry["worktree"]))
    files = added = removed = 0
    for line in out.splitlines():
        a, r, _ = line.split("\t", 2)
        files += 1
        added += int(a) if a.isdigit() else 0
        removed += int(r) if r.isdigit() else 0
    return {"files": files, "added": added, "removed": removed}


def diff(entry):
    return _git(entry["worktree"], "diff", entry["base"], _write_tree(entry["worktree"]))


def apply(repo, entry):
    """Apply an agent's changes to the repo's work tree, unstaged. Returns an error, or None."""
    patch = _git(entry["worktree"], "diff", "--binary", entry["base"], _write_tree(entry["worktree"]))
    if not patch.strip():
        return "That agent changed nothing."
    result = subprocess.run(["git", "-C", repo, "apply", "--whitespace=nowarn"], input=patch,
                            capture_output=True, text=True)
    return None if result.returncode == 0 else (result.stderr.strip() or "git apply failed")


def clean_up(repo, entries):
    for e in entries:
        subprocess.run(["git", "-C", repo, "worktree", "remove", "--force", e["worktree"]], capture_output=True)
        subprocess.run(["git", "-C", repo, "branch", "-D", e["branch"]], capture_output=True)
