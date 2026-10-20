"""Which optional features are on. The hook, the service and the panel share ~/.pitwall/settings.json.

Every feature is on until the user turns it off, so a missing file means the full Pitwall.
"""
from __future__ import annotations

import json
import os

from pitwall import config

FILE = config.HOME / "settings.json"

# (key, group, label, hint). The order here is the order in the panel.
FEATURES = (
    ("races", "Panel", "Agent races", "The race button and the races list."),
    ("failed_commands", "Panel", "Failed commands", "Catch commands that fail in shell tabs."),
    ("map", "Panel", "Code map", "The map of the active tab's work."),
    ("schedules", "Panel", "Scheduled prompts", "Loops, repeating jobs and reminders."),
    ("background", "Panel", "Background work", "Shells, sub-agents and monitors on each card."),
    ("ports", "Panel", "Ports", "Listening dev servers. Off stops the scan every 5 seconds."),
    ("plan_limits", "Panel", "Plan limits", "The limit bars at the bottom."),
    ("context_ring", "Card", "Context ring", "How full each agent's context window is."),
    ("timeline", "Card", "Timeline", ""),
    ("handoff", "Card", "Hand off", ""),
    ("review_loop", "Card", "Review loop", ""),
    ("undo", "Card", "Undo and Redo", "Off stops the snapshot before each prompt."),
    ("tab_colours", "iTerm2", "Tab colours", "Amber when waiting, green when done, red when failed."),
    ("tab_badges", "iTerm2", "Tab badges", "\"Needs you\" and \"Waiting\" on the pane."),
    ("shared_memory", "Agents", "Shared memory",
     "Claude Code and Codex start with each other's notes. PITWALL_SHARED_MEMORY=0 still turns it off."),
    ("update_check", "Agents", "Check for updates", "A git fetch from GitHub every 6 hours."),
)
DEFAULTS = {key: True for key, *_ in FEATURES}
# Settings an environment variable of the service forces off.
ENV_OFF = {"update_check": "PITWALL_UPDATE_CHECK"}

_cache = {}  # path -> ((mtime, size), values)


def _read(path):
    try:
        data = json.loads(path.read_text())
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        print(f"pitwall: {path} is not valid JSON, using the defaults: {e}", flush=True)
        return {}
    return data if isinstance(data, dict) else {}


def current(path=None):
    """{key: on} for every feature. Rereads the file only when it changed."""
    path = path or FILE
    try:
        st = path.stat()
        mtime = (st.st_mtime_ns, st.st_size)
    except OSError:
        mtime = None
    cached = _cache.get(path)
    if cached and cached[0] == mtime:
        return dict(cached[1])
    saved = _read(path) if mtime is not None else {}
    values = {k: saved[k] if isinstance(saved.get(k), bool) else default for k, default in DEFAULTS.items()}
    _cache[path] = (mtime, values)
    return dict(values)


def update(changes, path=None):
    """Turn features on or off. Raises ValueError for an unknown key or a value that is not true or false."""
    if not isinstance(changes, dict):
        raise ValueError("Send an object of feature names and true or false.")
    for key, value in changes.items():
        if key not in DEFAULTS:
            raise ValueError(f"No feature called {key}.")
        if not isinstance(value, bool):
            raise ValueError(f"{key} takes true or false.")
    path = path or FILE
    values = dict(current(path), **changes)
    text = json.dumps(values, indent=2) + "\n"
    config.write_private(path, text)
    return current(path)


def describe(env=None, path=None):
    """The features for the panel, with their state and what forces one off."""
    env = os.environ if env is None else env
    values = current(path)
    out = []
    for key, group, label, hint in FEATURES:
        var = ENV_OFF.get(key)
        locked = f"{var}=0" if var and env.get(var) == "0" else None
        out.append({"key": key, "group": group, "label": label, "hint": hint,
                    "on": values[key] and not locked, "locked": locked})
    return out


def on(key, env=None, path=None):
    """Is a feature on, after the environment of this process has had its say."""
    env = os.environ if env is None else env
    var = ENV_OFF.get(key)
    return current(path)[key] and not (var and env.get(var) == "0")
