# Roadmap

## Done

- Agent sidebar in the iTerm2 toolbelt, with Allow and Deny, Undo and Redo.
- Tab colour and badge signals, and the native tab status for Codex.
- `pitwall install`, `pitwall doctor`. (Mission Control was built, then removed on 2026-10-10.)
- Agent discovery, and protection against agents nested in another agent's tab.
- Shared memory between Claude Code and Codex.
- Timeline, Hand off, failed commands and ports.
- Busy port help, review loops, agent races, activity and plan usage.
- Code map of the work (this turn or uncommitted), following the active tab.
- 0.1.0: one-line installer, `pitwall update`, CI on Python 3.9 and 3.13, README screenshots.
- 0.2.0: live tests with real Claude agents for Allow, Deny, Send to Claude, Hand off and review
  loops.
- Removed after use: Mission Control (2026-10-10), and dev server tabs (2026-10-10: they took
  dev servers away from the session even when the user asked for a background run).

## Verify next

1. **Codex.** Approve Pitwall's hooks in Codex once (Codex asks at its next start), then check its
   card, tab status and timeline.
2. **Activity tooltip.** Its content is tested; its look is not, because the render tool cannot
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
- Undo works in git repositories only.
- Codex keeps one set of memories for all projects, so Claude gets all of them.