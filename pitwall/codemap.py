"""The code map: a project's folders and the files an agent touched this turn, laid out radially.

Overview shows the top two folder levels and every touched file with its folders. Files mode
also shows the other files beside the touched ones. Positions are in the unit circle.
"""
from __future__ import annotations

import math
import os
import posixpath
import re

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
OVERVIEW_DEPTH = 2
FILES_DEPTH = 3
MAX_NODES = 400


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


def build(root, files, touched, current, importers, mode="overview"):
    """The map as {nodes, edges, imports, stats}. `touched` maps absolute paths to read or edit."""
    rel = {}
    for path, kind in (touched or {}).items():
        r = os.path.relpath(path, root)
        if not r.startswith(".."):
            rel[r] = kind
    cur = current and os.path.relpath(current, root)
    files_set = set(files)
    folders = {a for f in files for a in _ancestors(f)}
    count = {}
    for f in files:
        for a in ["", *_ancestors(f)]:
            count[a] = count.get(a, 0) + 1

    hot = {f for f in rel if f in files_set} | ({cur} if cur in files_set else set())
    edited = {f for f, k in rel.items() if k == "edit" and f in files_set}
    radius_of = edited | ({cur} if cur in files_set else set())
    dependents = {d for f in radius_of for d in importers.get(f, [])} - hot
    limit = FILES_DEPTH if mode == "files" else OVERVIEW_DEPTH
    shown = {""} | {d for d in folders if _depth(d) <= limit}
    for f in hot | dependents:
        shown |= {f, *_ancestors(f)}
    if mode == "files":
        hot_folders = {posixpath.dirname(f) for f in hot}
        shown |= {f for f in files if posixpath.dirname(f) in hot_folders}
    if len(shown) > MAX_NODES:  # fold the quiet folders of a large repo
        keep = {a for f in hot | dependents for a in ["", *_ancestors(f), f]}
        shown = {n for n in shown if n in keep or _depth(n) <= 1}

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
    untested = sorted(f for f in edited if category(f) != "tests"
                      and not any(category(d) == "tests" for d in importers.get(f, [])))
    stats = {"files": len(files), "visited": len(hot), "edited": len(edited), "untested": untested}
    return {"nodes": nodes, "edges": edges, "imports": imports, "stats": stats}
