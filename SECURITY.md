# Security

Pitwall can answer permission prompts and send text into your terminal sessions, so a bug here
can matter more than it looks. If you find one, please tell me privately first.

## Reporting

Use [Report a vulnerability](https://github.com/vvojciech/pitwall/security/advisories/new) on the
Security tab. Please don't open a public issue.

Say what you found, how to reproduce it, and which version you ran (`pitwall --version`). I'll
reply within a week. Once a fix is out, I'll publish the advisory and credit you unless you'd
rather I didn't.

## Supported versions

Only the latest code on `main` gets fixes. `install.sh` installs from `main`, and running it again
updates you.

## What counts

Anything that lets another process, web page or user on the machine drive your agents, read
their transcripts, or run commands through Pitwall. Problems in the installer count too.

Bugs in Claude Code, Codex or iTerm2 themselves go to those projects.
