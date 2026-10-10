# Schedule view: design

Date: 2026-10-10. Status: approved. Phase 1 of "Night shift".

## Goal

Show every scheduled prompt of every Claude Code session on its card: `/loop` iterations,
`CronCreate` jobs and one-shot reminders. Show when each one fires next. Let the user stop one.

Phase 1 observes. It does not schedule anything itself. Phase 2 (runs of Desktop scheduled
tasks and cloud routines) and phase 3 (an own scheduler) wait for real use of phase 1.

## What Claude Code gives us

Measured with captured hook payloads on Claude Code 2.1, 2026-10-10.

| Source | Data |
|---|---|
| `Stop` payload, `session_crons` | Full list: `id`, `schedule` (5-field cron), `recurring`, `prompt` |
| `PostToolUse` `CronCreate` | input `cron`, `prompt`, `recurring`; response `id`, `humanSchedule` |
| `PostToolUse` `CronDelete` | input `id` |
| `PostToolUse` `ScheduleWakeup` | input `delaySeconds`, `reason`, `prompt`, `stop`; response `scheduledFor` (ms) |

- A dynamic `/loop` wake-up also appears in `session_crons` as a one-shot job whose prompt
  starts with `/loop`.
- No payload gives a creation time or a next fire time. Pitwall records the first time it sees a
  job and computes the next fire from the cron expression.
- Jobs live in the session's memory only. They die with the session. Recurring jobs expire
  after 7 days.
- Codex CLI has no scheduler. Phase 1 covers Claude only.

## Data flow

1. `events.py` turns the payloads into event fields: `crons` (the full list, trimmed),
   `cron_add`, `cron_del` and `wakeup`.
2. `state.py` keeps `schedules` on the session, keyed by job id. `Stop` replaces the list (it is
   the authority). The tool events update it between stops. `first_seen` is kept across updates.
   A `UserPromptSubmit` whose text equals a job's prompt sets `last_fired`.
3. `schedules.py` holds the pure logic: a 5-field cron matcher, `next_fire`, and `view()`, which
   adds `kind`, `next`, `expires` and a label for the panel.
4. `daemon.state()` sends the view. The panel ticks the countdowns once a second.

### Next fire rules

- Wake-up with `scheduledFor`: use it.
- Otherwise the next cron match after `max(first_seen, last_fired, now - GRACE)`.
- `GRACE` is 15 minutes, the maximum jitter Claude Code adds. A job stays "due" for up to
  15 minutes after its time, then rolls forward. So a fire that Pitwall did not see never
  leaves a row stuck on "due".
- A session fires only when idle. A busy session shows "due" until its turn ends.

## UI

- **Card:** one row per job in the existing background list. Kind label (`loop`, `repeats`,
  `once`), the prompt (without `/loop`), a live countdown, and a Stop button. The title shows the
  readable schedule and the expiry. "expires in 5h" shows in amber when under 24 hours remain.
- **Header:** "2 scheduled, next in 4m" next to the background count.
- **Stop:** `POST /api/schedule/stop {sid, id}` pastes into the tab:
  "Cancel scheduled job <id> with CronDelete. If it drives a /loop, stop the loop too."
  The row shows "stopping" until the next payload drops the job.

## Error handling

- Malformed cron or unknown field: the row shows the raw schedule and no countdown.
- Missing `id` in a tool response: wait for the next `Stop` list.
- Prompts are trimmed to one line of 120 characters. All text is escaped in the panel.

## Testing

- Unit tests (unittest, Python 3.9): cron matcher (`*`, `*/n`, ranges, lists, day-of-week and
  day-of-month OR rule), `next_fire` across month and year ends, grace roll-forward, event
  parsing from the captured payloads, state merging, one-shot removal after a fire.
- Demo data in `scripts/demo.py` for the three kinds.
- Live check: a real Claude session in iTerm2 with `/loop` and a reminder, a panel screenshot,
  and Stop.
