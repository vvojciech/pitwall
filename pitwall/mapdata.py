"""Collects the code map for one agent: repository files, imports and this turn's line counts."""
from __future__ import annotations

import os
import time

from pitwall import codemap, imports, snapshot

FILES_TTL = 15  # seconds; the file list changes rarely, the touched files change every second
MAX_FILES = 20_000
_files = {}  # root -> (time, files)


def repo_files(root):
    hit = _files.get(root)
    if hit and time.time() - hit[0] < FILES_TTL:
        return hit[1]
    out = snapshot._git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    files = sorted({f for f in out.split("\0") if f})[:MAX_FILES]
    _files[root] = (time.time(), files)
    return files


def turn_lines(root, s):
    """(added, removed) since the agent's last prompt, from its snapshot."""
    snap = s.get("snapshots") and s["snapshots"][-1]
    if not snap or snap.get("root") != root:
        return 0, 0
    out = snapshot._git(root, "diff", "--numstat", snap["tree"], snapshot._write_tree(root))
    added = removed = 0
    for line in out.splitlines():
        a, r, _ = line.split("\t", 2)
        added += int(a) if a.isdigit() else 0
        removed += int(r) if r.isdigit() else 0
    return added, removed


def map_for(s, mode):
    root = s.get("cwd") and snapshot.repo_root(s["cwd"])
    if not root:
        return {"error": "The code map needs a git repository."}
    files = repo_files(root)
    graph = codemap.build(root, files, s.get("touched") or {}, s.get("current"),
                          imports.importers(root, files), mode)
    graph["stats"]["added"], graph["stats"]["removed"] = turn_lines(root, s)
    graph.update(project=os.path.basename(root), agent=s["agent"], state=s["state"],
                 action=s.get("action"), truncated=len(files) >= MAX_FILES)
    return graph
