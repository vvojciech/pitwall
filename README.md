# Pitwall

Watch and steer Claude Code and Codex agents from iTerm2.

Pitwall is a small daemon and an iTerm2 toolbelt panel. It is not a fork of iTerm2. It uses the
iTerm2 Python API and the hooks that Claude Code and Codex already support. It follows the idea
of [GhosttyEXTREME](https://github.com/steventsvik/GhosttyEXTREME), but for iTerm2.

## What it does

- **Agent sidebar.** A toolbelt panel lists every agent in every iTerm2 tab. Each card shows
  the project, the agent, its state (working, needs permission, waiting for you, done or
  failed), the task, the last tool call and a timer. Click a card to go to its tab.
- **Tab signals.** A tab turns amber when its agent waits for you, and it gets a "Needs you"
  badge. It turns green or red when the agent finishes or fails, until you look at it. Your
  profile's own tab colour and badge come back after that.
- **Native tab status for Codex.** iTerm2's own Claude Code integration shows a status dot and
  text (idle, working, waiting) in each Claude tab. Pitwall writes the same status for Codex
  tabs, in the same colours. It leaves Claude tabs to iTerm2, so the two do not overwrite each
  other. Set **Settings > Appearance > General > Tab bar location** to **Left** to see all
  tabs as a vertical list.
- **Allow and Deny without switching.** A card that needs permission shows the command and
  two buttons. Pitwall sends the keys only when the permission menu is on screen with the
  first option selected. In all other cases it tells you to open the tab.
- **Mission Control.** All agents on one page, with the last lines of each terminal. Waiting
  agents come first. Open it with the grid button in the sidebar, or run `pitwall mission`.
- **Undo a turn.** Before each prompt, Pitwall snapshots the work tree as a git tree object.
  "Undo turn" lists the files it will change, then puts them back. "Redo" brings the agent's
  changes back. Pitwall does not change your index, commits, branches or stash. Ignored
  files such as `node_modules` stay as they are.
- **Timeline.** "Timeline" on a card shows the agent's prompts, thinking, replies, tool calls
  and sub-agents, read from its transcript. It updates while it is open.
- **Hand off.** "Hand off" on a card writes a message for Claude or Codex: the task, the recent
  activity, the diff since the first prompt and the failed commands for the project. Choose
  Continue, Review or Opinion, edit the text, and send it. The other agent starts in a new
  split beside the first one.
- **Shared memory.** A new Codex session starts with the Claude Code notes for the project, and
  a new Claude Code session starts with the Codex memories. Both are marked as possibly out of
  date. Turn it off with `PITWALL_SHARED_MEMORY=0`.
- **Failed commands.** When a command fails in a shell tab, the panel shows it with its last
  output lines. "Send to Claude" types it into the agent that works in that project, when the
  agent is not busy. With no agent there, "Fix with Claude" or "Codex" starts one in a new
  split. This needs iTerm2 shell integration.
- **Dev server tabs.** When Claude starts a dev server (`npm run dev`, `vite`, `rails s` and
  others), Pitwall runs it in its own tab, so it keeps running after the turn. Claude gets
  the path of the log file. Turn it off with `PITWALL_DEV_TABS=0`.
- **Ports.** The panel lists the ports that your projects listen on, with Open and Stop.
- **Setup and doctor.** `pitwall install` adds the hooks, with a backup of each file it
  changes, and starts the daemon. `pitwall doctor` checks each part and tells you the fix.

## Install

You need macOS, iTerm2 3.6 or newer with the Python API on, Python 3.9 or newer and git.

```sh
git clone https://github.com/vvojciech/pitwall.git
cd pitwall
bin/pitwall install
```

Then in iTerm2, open **View > Show Toolbelt**, and select **Toolbelt > Pitwall**.

To turn on the Python API, open iTerm2 **Settings > General > Magic** and select
**Enable Python API**.

Codex asks you to trust new hooks. Start Codex once after the install and approve them.

To open Mission Control from a key, open iTerm2 **Settings > Keys > Key Bindings**, add a
binding, select **Invoke Script Function**, and enter `pitwall_mission_control()`.

## Commands

| Command | What it does |
|---|---|
| `pitwall install` | Make the venv, add the hooks, start the daemon |
| `pitwall uninstall` | Remove the hooks and stop the daemon |
| `pitwall doctor` | Check the setup |
| `pitwall mission` | Open Mission Control |

## How it works

1. Claude Code and Codex run `pitwall hook <agent> <event>` on each hook event. The hook
   reads `ITERM_SESSION_ID` to know its tab. It prints nothing and always exits 0, so it
   cannot break the agent.
2. The hook posts the event to the daemon on `127.0.0.1`. The daemon makes a new random
   token at each start, and it refuses each request without that token. The token is in
   `~/.pitwall/daemon.json`, which only you can read.
3. The daemon runs as a LaunchAgent in its own venv with the `iterm2` package. It waits
   for iTerm2 to start, and it starts again when iTerm2 quits.
4. The daemon serves the sidebar page and registers it as a toolbelt tool.

State and logs are in `~/.pitwall/`. Nothing leaves your Mac.

## Limits

- The macOS notification for a waiting agent comes from Claude Code itself. Click it to go to
  the tab. It has no Allow or Deny buttons. That needs a native helper app.
- Undo works in git repositories only. Snapshots are not referenced by a ref, so
  `git gc` can remove them after its prune window (two weeks by default).
- Mission Control opens in your default browser, not in an iTerm2 tab.

## Development

```sh
python3 -m unittest
```

To run a second daemon for a test, give it its own state folder, and keep it off the toolbelt:

```sh
PITWALL_HOME=/tmp/pw PITWALL_NO_TOOLBELT=1 PYTHONPATH=. ~/.pitwall/venv/bin/python -m pitwall.daemon
```

## License

MIT
