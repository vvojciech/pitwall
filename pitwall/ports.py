"""Listening TCP ports that belong to projects, read with lsof."""
from __future__ import annotations

import os
import re
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


IN_USE = re.compile(r"EADDRINUSE|address already in use|\bis (?:already )?in use", re.I)
PORT_WORD = re.compile(r"\bport\s+(\d{2,5})\b", re.I)
PORT_COLON = re.compile(r":(\d{2,5})\b")


PORT_ARG = re.compile(r"(?:--port[= ]|-p |\bPORT=)(\d{2,5})\b|(?:^|\s)(\d{4,5})(?=\s|$)")


def busy_port(output, command=""):
    """The port from an 'address already in use' error, or None.

    Some errors (Python's) do not name the port; then the port comes from the command.
    """
    in_use = False
    for line in output.splitlines():
        if not IN_USE.search(line):
            continue
        in_use = True
        word = PORT_WORD.search(line)
        if word:
            return int(word.group(1))
        colons = PORT_COLON.findall(line)
        if colons:
            return int(colons[-1])
    arg = in_use and PORT_ARG.search(command)
    return int(arg.group(1) or arg.group(2)) if arg else None


def holders(lsof_text, port):
    """The processes listening on port, from `lsof -Fpcn` output."""
    return [{"pid": pid, "command": (f.get("c") or ["?"])[0]} for pid, f in _records(lsof_text)
            if any(n.rsplit(":", 1)[-1] == str(port) for n in f.get("n", []))]


def holder_of(port):
    text = subprocess.run(["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-Fpcn"],
                          capture_output=True, text=True).stdout
    found = holders(text, port)
    if not found:
        return None
    holder = found[0]
    cwd = parse_cwds(subprocess.run(["lsof", "-nP", "-a", "-d", "cwd", "-p", str(holder["pid"]), "-Fpn"],
                                    capture_output=True, text=True).stdout).get(holder["pid"], "")
    return dict(holder, port=port, project=project_name(cwd) if cwd not in ("", "/") else "")


def scan(home):
    run = lambda *a: subprocess.run(["lsof", "-nP", *a], capture_output=True, text=True).stdout
    text = run("-iTCP", "-sTCP:LISTEN", "-Fpcn")
    pids = [str(pid) for pid, _ in _records(text)]
    cwds = parse_cwds(run("-a", "-d", "cwd", "-p", ",".join(pids), "-Fpn")) if pids else {}
    return listeners(text, cwds, home, skip_pid=os.getpid())
