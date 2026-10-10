"""Listening TCP ports that belong to projects, read with lsof."""
from __future__ import annotations

import os
import subprocess


def _records(text):
    """lsof -F output as a list of (pid, {field: [values]})."""
    out, pid, fields = [], None, {}
    for line in text.splitlines():
        if not line:
            continue
        key, value = line[0], line[1:]
        if key == "p":
            if pid is not None:
                out.append((pid, fields))
            pid, fields = int(value), {}
        else:
            fields.setdefault(key, []).append(value)
    if pid is not None:
        out.append((pid, fields))
    return out


def parse_cwds(text):
    return {pid: f["n"][0] for pid, f in _records(text) if f.get("n")}


EPHEMERAL = 49152  # the OS hands out ports from here up; they are inspectors and helpers, not servers


def project_name(cwd):
    """'shop', or 'shop › feature' for a worktree under .claude/worktrees."""
    repo, sep, rest = cwd.partition("/.claude/worktrees/")
    return f"{os.path.basename(repo)} › {rest.split('/')[0]}" if sep else os.path.basename(cwd)


def listeners(lsof_text, cwds, home, skip_pid=None):
    """One entry per (pid, port) for project processes: run in a folder under home, not in ~/Library."""
    found, home = [], home.rstrip("/")
    for pid, f in _records(lsof_text):
        cwd = cwds.get(pid, "")
        if pid == skip_pid or not cwd.startswith(home + "/") or cwd.startswith(home + "/Library/"):
            continue  # system services run in /, app helpers in ~/Library
        ports = sorted({int(n.rsplit(":", 1)[1]) for n in f.get("n", []) if n.rsplit(":", 1)[-1].isdigit()})
        for port in (p for p in ports if p < EPHEMERAL):
            found.append({"pid": pid, "port": port, "command": (f.get("c") or ["?"])[0], "cwd": cwd,
                          "project": project_name(cwd)})
    return sorted(found, key=lambda p: p["port"])


def scan(home):
    run = lambda *a: subprocess.run(["lsof", "-nP", *a], capture_output=True, text=True).stdout
    text = run("-iTCP", "-sTCP:LISTEN", "-Fpcn")
    pids = [str(pid) for pid, _ in _records(text)]
    cwds = parse_cwds(run("-a", "-d", "cwd", "-p", ",".join(pids), "-Fpn")) if pids else {}
    return listeners(text, cwds, home, skip_pid=os.getpid())
