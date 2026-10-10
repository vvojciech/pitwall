"""Snapshot a git work tree before each agent turn, and restore it.

A snapshot is a tree object only: no commit, branch, stash entry or ref.
The real index is never touched; every step uses a temporary index.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile

# ponytail: unreferenced trees survive `git gc` for its prune window (two weeks by default).
# Add refs under refs/pitwall/ if older turns must stay undoable.


def _git(root, *args, env=None, stdin=None):
    return subprocess.run(["git", "-C", root, *args], check=True, capture_output=True,
                          text=True, env=env, input=stdin).stdout


def _temp_index(root):
    """A copy of the real index, so `git add -A` reuses its stat cache and stays fast."""
    fd, path = tempfile.mkstemp(prefix="pitwall-index-")
    os.close(fd)
    real = os.path.join(root, _git(root, "rev-parse", "--git-path", "index").strip())
    if os.path.exists(real):
        shutil.copyfile(real, path)
    else:
        os.remove(path)
    return path, dict(os.environ, GIT_INDEX_FILE=path)


def _write_tree(root):
    index, env = _temp_index(root)
    try:
        _git(root, "add", "-A", env=env)
        return _git(root, "write-tree", env=env).strip()
    finally:
        if os.path.exists(index):
            os.remove(index)


def take(cwd):
    """Snapshot the work tree that holds cwd. Returns {root, tree}, or None outside git."""
    try:
        root = _git(cwd, "rev-parse", "--show-toplevel").strip()
        return {"root": root, "tree": _write_tree(root)}
    except (subprocess.CalledProcessError, OSError):
        return None


def _diff(root, tree, current):
    out = _git(root, "diff-tree", "-r", "-z", "--no-renames", "--name-status", tree, current)
    parts = out.split("\0")
    for status, path in zip(parts[0::2], parts[1::2]):
        yield ("delete" if status == "A" else "restore"), path


def preview(root, tree):
    """List what a restore would change, as (action, path) pairs."""
    return list(_diff(root, tree, _write_tree(root)))


def diff(root, tree):
    """The patch from the snapshot to the work tree now, new untracked files included."""
    current = _write_tree(root)
    return _git(root, "diff", "--stat", tree, current) + "\n" + _git(root, "diff", tree, current)


def restore(root, tree):
    """Put the work tree back to the snapshot. Returns a snapshot of the state before it."""
    current = _write_tree(root)
    changes = list(_diff(root, tree, current))
    restore_paths = [p for action, p in changes if action == "restore"]
    if restore_paths:
        index, env = _temp_index(root)
        try:
            _git(root, "read-tree", tree, env=env)
            _git(root, "checkout-index", "-f", "-z", "--stdin", env=env, stdin="\0".join(restore_paths))
        finally:
            if os.path.exists(index):
                os.remove(index)
    for action, path in changes:
        if action == "delete":
            full = os.path.join(root, path)
            if os.path.lexists(full):
                os.remove(full)
            _remove_empty_dirs(root, os.path.dirname(full))
    return {"root": root, "tree": current}


def _remove_empty_dirs(root, folder):
    while os.path.abspath(folder) != os.path.abspath(root):
        try:
            os.rmdir(folder)
        except OSError:
            return
        folder = os.path.dirname(folder)
