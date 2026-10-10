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


EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"  # git's tree for "no files"


def base_tree(root, s, mode):
    """What the work is compared with: the snapshot at the last prompt, or the last commit."""
    snap = s.get("snapshots") and s["snapshots"][-1]
    if mode == "turn" and snap and snap.get("root") == root:
        return snap["tree"]
    if mode == "turn":
        return None  # no prompt seen yet in this repository: only the hooks' files count
    try:
        return snapshot._git(root, "rev-parse", "HEAD^{tree}").strip()
    except Exception:  # noqa: BLE001  a repository with no commit yet
        return EMPTY_TREE


def changes(root, base):
    """(changed paths, added lines, removed lines) from base to the work tree now, new files included."""
    if not base:
        return [], 0, 0
    out = snapshot._git(root, "diff", "--numstat", "--no-renames", base, snapshot._write_tree(root))
    paths, added, removed = [], 0, 0
    for line in out.splitlines():
        a, r, path = line.split("\t", 2)
        paths.append(path)
        added += int(a) if a.isdigit() else 0
        removed += int(r) if r.isdigit() else 0
    return paths, added, removed


def map_for(s, mode):
    root = s.get("cwd") and snapshot.repo_root(s["cwd"])
    if not root:
        return {"error": "The code map needs a git repository."}
    files = repo_files(root)
    changed, added, removed = changes(root, base_tree(root, s, mode))
    # "This turn" also counts what the hooks saw; "Uncommitted" is what git sees, nothing else.
    touched = (s.get("touched") or {}) if mode == "turn" else {}
    graph = codemap.build(root, files, touched, s.get("current"), imports.importers(root, files), changed)
    graph["stats"]["added"], graph["stats"]["removed"] = added, removed
    graph.update(project=os.path.basename(root), agent=s["agent"], state=s["state"],
                 action=s.get("action"), truncated=len(files) >= MAX_FILES)
    return graph
