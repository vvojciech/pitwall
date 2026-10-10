"""Paths that the hook, the daemon and the installer share."""
from __future__ import annotations

import json
import os
from pathlib import Path

HOME = Path(os.environ.get("PITWALL_HOME", Path.home() / ".pitwall"))
DAEMON_FILE = HOME / "daemon.json"  # port and token of the running daemon
STATE_FILE = HOME / "state.json"
LOG_FILE = HOME / "daemon.log"
VENV = HOME / "venv"
REPO = Path(__file__).resolve().parent.parent


def read_daemon():
    try:
        return json.loads(DAEMON_FILE.read_text())
    except (OSError, ValueError):
        return None


def write_private(path, text):
    """Write a file that only this user can read."""
    HOME.mkdir(mode=0o700, parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(text)
    os.replace(tmp, path)
