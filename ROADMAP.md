# Roadmap

## Done

- Agent sidebar in the iTerm2 toolbelt, with Allow and Deny, Undo and Redo.
- Tab colour and badge signals, and the native tab status for Codex.
- Mission Control, `pitwall install`, `pitwall doctor`.
- Agent discovery, and protection against agents nested in another agent's tab.
- Shared memory between Claude Code and Codex.
- Timeline, Hand off, failed commands, dev server tabs and ports.

## Verify next

1. **Allow and Deny on a real prompt.** Only the refusal path is tested on a live agent.
2. **Failed commands.** Install iTerm2 shell integration, make a command fail in a shell tab,
   and check the panel. The section is tested only with sample data.
3. **Hand off and Fix with.** Send one to Codex and one to Claude, and check that the new
   split starts the agent with the message.
4. **Dev server tabs.** Ask Claude to start a dev server, and check that it gets its own tab and
   that Claude reads the log.
5. **Codex.** Approve the hooks in Codex once, then check its card, tab status and timeline.

## Next features

| Rank | Feature | Size | Notes |
|---|---|---|---|
| 1 | Review loops | M | Hand off in Review mode after each turn, and send the findings back until APPROVED. |
| 2 | Agent races | M | One task, several agents, each in its own worktree; compare the diffs and keep one. |
| 3 | Activity and plan usage | M | Time, prompts and tokens per project. Check `ccusage` first. |
| 4 | Busy port help | E | When a command fails with EADDRINUSE, name the process that holds the port. |

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
