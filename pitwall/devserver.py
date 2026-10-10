"""Recognise a dev server command, so Pitwall can run it in its own tab."""
from __future__ import annotations

import re

_PM = r"(?:npm|pnpm|yarn|bun)(?: run)? (?:dev|start|serve|preview)"
_NPX = r"(?:npx |pnpm exec |bunx )?(?:next|vite|astro|nuxt|remix|vinext|wrangler) dev"
_OTHER = r"vite|rails s(?:erver)?|bin/dev|python3? manage\.py runserver|make (?:dev|serve|run)|hugo server|jekyll serve"
DEV = re.compile(rf"^(?:cd [^&;|]+&& *)?(?:{_PM}|{_NPX}|{_OTHER})(?: +-[\w-]+(?:[ =][\w./:-]+)?)*\s*&?\s*$")


def is_dev_server(command):
    """True for one dev server command, optionally after a cd. Chains and `-- --help` do not count."""
    command = (command or "").strip()
    return bool(DEV.match(command)) and "--help" not in command
