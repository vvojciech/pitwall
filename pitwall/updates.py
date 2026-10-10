"""Is a newer Pitwall on GitHub? And the background run of `pitwall update` that the panel starts."""
from __future__ import annotations

import subprocess
import sys

from pitwall import config

CHECK_EVERY = 6 * 3600


def _git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=60)


def check(repo):
    """{"behind": commits to pull, "latest": newest tag upstream}, or None when git cannot tell."""
    try:
        if _git(repo, "fetch", "--quiet", "--tags", "origin").returncode != 0:
            return None
        count = _git(repo, "rev-list", "--count", "HEAD..@{u}")
        if count.returncode != 0:
            return None
        tag = _git(repo, "describe", "--tags", "--abbrev=0", "@{u}")
        return {"behind": int(count.stdout.strip()), "latest": tag.stdout.strip() if tag.returncode == 0 else None}
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None


def start_update():
    """Run `pitwall update` apart from the service: the update restarts the service, which ends this process."""
    log = open(config.HOME / "update.log", "w")
    subprocess.Popen([sys.executable, str(config.REPO / "bin" / "pitwall"), "update"], cwd=str(config.REPO),
                     stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
