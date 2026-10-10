# Changelog

## Unreleased

- An **Update** button shows in the top bar of the panel when a newer Pitwall is on GitHub. It runs
  `pitwall update`, and the panel comes back by itself. Pitwall checks with `git fetch` every 6
  hours; `launchctl setenv PITWALL_UPDATE_CHECK 0` turns the check off.
- Fixed: `pitwall update` ran the old installer after it pulled the new code. (#3)
- `pitwall install` no longer says it creates the venv when the venv is already there.
- Fixed: the panel and the activity page showed empty Codex rows on a Mac without Codex. They
  now show only the agents that are installed. (#2)

- Fixed: `pitwall install` printed a pip upgrade warning on the stock macOS Python. (#1)

## 0.5.1 (2026-10-10)

- Codex checked end to end: card, task, last action, context ring, Allow, Deny and timeline.
- Fixed: the timeline showed Codex commands as JavaScript (`tools.exec_command({cmd:...})`). It
  now shows `Bash <command>`, as the card does.
- Fixed: `pitwall install` and `pitwall update` could fail with "Bootstrap failed: 5" when the
  service was already running, and leave it stopped. Pitwall now waits for launchd.
- Fixed: Codex warned "clamping Interrupt hook timeout to 3s". Pitwall's Codex Interrupt hook now
  asks for 3 seconds. The change keeps the hook trusted.

## 0.5.0 (2026-10-10)

- Claude's questions (AskUserQuestion) show on the card with their options, not as a permission
  prompt. A single-choice question takes one click; other questions collect picks until **Send**.
  Pitwall types the answers only when the menu is on screen and nobody answered part of it.
- Fixed: a card could show `<task-notification>` as its task, from state that an older version saved.

## 0.4.1 (2026-10-10)

- All tab signal colours are dark: dark amber for waiting, dark green for finished, dark red for
  failed.
- Fixed: after a restart, a tab could keep a bright colour from an older version, because Pitwall
  took its own leftover colour for the user's. Pitwall now recognises its own colours and badges,
  old and new, and clears leftovers when it starts.

## 0.4.0 (2026-10-10)

- A context ring on each agent card shows how full its context window is: neutral, then amber from
  80% and red from 90%. Hover for the percentage, window size and tokens. The status line wrapper
  now also keeps one status file per Claude session; files older than three days are removed.

## 0.3.0 (2026-10-10)

- Removed: dev server tabs. Pitwall no longer takes a dev server away from the session; Claude
  runs it as it chooses, normally as a background task, which the card lists. The
  `PITWALL_DEV_TABS` setting is gone.
- Changed: the "finished" tab colour is a very dark green, so it does not shout.

## 0.2.0 (2026-10-10)

- The code map shows the work, not the whole project: "This turn" (files read, edited, or changed
  since the last prompt, also through shell commands) and "Uncommitted" (everything that differs
  from the last commit). Chips count changed, visited and read files, and lines.
- One code map above Ports follows the agent in your active tab. The Map buttons on cards are gone.
- Cards list each Claude Code agent's background work (shells, sub-agents, monitors, scheduled
  wake-ups), and the header counts it.
- Fixed: pasted prompts (hand-offs, review messages, Send to Claude) did not update the card's task,
  the timeline or the prompt count. Claude Code wraps pasted text in tags, which Pitwall skipped.
- Changed: dev server logs go to `.pitwall/` inside the project (hidden from git), so Claude reads
  them without a permission prompt.
- Tested live with real Claude agents: Allow, Deny, dev server tabs, Send to Claude, Hand off and a
  review loop.

## 0.1.0 (2026-10-10)

The first release.

- Agent sidebar in the iTerm2 toolbelt for Claude Code and Codex: state, task, last action,
  timer, and a click that gives the agent's pane keyboard focus.
- Allow and Deny for permission prompts, sent only when the prompt is on screen.
- Tab colour and badge signals; the native iTerm2 tab status for Codex.
- Undo and Redo for an agent's turn, from git tree snapshots.
- Code map: folders by type, files read and edited this turn, the blast radius of an edit.
- Timeline, Hand off, review loops and agent races.
- Shared memory between Claude Code and Codex.
- Failed commands with "Send to Claude" and "Fix with"; busy port help.
- Dev server tabs and a ports list.
- Activity page and plan limit meters for Claude and Codex.
- `pitwall install`, `update`, `uninstall`, `doctor`, `activity`, and a one-line
  installer.
