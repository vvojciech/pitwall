"""The code map: the files an agent works on, laid out radially around the project root.

Only the work is drawn: files read, edited or changed, the folders on their paths, and the files
that import an edit. Positions are in the unit circle.
"""
from __future__ import annotations

import math
import os
import posixpath
import re

from pitwall.imports import JS

CATEGORIES = (
    ("tests", {"test", "tests", "__tests__", "spec", "specs", "e2e", "cypress", "playwright"}),
    ("database", {"migrations", "migration", "db", "database", "prisma", "supabase", "schema", "sql", "models"}),
    ("backend", {"api", "server", "routes", "functions", "workers", "worker", "handlers", "services", "backend"}),
    ("frontend", {"components", "app", "pages", "ui", "views", "web", "styles", "frontend", "client", "hooks",
                  "layouts", "src-tauri"}),
    ("assets", {"public", "static", "assets", "images", "img", "fonts", "media"}),
    ("config", {"config", "scripts", ".github", "infra", "docker", "deploy", "bin", "tools", ".claude"}),
    ("docs", {"docs", "doc", "documentation"}),
)
TEST_FILE = re.compile(r"(\.|_)(test|spec)\.\w+$|^test_.+\.py$")
MAX_NODES = 200  # files; a sweeping change (a rename across the repo) is cut to keep the map legible
CODE = (*JS, ".py")  # files that tests import; only these can be "not reached by a test"


def category(path, is_file=True):
    name = posixpath.basename(path)
    if is_file and TEST_FILE.search(name):
        return "tests"
    folders = path.split("/")[:-1] if is_file else path.split("/")
    for segment in reversed(folders):
        for cat, names in CATEGORIES:
            if segment.lower() in names:
                return cat
    return "code"


def _ancestors(path):
    parts = path.split("/")
    return ["/".join(parts[:i]) for i in range(1, len(parts))]


def _depth(path):
    return 0 if path == "" else path.count("/") + 1


def build(root, files, touched, current, importers, changed=()):
    """The map of the work: touched and changed files, the folders on their paths, and dependents.

    `touched` maps absolute paths to read or edit (from the agent's hooks). `changed` lists repo
    paths that git sees as changed, so edits made through shell commands show up too.
    """
    rel = {}
    for path, kind in (touched or {}).items():
        r = os.path.relpath(path, root)
        if not r.startswith(".."):
            rel[r] = kind
    opened = set(rel)
    for path in changed:
        rel[path] = "edit"  # a change on disk is an edit, whatever the hooks saw
    cur = current and os.path.relpath(current, root)
    files_set = set(files) | set(changed)  # a deleted file is a change too
    count = {}
    for f in files:
        for a in ["", *_ancestors(f)]:
            count[a] = count.get(a, 0) + 1

    hot = {f for f in rel if f in files_set} | ({cur} if cur in files_set else set())
    edited = {f for f, k in rel.items() if k == "edit" and f in files_set}
    radius_of = edited | ({cur} if cur in files_set else set())
    dependents = {d for f in radius_of for d in importers.get(f, [])} - hot
    shown = {""}
    for f in sorted(hot | dependents)[:MAX_NODES]:
        shown |= {f, *_ancestors(f)}

    children = {}
    for n in sorted(shown - {""}, key=lambda p: (p in files_set, p.lower())):
        children.setdefault(posixpath.dirname(n), []).append(n)
    weight = {}

    def leaves(n):
        weight[n] = sum(leaves(c) for c in children.get(n, [])) or 1
        return weight[n]

    leaves("")
    max_depth = max(_depth(n) for n in shown) or 1
    pos = {"": (0.0, 0.0)}

    def place(n, a0, a1):
        start = a0
        for c in children.get(n, []):
            span = (a1 - a0) * weight[c] / weight[n]
            angle, r = start + span / 2, _depth(c) / max_depth
            pos[c] = (round(r * math.cos(angle), 4), round(r * math.sin(angle), 4))
            place(c, start, start + span)
            start += span

    place("", -math.pi / 2, 3 * math.pi / 2)
    nodes = [{"id": n, "name": posixpath.basename(n) or posixpath.basename(root.rstrip("/")),
              "kind": "root" if n == "" else "file" if n in files_set else "folder",
              "cat": "root" if n == "" else category(n, n in files_set), "depth": _depth(n),
              "count": count.get(n, 0), "x": pos[n][0], "y": pos[n][1], "touch": rel.get(n),
              "current": n == cur, "dependent": n in dependents} for n in sorted(shown)]
    edges = [{"from": posixpath.dirname(n), "to": n} for n in sorted(shown - {""})]
    imports = [{"from": d, "to": f} for f in sorted(radius_of) for d in importers.get(f, []) if d in shown]
    untested = sorted(f for f in edited if f.endswith(CODE) and category(f) != "tests"
                      and not any(category(d) == "tests" for d in importers.get(f, [])))
    reads = {f for f in hot if rel.get(f) == "read"}
    visited = {f for f in hot if f in opened}  # files the agent itself opened, read or edited
    stats = {"files": len(files), "visited": len(visited), "read": len(reads), "edited": len(edited),
             "untested": untested}
    return {"nodes": nodes, "edges": edges, "imports": imports, "stats": stats}
