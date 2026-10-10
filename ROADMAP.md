# Roadmap

## Done

- Agent sidebar in the iTerm2 toolbelt, with Allow and Deny, Undo and Redo.
- Tab colour and badge signals, and the native tab status for Codex.
- Mission Control, `pitwall install`, `pitwall doctor`.
- Agent discovery, and protection against agents nested in another agent's tab.
- Shared memory between Claude Code and Codex.
- Timeline, Hand off, failed commands, dev server tabs and ports.
- Busy port help, review loops, agent races, activity and plan usage.

## Verify next

1. **Allow and Deny on a real prompt.** Claude draws its menu with NUL cells, which hid it from
   Pitwall until 2026-10-10. The fix is tested on a race's trust menu, not on a permission menu.
2. **Send to Claude and Fix with.** Detection of failed commands is tested live; typing the
   failure into an agent is not.
3. **Hand off and review loops.** Run one of each with real agents. The loop is tested with fakes.
4. **Dev server tabs.** Ask Claude to start a dev server, and check that it gets its own tab and
   that Claude reads the log.
5. **Codex.** Approve Pitwall's hooks in Codex once (Codex asks at its next start), then check its
   card, tab status and timeline.
6. **Activity tooltip.** Its content is tested; its look is not, because the render tool cannot
   capture it.

## Next features

| Rank | Feature | Size | Notes |
|---|---|---|---|
| 1 | Isolated sessions | M | A sandboxed Claude or Codex in a throwaway Docker container with only the project mounted. |
| 2 | Project memory window | E | Read and edit CLAUDE.md, AGENTS.md and the Claude notes for a project in one place. |
| 3 | Background processes | M | Find stale dev servers, VMs and agents across the machine, and close them. |

## Not planned

- **Review inbox.** iTerm2 3.7 already has Diff and Code Review views for Claude tabs.
- **Follow-mode editor, code map, backend view, database view, Visual Fix.** Each is a large
  web app of its own.

## Known limits

- iTerm2 always docks the toolbelt on the right.
- Notifications have no Allow or Deny buttons. That needs a native helper app.
- Mission Control opens in the default browser.
- Undo works in git repositories only.
- Codex keeps one set of memories for all projects, so Claude gets all of them.
- Dev server tabs work for Claude only. Codex has no way to refuse a command with a reason.
