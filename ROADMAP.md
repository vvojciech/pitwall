# Roadmap

## Done

- Agent sidebar in the iTerm2 toolbelt, with Allow and Deny, Undo turn and Redo.
- Tab colour and badge signals, and the native tab status for Codex.
- Mission Control, `pitwall install`, `pitwall doctor`.
- Agent discovery: a scan every 5 seconds adds agents that fired no hook yet, and removes
  agents that quit without a SessionEnd. A Claude run inside another agent's tab
  (`claude -p` in a script) is ignored, so it cannot remove or finish the outer card.

## Verify next

1. **Allow and Deny on a real prompt.** Only the refusal path is tested on a live agent.
2. **Cards stay while agents work.** Watch for a card that disappears or loses its task.
   If one does, send the time, so the cause can be found in `~/.pitwall/daemon.log`.
3. **Codex.** Approve the hooks in Codex once, then check that its card and tab status follow it.

## Next features

Ranked by value for effort. E is easy, M is medium.

| Rank | Feature | Size | Notes |
|---|---|---|---|
| 1 | Shared memory between Claude and Codex | E | A SessionStart hook gives each agent the other's notes for the project. Needs no iTerm2 work. |
| 2 | Fix with Claude for a failed command | M | iTerm2 shell integration already marks each command and its exit code. A trigger offers to send the command and output to the agent in that project. |
| 3 | Hand off | M | Send a pane's task, its diff since the first prompt and its failed commands to a new or running Claude or Codex. |
| 4 | Agent timeline | M | Expand a card to see its prompts, tool calls and sub-agents, read from the transcript file. |
| 5 | Localhost sessions and ports | M | Move a dev server that an agent starts into its own tab; list listening ports per project. |
| 6 | Agent races | M | One task, several agents, each in its own worktree; compare the diffs and keep one. |
| 7 | Activity and plan usage | M | Time, prompts and tokens per project. Check `ccusage` first. |

## Not planned

- **Review inbox.** iTerm2 3.7 already has Diff and Code Review views for Claude tabs.
- **Follow-mode editor, code map, backend view, database view, Visual Fix.** Each is a large
  web app of its own. Start one only when the features above are done.

## Known limits

- iTerm2 always docks the toolbelt on the right. A left panel would need a browser pane in each
  window, which iTerm2 does not keep fixed when you change tabs.
- Notifications have no Allow or Deny buttons. That needs a native helper app.
- Mission Control opens in the default browser.
- Undo works in git repositories only.
