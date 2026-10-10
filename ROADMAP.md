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
- 0.5.0: answer Claude's questions from the card.
- 0.5.1: Codex checked live: card, task, action, context ring, Allow, Deny and timeline.
- 0.7.0: scheduled prompts (Night shift phase 1), checked live with a real `/loop`, a repeating
  job and a reminder: rows, fire detection, and Stop for a job and for a loop.
- 0.1.0: one-line installer, `pitwall update`, CI on Python 3.9 and 3.13, README screenshots.
- 0.2.0: live tests with real Claude agents for Allow, Deny, Send to Claude, Hand off and review
  loops.
- Removed after use: Mission Control (2026-10-10), and dev server tabs (2026-10-10: they took
  dev servers away from the session even when the user asked for a background run).

## Verify next

1. **Activity tooltip.** Its content is tested; its look is not, because the render tool cannot
   capture it.
2. **Scheduled prompt states.** "due" and "stopping" are tested in code and seen in the live API,
   not yet on a screenshot.

## Next features

| Rank | Feature | Size | Notes |
|---|---|---|---|
| 1 | Night shift phase 2 | M | Show the runs of Claude Desktop scheduled tasks and cloud routines as cards, and land their work through a worktree, a review and Merge or Discard. Design: `docs/plans/2026-10-10-schedule-view-design.md`. |
| 2 | Night shift phase 3 | L | Pitwall's own scheduler, only for what Claude does not cover: shell command jobs and local runs with no app open. Decide after phase 2. |
| 3 | Isolated sessions | M | A sandboxed Claude or Codex in a throwaway Docker container with only the project mounted. |
| 4 | Project memory window | E | Read and edit CLAUDE.md, AGENTS.md and the Claude notes for a project in one place. |
| 5 | Background processes | M | Find stale dev servers, VMs and agents across the machine, and close them. |

## Not planned

- **Review inbox.** iTerm2 3.7 already has Diff and Code Review views for Claude tabs.
- **Follow-mode editor, backend view, database view, Visual Fix.** Each is a large
  web app of its own.

## Known limits

- iTerm2 always docks the toolbelt on the right.
- Notifications have no Allow or Deny buttons. That needs a native helper app.
- Undo works in git repositories only.
- Codex keeps one set of memories for all projects, so Claude gets all of them.