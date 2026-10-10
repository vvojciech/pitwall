"""Install, remove and check Pitwall: agent hooks, the daemon venv and its LaunchAgent."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from pitwall import config

LABEL = "com.vvojciech.pitwall"
PLIST = Path.home() / "Library/LaunchAgents" / f"{LABEL}.plist"
CLAUDE = Path.home() / ".claude/settings.json"
CODEX = Path.home() / ".codex/hooks.json"
CLAUDE_EVENTS = ("SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "PostToolUseFailure",
                 "PermissionRequest", "Notification", "Stop", "StopFailure", "SessionEnd")
CODEX_EVENTS = ("SessionStart", "UserPromptSubmit", "PreToolUse", "PermissionRequest", "PostToolUse",
                "Stop", "Interrupt")
MARK = "/bin/pitwall\" hook "


def hook_command(agent, event):
    return f'python3 "{config.REPO}/bin/pitwall" hook {agent} {event}'


def is_ours(entry):
    return any(MARK in h.get("command", "") for h in entry.get("hooks", []))


def edit_hooks(path, agent, events, add):
    """Add or remove Pitwall's hooks in one agent's settings file. Keeps a backup."""
    if not path.parent.exists():
        return False
    data = json.loads(path.read_text()) if path.exists() else {}
    hooks = data.setdefault("hooks", {})
    for event in set(hooks) | set(events):
        entries = [e for e in hooks.get(event, []) if not is_ours(e)]
        if add and event in events:
            timeout = 3 if (agent, event) == ("codex", "Interrupt") else 10  # Codex caps Interrupt hooks at 3 s
            entries.append({"hooks": [{"type": "command", "command": hook_command(agent, event), "timeout": timeout}]})
        if entries:
            hooks[event] = entries
        else:
            hooks.pop(event, None)
    if not hooks:
        data.pop("hooks")
    _save(path, data)
    return True


def _save(path, data):
    """Write a settings file only when it changes, and keep a backup of the old one."""
    text = json.dumps(data, indent=2) + "\n"
    if path.exists():
        if path.read_text() == text:
            return
        shutil.copyfile(path, path.with_name(f"{path.name}.pitwall-backup-{int(time.time())}"))
    path.write_text(text)


def wrap_statusline(path, home, add):
    """Put Pitwall's wrapper around the Claude Code status line, or take it off again.

    The wrapper saves the status line input, which holds the plan limits, then runs the original.
    """
    if not path.parent.exists():
        return
    data = json.loads(path.read_text()) if path.exists() else {}
    line = data.get("statusLine") or {}
    saved = home / "statusline-command"
    wrapped = "pitwall-statusline" in line.get("command", "")
    if add:
        if not wrapped:
            home.mkdir(parents=True, exist_ok=True)
            saved.write_text(line.get("command", ""))
        data["statusLine"] = dict(line or {"type": "command"}, command=f'bash "{config.REPO}/bin/pitwall-statusline"')
    elif not wrapped:
        return
    elif saved.exists() and saved.read_text().strip():
        data["statusLine"] = dict(line, command=saved.read_text())
    else:
        data.pop("statusLine", None)
    _save(path, data)


def launch_agent(load):
    domain = f"gui/{os.getuid()}"
    subprocess.run(["launchctl", "bootout", f"{domain}/{LABEL}"], capture_output=True)
    if not load:
        PLIST.unlink(missing_ok=True)
        return
    PLIST.parent.mkdir(parents=True, exist_ok=True)
    PLIST.write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>{LABEL}</string>
  <key>ProgramArguments</key><array>
    <string>{config.VENV}/bin/python</string><string>-m</string><string>pitwall.daemon</string>
  </array>
  <key>WorkingDirectory</key><string>{config.REPO}</string>
  <key>EnvironmentVariables</key><dict><key>PYTHONPATH</key><string>{config.REPO}</string></dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>10</integer>
  <key>StandardOutPath</key><string>{config.LOG_FILE}</string>
  <key>StandardErrorPath</key><string>{config.LOG_FILE}</string>
</dict></plist>
""")
    # bootout returns before launchd has removed the old service, and bootstrap fails (5) until it has.
    for _ in range(20):
        result = subprocess.run(["launchctl", "bootstrap", domain, str(PLIST)], capture_output=True)
        if result.returncode == 0:
            return
        time.sleep(0.25)
    raise RuntimeError(f"launchctl could not start the service: {result.stderr.decode(errors='replace').strip()}")


def install():
    if sys.platform != "darwin" or not Path("/Applications/iTerm.app").exists():
        print("Pitwall needs macOS and iTerm2 (https://iterm2.com) in /Applications.")
        return False
    config.HOME.mkdir(mode=0o700, parents=True, exist_ok=True)
    print("Creating the daemon venv in", config.VENV)
    subprocess.run([sys.executable, "-m", "venv", str(config.VENV)], check=True)
    subprocess.run([f"{config.VENV}/bin/pip", "install", "-q", "--disable-pip-version-check", "--upgrade", "iterm2"], check=True)
    if not CLAUDE.parent.exists() and not CODEX.parent.exists():
        print("No Claude Code (~/.claude) and no Codex (~/.codex) found. Install one, then run: pitwall install")
    if CLAUDE.parent.exists():
        print("Adding hooks to", CLAUDE, "(backup kept next to it)")
        edit_hooks(CLAUDE, "claude", CLAUDE_EVENTS, add=True)
        wrap_statusline(CLAUDE, config.HOME, add=True)
    if edit_hooks(CODEX, "codex", CODEX_EVENTS, add=True):
        print("Adding hooks to", CODEX, "(Codex asks you to trust them on its next start)")
    print("Starting the daemon")
    launch_agent(load=True)
    for _ in range(30):  # the venv's first import of iterm2 takes a few seconds
        if daemon_answers():
            break
        time.sleep(0.5)
    ok = doctor()
    print("\nIn iTerm2, open View > Show Toolbelt, then Toolbelt > Pitwall.")
    return ok


def update():
    """Pull the newest version into this checkout, then run the install again."""
    before = subprocess.run(["git", "-C", str(config.REPO), "rev-parse", "--short", "HEAD"],
                            capture_output=True, text=True).stdout.strip()
    pull = subprocess.run(["git", "-C", str(config.REPO), "pull", "--ff-only"], capture_output=True, text=True)
    if pull.returncode != 0:
        print(pull.stderr.strip() or "git pull failed.")
        print(f"Update {config.REPO} by hand, then run: pitwall install")
        return False
    after = subprocess.run(["git", "-C", str(config.REPO), "rev-parse", "--short", "HEAD"],
                           capture_output=True, text=True).stdout.strip()
    print("Already up to date." if before == after else f"Updated {before} to {after}.")
    return install()


def uninstall():
    launch_agent(load=False)
    edit_hooks(CLAUDE, "claude", CLAUDE_EVENTS, add=False)
    wrap_statusline(CLAUDE, config.HOME, add=False)
    edit_hooks(CODEX, "codex", CODEX_EVENTS, add=False)
    config.DAEMON_FILE.unlink(missing_ok=True)
    print("Removed the hooks and the LaunchAgent. Delete", config.HOME, "to remove the venv and state.")


def daemon_answers():
    d = config.read_daemon()
    if not d:
        return False
    req = urllib.request.Request(f"http://127.0.0.1:{d['port']}/api/state", headers={"X-Pitwall-Token": d["token"]})
    try:
        with urllib.request.urlopen(req, timeout=2) as resp:
            return resp.status == 200
    except OSError:
        return False


def count_hooks(path):
    try:
        hooks = json.loads(path.read_text()).get("hooks", {})
    except (OSError, ValueError):
        return 0
    return sum(1 for entries in hooks.values() for e in entries if is_ours(e))


def doctor():
    api = subprocess.run(["defaults", "read", "com.googlecode.iterm2", "EnableAPIServer"], capture_output=True, text=True)
    checks = [
        ("python3 3.9 or newer is on PATH", sys.version_info >= (3, 9) and bool(shutil.which("python3")),
         "Install Python 3.9 or newer."),
        ("git is on PATH", bool(shutil.which("git")), "Install the Xcode command line tools."),
        ("iTerm2 Python API is on", api.stdout.strip() == "1",
         "In iTerm2, open Settings > General > Magic and turn on Enable Python API."),
        ("Daemon venv has the iterm2 package",
         subprocess.run([f"{config.VENV}/bin/python", "-c", "import iterm2"], capture_output=True).returncode == 0
         if Path(f"{config.VENV}/bin/python").exists() else False, "Run: pitwall install"),
        ("LaunchAgent is loaded", subprocess.run(["launchctl", "print", f"gui/{os.getuid()}/{LABEL}"],
                                                 capture_output=True).returncode == 0, "Run: pitwall install"),
        ("Daemon answers", daemon_answers(), f"Start iTerm2, then read {config.LOG_FILE}"),
    ]
    if CLAUDE.parent.exists():
        statusline = CLAUDE.exists() and "pitwall-statusline" in CLAUDE.read_text()
        checks += [("Claude Code status line feeds the plan limits", statusline, "Run: pitwall install"),
                   (f"Claude Code hooks ({len(CLAUDE_EVENTS)} events)", count_hooks(CLAUDE) == len(CLAUDE_EVENTS),
                    "Run: pitwall install")]
    if CODEX.parent.exists():
        checks.append((f"Codex hooks ({len(CODEX_EVENTS)} events)", count_hooks(CODEX) == len(CODEX_EVENTS),
                       "Run: pitwall install"))
    for label, ok, fix in checks:
        print(f"  {'ok  ' if ok else 'FAIL'}  {label}" + ("" if ok else f"\n        {fix}"))
    shell = any(Path.home().glob(".iterm2_shell_integration.*")) or bool(os.environ.get("ITERM_SHELL_INTEGRATION_INSTALLED"))
    print(f"  {'ok  ' if shell else 'opt '}  iTerm2 shell integration (needed to catch failed commands)"
          + ("" if shell else "\n        In iTerm2, open iTerm2 > Install Shell Integration."))
    return all(ok for _, ok, _ in checks)
