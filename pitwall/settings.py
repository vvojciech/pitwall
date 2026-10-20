"""Which optional features are on, from ~/.pitwall/settings.json. A missing key is on."""
from __future__ import annotations

import json
import os

from pitwall import config

FILE = config.HOME / "settings.json"

# (key, group, label, hint), in panel order.
FEATURES = (
    ("races", "Panel", "Agent races", ""),
    ("failed_commands", "Panel", "Failed commands", ""),
    ("map", "Panel", "Code map", ""),
    ("schedules", "Panel", "Scheduled prompts", ""),
    ("background", "Panel", "Background work", ""),
    ("ports", "Panel", "Ports", "Off stops the scan every 5 seconds."),
    ("plan_limits", "Panel", "Plan limits", ""),
    ("context_ring", "Card", "Context ring", ""),
    ("timeline", "Card", "Timeline", ""),
    ("handoff", "Card", "Hand off", ""),
    ("review_loop", "Card", "Review loop", ""),
    ("undo", "Card", "Undo and Redo", "Off stops the snapshot before each prompt."),
    ("tab_colours", "iTerm2", "Tab colours", ""),
    ("tab_badges", "iTerm2", "Tab badges", ""),
    ("shared_memory", "Agents", "Shared memory", "PITWALL_SHARED_MEMORY=0 still turns it off."),
    ("update_check", "Agents", "Check for updates", ""),
)
DEFAULTS = {key: True for key, *_ in FEATURES}
ENV_OFF = {"update_check": "PITWALL_UPDATE_CHECK"}

_cache = {}


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
    """{key: on} for every feature. Rereads the file when it changes."""
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
    """Raises ValueError for an unknown key or a value that is not true or false."""
    for key, value in changes.items():
        if key not in DEFAULTS:
            raise ValueError(f"No feature called {key}.")
        if not isinstance(value, bool):
            raise ValueError(f"{key} takes true or false.")
    path = path or FILE
    config.write_private(path, json.dumps(dict(current(path), **changes), indent=2) + "\n")
    return current(path)


def _locked(key, env):
    var = ENV_OFF.get(key)
    return f"{var}=0" if var and (os.environ if env is None else env).get(var) == "0" else None


def describe(env=None, path=None):
    values = current(path)
    return [{"key": key, "group": group, "label": label, "hint": hint,
             "on": values[key] and not _locked(key, env), "locked": _locked(key, env)}
            for key, group, label, hint in FEATURES]


def on(key, env=None, path=None):
    return current(path)[key] and not _locked(key, env)
