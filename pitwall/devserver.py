"""Recognise a dev server command, so Pitwall can run it in its own tab."""
from __future__ import annotations

import os
import re
from pathlib import Path

from pitwall import config
from pitwall.snapshot import exclude, repo_root

_PM = r"(?:npm|pnpm|yarn|bun)(?: run)? (?:dev|start|serve|preview)"
_NPX = r"(?:npx |pnpm exec |bunx )?(?:next|vite|astro|nuxt|remix|vinext|wrangler) dev"
_OTHER = r"vite|rails s(?:erver)?|bin/dev|python3? manage\.py runserver|make (?:dev|serve|run)|hugo server|jekyll serve"
DEV = re.compile(rf"^(?:cd [^&;|]+&& *)?(?:{_PM}|{_NPX}|{_OTHER})(?: +-[\w-]+(?:[ =][\w./:-]+)?)*\s*&?\s*$")


def is_dev_server(command):
    """True for one dev server command, optionally after a cd. Chains and `-- --help` do not count."""
    command = (command or "").strip()
    return bool(DEV.match(command)) and "--help" not in command


def log_path(cwd, stamp):
    """Where a dev server's output goes: .pitwall/ inside the project, hidden from git.

    Claude Code reads files inside the project without asking, so it can follow the log.
    Outside a git repository the log goes to ~/.pitwall/logs.
    """
    name = f"dev-{os.path.basename(cwd.rstrip('/'))}-{stamp}.log"
    root = repo_root(cwd)
    if not root:
        folder = config.HOME / "logs"
    else:
        exclude(root, "/.pitwall/")
        folder = Path(root) / ".pitwall"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / name
